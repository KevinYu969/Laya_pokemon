"""常駐PyBoy＋離線Laya；60秒檢查點、逐館檢討、關鍵畫面與時間帳。"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import time

from .core import parse_rom_header,sha256_file,utc_now,write_json,append_jsonl
from .game import observe,advance_action,run_with_window_events,WindowClosed,TimeBudgetReached
from .runtime import enable_offline_runtime
from .policy import LayaPolicy,PINNED_REVISION
from .progress import read_progress
from .video import VideoRecorder
from .campaign_journal import Journal
from .loss_review import LossGuard,parse_loss_review,frame_loss_signal


class BattleLossDuringAction(Exception):
    pass


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--rom',required=True);parser.add_argument('--state',required=True);parser.add_argument('--plan',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();root=Path.cwd();rom=Path(args.rom).resolve();source=Path(args.state).resolve();plan_path=Path(args.plan).resolve();out=Path(args.output).resolve()
    if not all(p.is_relative_to(root) for p in [rom,source,plan_path]) or not out.is_relative_to(root/'outputs'):raise ValueError('輸入與輸出須在本專案')
    if parse_rom_header(rom)['sha256']!='5ca7ba01642a3b27b0cc0b5349b52792795b62d3ed977e98a09390659af96b7b':raise ValueError('ROM版本不符')
    enable_offline_runtime();os.environ['HF_HOME']=str(root/'.cache/huggingface');out.mkdir(parents=True,exist_ok=False)
    from pyboy import PyBoy
    from pyboy.utils import WindowEvent
    from . import campaign_route
    started=time.monotonic();stats={'recorded_at':utc_now(),'status':'running','source_state_sha256':sha256_file(source),'model_load_count':0,'actions':0,'uncached_choices':0,'cache_hits':0,'model_wait_seconds':0.,'review_pause_seconds':0.,'emulated_frames':0,'checkpoint_interval_seconds':60,'cloud_fallback':False,'strata_configuration_changed':False}
    emulator=recorder=None;previous=[];step_id=None;segment=0;plan_sha=None;last_pos=None;stalled=0;known_maps=set();known_battles=set();cursor_revision=None;loss_guard=LossGuard()
    def timing():
        wall=time.monotonic()-started
        return {'wall_seconds':round(wall,3),'model_wait_seconds':round(stats['model_wait_seconds'],3),'review_pause_seconds':round(stats['review_pause_seconds'],3),'non_review_session_seconds':round(wall-stats['review_pause_seconds'],3),'emulated_seconds':round(stats['emulated_frames']/60,3)}
    def save(name):
        target=out/name;temporary=target.with_suffix(target.suffix+'.tmp')
        with temporary.open('wb') as stream:emulator.save_state(stream)
        temporary.replace(target);return target
    def persist():
        stats.update(timing=timing(),route_step=step_id,segment=segment);write_json(out/'summary.json',stats)
    def pause(reason,state,old_plan_hash):
        nonlocal plan_sha
        pause_start=time.monotonic();save('checkpoint.state');stats.update(status='paused_for_review',review_reason=reason);persist()
        request={'at':utc_now(),'reason':reason,'state':state,'timing':timing(),'route_step':step_id,'plan_sha256':old_plan_hash}
        write_json(out/'review-request.json',request);journal.capture(emulator,'review-'+reason,state,timing())
        emulator.send_input(WindowEvent.PAUSE)
        try:
            while True:
                if not emulator.tick(1,True,False):raise WindowClosed('使用者關窗')
                if (out/'STOP').exists():raise KeyboardInterrupt
                if (out/'RESUME').exists():
                    resume=(out/'RESUME').read_text(encoding='utf-8')
                    review=parse_loss_review(resume) if reason=='battle_loss_requires_review' else resume
                    if review is not None:
                        (out/'RESUME').unlink();append_jsonl(out/'reviews.jsonl',{'at':utc_now(),'reason':reason,'review':review});break
                if reason not in {'gym_review','battle_loss_requires_review'} and sha256_file(plan_path)!=old_plan_hash:break
                time.sleep(.1)
        finally:
            emulator.send_input(WindowEvent.UNPAUSE);stats['review_pause_seconds']+=time.monotonic()-pause_start;stats['status']='running';persist()
        importlib.reload(campaign_route)
        import laya_pokemon.battle as battle_module
        importlib.reload(battle_module)
    def frame_ready(frame):
        stats['emulated_frames']+=1
        if recorder and stats['emulated_frames']%4==0:recorder.append(frame)
        if not loss_guard.latched and frame_loss_signal(emulator.memory):
            raise BattleLossDuringAction()
    try:
        emulator=PyBoy(str(rom),window='SDL2',scale=4,sound_emulated=False,title_status=True);emulator.set_emulation_speed(0)
        with source.open('rb') as stream:emulator.load_state(stream)
        advance_action(emulator,'wait',1,0)
        journal=Journal(out,read_progress(emulator));recorder=VideoRecorder(out/'video-000.mp4',fps=15,scale=3)
        t=time.monotonic();policy=run_with_window_events(emulator,lambda:LayaPolicy(revision=PINNED_REVISION,threads=4,offline=True,cache=True),time.perf_counter()+60,WindowEvent.PAUSE,WindowEvent.UNPAUSE)
        stats['model_wait_seconds']+=time.monotonic()-t;stats['model_load_count']=1;stats['model_load_seconds']=policy.load_seconds
        segment_started=time.monotonic();last_checkpoint=segment_started
        while True:
            if (out/'STOP').exists():raise KeyboardInterrupt
            if (out/'REVIEW').exists():
                (out/'REVIEW').unlink();pause('operator_review',state,plan_sha)
            plan=json.loads(plan_path.read_text(encoding='utf-8'));plan_sha=sha256_file(plan_path)
            if plan.get('resume_revision')!=cursor_revision:
                step_id=plan.get('resume_step',step_id);cursor_revision=plan.get('resume_revision')
            state=observe(emulator,'Continue Pokemon Red toward the Champion.','KEVIN',previous,True,'BULBASAUR','first_gym')
            loss=loss_guard.observe(state)
            if loss:
                journal.battle_loss(emulator,state,loss,timing(),save)
                pause('battle_loss_requires_review',state,plan_sha);continue
            # 已核對並解除同一場敗北：只讓遊戲完成倒下／回城動畫，不再反覆觸發同一敗北。
            if loss_guard.latched and state.get('review_reason')=='battle_loss_requires_review':
                state.update(phase='battle_dialogue',objective='Confirm the current selection.',available_actions=['a','b'])
            # 原observe的first_gym路線只用於解析戰鬥；實際行程由本次已核對plan接管。
            if state['phase']=='overworld':state['phase']='unclassified'
            if plan.get('mode')=='battle_recovery' and state.get('battle_state',{}).get('kind')=='none' and campaign_route.healthy(state['progress']):
                pause('recovery_complete',state,plan_sha);continue
            milestones=journal.observe(emulator,state,timing(),save)
            if any(m['kind']=='gym' for m in milestones):pause('gym_review',state,plan_sha);continue
            if any(m['id']=='beat_champion_rival' for m in milestones):
                stats['champion_event_seen']=True
            if state['phase']=='strategy_review':pause(state.get('review_reason','strategy_review'),state,plan_sha);continue
            if state['phase']=='unclassified':
                context,step_id=campaign_route.waypoint(emulator,state,plan,step_id,previous)
                state.update(context)
            if state['phase']=='campaign_review':pause(state['review_reason'],state,plan_sha);continue
            state['campaign_step']=step_id
            mid=state.get('location',{}).get('map_id')
            if mid not in known_maps and state.get('world_path_hint'):
                known_maps.add(mid);journal.capture(emulator,'map-'+str(mid),state,timing())
            if state.get('battle_state',{}).get('active'):
                key=(mid,state.get('enemy_species'),state['battle_state']['kind'])
                if state['phase']=='battle_menu' and key not in known_battles:known_battles.add(key);journal.capture(emulator,'battle-'+str(state.get('enemy_species') or 'unknown'),state,timing())
            text=' '.join(state.get('visible_text_candidates',[])).upper()
            for marker,kind in [('GREW','level-up'),('EVOLVED','evolution'),('WAS CAUGHT','capture'),('BADGE','badge-dialogue'),('DEFEATED','trainer-defeated'),('LEARNED','move-learned')]:
                if marker in text:journal.capture(emulator,kind,state,timing())
            position=(mid,state.get('location',{}).get('x'),state.get('location',{}).get('y'),state.get('goal'))
            stalled=stalled+1 if state['phase']=='overworld' and position==last_pos else 0;last_pos=position
            if stalled>=25:stalled=0;pause('navigation_stall',state,plan_sha);continue
            before=time.monotonic();decision=run_with_window_events(emulator,lambda:policy.choose(state),time.perf_counter()+60,WindowEvent.PAUSE,WindowEvent.UNPAUSE);stats['model_wait_seconds']+=time.monotonic()-before
            settle=120 if state['phase'] in {'dialogue','battle_dialogue','battle_animation'} else 32
            try:
                frames=advance_action(emulator,decision['action'],8,settle,frame_ready)
            except BattleLossDuringAction:
                state=observe(emulator,'Review the battle loss.','KEVIN',previous,True,'BULBASAUR','first_gym')
                loss=loss_guard.observe(state)
                if not loss:raise RuntimeError('逐幀敗北訊號與完整觀測不一致；停止核對')
                journal.battle_loss(emulator,state,loss,timing(),save)
                pause('battle_loss_requires_review',state,plan_sha);continue
            previous.append(decision['action']);previous=previous[-8:]
            stats['actions']+=1;stats['cache_hits']+=bool(decision.get('prediction_cache_hit'));stats['uncached_choices']+=not decision.get('prediction_cache_hit',False)
            append_jsonl(out/f'steps-{segment:03}.jsonl',{'at':utc_now(),'step':stats['actions'],'state':state,**decision,'emulated_frames':frames,'timing':timing()})
            if time.monotonic()-last_checkpoint>=10:save('checkpoint.state');last_checkpoint=time.monotonic();persist()
            if time.monotonic()-segment_started>=60:
                save('segment-%03d.state'%segment);video=recorder.close();append_jsonl(out/'segments.jsonl',{'at':utc_now(),'segment':segment,'timing':timing(),'video':video});segment+=1;recorder=VideoRecorder(out/f'video-{segment:03}.mp4',fps=15,scale=3);segment_started=time.monotonic();persist()
    except (KeyboardInterrupt,WindowClosed,TimeBudgetReached) as error:
        stats.update(status='saved_stopped',stop_reason=type(error).__name__)
    except Exception as error:
        stats.update(status='failed',error_type=type(error).__name__,error=str(error));raise
    finally:
        if recorder:
            stats['last_video']=recorder.close()
        if emulator:
            try:save('final.state');emulator.screen.image.save(out/'last-frame.png')
            finally:emulator.stop(save=False)
        persist()


if __name__=='__main__':main()
