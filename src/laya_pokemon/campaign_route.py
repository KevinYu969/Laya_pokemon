"""可核對的正常遊戲行程；路線資料可熱更新，不寫遊戲記憶體。"""
import importlib
import json
import time
from . import party_control,balanced_training
if 'waypoint' in globals():
    importlib.reload(party_control)
    importlib.reload(balanced_training)
from . import world_map
importlib.reload(world_map)
read_world_grid,world_direction=world_map.read_world_grid,world_map.world_direction
_LEARNED_EDGES=globals().get('_LEARNED_EDGES',{})
_LAST_ATTEMPT=globals().get('_LAST_ATTEMPT')
_FIELD_CONTROLLERS=globals().get('_FIELD_CONTROLLERS',{})
_GYM_CONTROLLERS=globals().get('_GYM_CONTROLLERS',{})
_SCRIPT_WAITS=globals().get('_SCRIPT_WAITS',{})
_VIA_PROGRESS=globals().get('_VIA_PROGRESS',{})
from . import field_moves as field_moves_module
importlib.reload(field_moves_module)
from . import gym_switches as gym_switches_module
importlib.reload(gym_switches_module)
from . import campaign_transactions
importlib.reload(campaign_transactions)
from . import capture_transaction
importlib.reload(capture_transaction)
from . import campaign_safety,capture_closing_gate
from . import safari_entry
importlib.reload(safari_entry)
from . import hm_teaching_bridge
importlib.reload(hm_teaching_bridge)
from . import vending_bridge
importlib.reload(vending_bridge)
importlib.reload(campaign_safety)
importlib.reload(capture_closing_gate)
for controller in _GYM_CONTROLLERS.values():controller._last_now=None


def switch_context(pyboy,state,plan,step_id,previous):
    step=next((s for s in plan['steps'] if s['id']==step_id),None)
    if not step or step['kind']!='gym_switches':return None
    GymSwitchController=gym_switches_module.GymSwitchController
    from .observation import read_visible_text
    loc=state['location'];grid=read_world_grid(pyboy,loc)
    blocked=[tuple(p) for p in plan.get('blocked',{}).get(str(loc['map_id']),[])]
    npcs=world_map.read_npc_obstacles(pyboy,grid,blocked) if grid else None
    if npcs:blocked=list(set(blocked)|set(npcs['positions']))
    controller=_GYM_CONTROLLERS.setdefault(step_id,GymSwitchController())
    controller.__class__=GymSwitchController
    revision=step.get('reviewed_controller_revision',0)
    if revision>getattr(controller,'_reviewed_revision',0) and controller._review_reason==step.get('reviewed_controller_error'):
        controller._review_reason=None;controller._reviewed_revision=revision
    context=controller.context(read_visible_text(pyboy),loc,state['progress'],grid,battle_state=state.get('battle_state'),previous=previous,blocked=blocked)
    if context is None:return None
    next_id=step_id
    if context.get('gym_switches_complete'):
        index=plan['steps'].index(step)+1
        next_id=plan['steps'][index]['id'] if index<len(plan['steps']) else 'complete'
    return context,next_id


def field_context(pyboy,state,plan,step_id):
    """僅精確field步驟可接管HM UI；其他未知學招仍由主程序暫停。"""
    step=next((s for s in plan['steps'] if s['id']==step_id),None)
    if vending_bridge.applies(step_id,step):
        if (set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'vending_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return vending_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                      read_world_grid(pyboy,state['location']))
    if hm_teaching_bridge.applies(step_id,step):
        if (set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'hm_teaching_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return hm_teaching_bridge.context(state,plan,step_id,read_visible_text(pyboy),
                                          read_world_grid(pyboy,state['location']))
    if safari_entry.applies(step_id,step,state):
        from .observation import read_visible_text
        return safari_entry.field_context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                         read_world_grid(pyboy,state['location']))
    if capture_transaction.applies(step_id,step):
        from .observation import read_visible_text
        closing=capture_closing_gate.eligible(state,plan,step_id)
        result=capture_transaction.context(pyboy,state,plan,step_id,read_visible_text(pyboy),read_world_grid(pyboy,state['location']))
        return capture_closing_gate.restrict(result) if closing else result
    if campaign_transactions.applies(step_id,step):
        from .observation import read_visible_text
        return campaign_transactions.context(pyboy,state,plan,step_id,read_visible_text(pyboy),read_world_grid(pyboy,state['location']))
    if not step:return None
    if step['kind'] not in {'teach_cut','use_cut'}:return None
    if state.get('battle_state',{}).get('kind')!='none':return None
    loc=dict(state['location'])
    if loc['map_id']!=step['map_id'] or [loc['x'],loc['y']]!=step['target']:return None
    from .observation import read_visible_text
    CutController=field_moves_module.CutController
    loc['facing']={0:'down',4:'up',8:'left',12:'right'}.get(int(pyboy.memory[0xC109]))
    grid=read_world_grid(pyboy,loc)
    controller=_FIELD_CONTROLLERS.get(step_id)
    if controller is not None:
        controller.__class__=CutController
        revision=step.get('reviewed_controller_revision',0)
        if revision>getattr(controller,'_reviewed_revision',0) and controller.error==step.get('reviewed_controller_error'):
            controller.error=None;controller._reviewed_revision=revision
    if controller is None:
        if grid is None:return None
        if step['kind']=='use_cut' and loc['facing']!=step.get('face'):
            direction=step['face']
            return ({'phase':'field_move_menu','objective':f'Move {direction.upper()}.','available_actions':[direction,'wait'],'controller_menu_verified':True},step_id)
        candidates=[m['species'] for m in state['progress'].get('party',[])
                    if type(m.get('species')) is int and m['species'] in {9,154}
                    and (step['kind']=='teach_cut' or 15 in m.get('moves',[]))]
        if state['progress'].get('party_read_valid') is not True or len(candidates)!=1:
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'unique_current_cut_user_unverified'},step_id)
        intent={'kind':step['kind'],'species':candidates[0],'replace_move':45}
        if step['kind']=='use_cut':intent.update(map_id=step['map_id'],tree_x=step['tree'][0],tree_y=step['tree'][1],tileset_id=step.get('tileset_id',0))
        controller=CutController(intent);_FIELD_CONTROLLERS[step_id]=controller
    context=controller.context(read_visible_text(pyboy),state['progress'],location=loc,grid=grid,overworld_ready=grid is not None,battle_active=False)
    next_id=step_id
    if context.get('field_move_complete'):
        index=plan['steps'].index(step)+1
        next_id=plan['steps'][index]['id'] if index<len(plan['steps']) else 'complete'
    return context,next_id


def satisfied(step,progress):
    if 'event' in step:return progress['story_event_bits'].get(step['event']) is True
    if 'item' in step:return any(i['item']==step['item'] for i in progress.get('inventory') or [])
    if 'badge' in step:return bool((progress.get('badges_raw') or 0)&step['badge'])
    return False


def attack_pp(mon):
    from .team_strategy import effective_power
    return sum(pp&63 for move,pp in zip(mon.get('moves',[]),mon.get('pp',[])) if effective_power(move,mon.get('species'))>0)


def healthy(progress, *, require_full_pp=False):
    party=progress['party']
    if require_full_pp:
        from .team_strategy import reference,move_key
        for mon in party:
            moves,pp=mon.get('moves'),mon.get('pp')
            if (not isinstance(moves,(list,tuple)) or not isinstance(pp,(list,tuple))
                    or len(moves)!=4 or len(pp)!=4):return False
            for move,remaining in zip(moves,pp):
                if type(move) is not int or type(remaining) is not int:return False
                if move==0:
                    if remaining!=0:return False
                    continue
                key=move_key(move)
                base=reference()['moves'].get(key,{}).get('pp')
                if type(base) is not int or remaining!=base:return False
    return bool(party) and all(m['hp']==m['max_hp'] and not m.get('status',0) for m in party) and attack_pp(party[0])>=3


def coordinate_script_wait(state, step):
    """只在固定紅版嘎啦嘎啦座標等遊戲自己的腳本；絕不輸出按鍵。"""
    def review(reason):
        return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                'review_reason':reason,'route_step':step['id']}
    if (step.get('await_script_event') is not True or step.get('kind')!='move'
            or step.get('map_id')!=147 or step.get('target')!=[10,16]
            or step.get('event')!='beat_ghost_marowak'):
        return review('coordinate_script_intent_unverified')
    battle=state.get('battle_state',{});progress=state.get('progress',{})
    if (battle.get('kind')!='none' or battle.get('active') is not False
            or progress.get('party_read_valid') is not True
            or progress.get('story_event_bits',{}).get('beat_ghost_marowak') is not False
            or not any(i.get('item')==72 and type(i.get('quantity')) is int and i['quantity']>0
                       for i in progress.get('inventory') or [])):
        return review('coordinate_script_prerequisites_unverified')
    now=time.monotonic();record=_SCRIPT_WAITS.setdefault(step['id'],{'started':now,'calls':0})
    record['calls']+=1
    if record['calls']>25 or now-record['started']>60:
        return review('coordinate_script_wait_exhausted')
    return {'phase':'overworld','objective':'Wait.','available_actions':['wait'],
            'goal':step['id'],'route_step':step['id'],'source_coordinate_script_wait':True,
            'source_commit':'a53671100ec22e5394ff26ec028d0812a238dae2',
            'phase_source':'PokemonTower6F.asm:25-47；保留10,16，讓原生座標腳本啟動，不把到站當成戰勝。'}


def _via_target(plan,step,position):
    """只消費實際抵達的下一中繼點；暫停、戰鬥與熱載入不重設游標。"""
    via=step.get('via',[])
    if not via:return step.get('target',list(position))
    # 工程解除的resume_revision與blocked修正不是新旅程；幾何或job改變才另建進度。
    fields=('id','kind','map_id','target','via','next_map','terminal',
            'event','item','badge','await_script_event','face','require_full_pp')
    geometry=[{key:s[key] for key in fields if key in s} for s in plan['steps']]
    canonical=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)
    job=plan.get('training_job')
    scope=('training_job',canonical(job)) if job not in (None,'',{},[]) else ('unscoped_route',)
    key=(scope,canonical(geometry),step['id'])
    following=_VIA_PROGRESS.get(key,0)
    while following<len(via) and tuple(via[following])==position:
        following+=1
    _VIA_PROGRESS[key]=following
    return via[following] if following<len(via) else step.get('target',list(position))


def waypoint(pyboy,state,plan,step_id,previous):
    global _LAST_ATTEMPT
    steps=plan['steps'];ids=[s['id'] for s in steps]
    if len(ids)!=len(set(ids)):raise ValueError('路線ID重複')
    index=len(steps) if step_id=='complete' else ids.index(step_id) if step_id in ids else 0
    loc=state['location'];progress=state['progress'];mid=loc['map_id'];x,y=loc['x'],loc['y']
    # 先承認已完成的轉場，再判斷補血繞路，避免「進中心→繞路出門→再進中心」循環。
    while index<len(steps) and (satisfied(steps[index],progress) or steps[index].get('next_map')==mid):index+=1
    current=steps[index] if index<len(steps) else {}
    lead=progress['party'][0] if progress.get('party') else None
    needs_heal=lead is not None and (lead['hp']*3<=lead['max_hp']*2 or lead.get('status',0) or attack_pp(lead)<3)
    detour=None
    if not plan.get('_detour'):
        if mid in {58,68,64} and current.get('map_id')!=mid:
            detour={'id':'detour-center','map_id':mid,'target':[3,3] if not healthy(progress) else [3,8],'kind':'heal' if not healthy(progress) else 'move','face':'up','terminal':True}
        elif mid==14 and needs_heal:detour={'id':'detour-return-pewter','map_id':14,'target':[-1,9],'kind':'move','terminal':True}
        elif mid==2 and current.get('map_id')==14:detour={'id':'detour-city','map_id':2,'target':[13,25] if not healthy(progress) else [40,17],'kind':'move','terminal':True}
        elif mid==35 and needs_heal:detour={'id':'detour-bridge-center','map_id':35,'target':[10,36],'kind':'move','terminal':True}
        elif mid==36 and needs_heal:detour={'id':'detour-route25-center','map_id':36,'target':[-1,8],'kind':'move','terminal':True}
        elif mid==35 and current.get('map_id')==36:detour={'id':'detour-return-route25','map_id':35,'target':[20,8],'kind':'move','terminal':True}
        elif mid==3 and current.get('map_id') in {35,36,88}:
            detour={'id':'detour-cerulean-center','map_id':3,'target':[19,17] if not healthy(progress) else [20,-1],'kind':'move','terminal':True}
    if detour:
        context,_=waypoint(pyboy,state,{'steps':[detour],'blocked':plan.get('blocked',{}),'_detour':True},detour['id'],previous)
        return context,current.get('id',step_id)
    # 只由實際執行的行程記錄失敗邊；外層主線不能清掉補血繞路的嘗試。
    if pyboy is not None and _LAST_ATTEMPT:
        old=_LAST_ATTEMPT
        if (mid,x,y,current.get('id'))==old['key'] and previous and previous[-1]==old['direction']:
            old['misses']+=1
            if old['misses']>=3:
                dx,dy={'up':(0,-1),'down':(0,1),'left':(-1,0),'right':(1,0)}[old['direction']]
                _LEARNED_EDGES.setdefault(mid,set()).add(((x,y),(x+dx,y+dy)))
                _LAST_ATTEMPT=None
        else:_LAST_ATTEMPT=None
    while index<len(steps):
        step=steps[index]
        if satisfied(step,progress) or ('next_map' in step and mid==step['next_map']):index+=1;continue
        if mid!=step['map_id']:
            return {'phase':'campaign_review','review_reason':'unexpected_map','expected_map':step['map_id'],'route_step':step['id']},step['id']
        target=_via_target(plan,step,(x,y))
        target={'x':target[0],'y':target[1]}
        if 'await_script_event' in step and [x,y]==list(target.values()):
            return coordinate_script_wait(state,step),step['id']
        if step['kind']=='heal' and healthy(progress,require_full_pp=step.get('require_full_pp') is True):index+=1;continue
        if step['kind']=='move' and [x,y]==list(target.values()) and 'next_map' not in step:index+=1;continue
        if (step['kind'] in {'teach_cut','use_cut','gym_switches'} or 'mechanic' in step) and [x,y]==list(target.values()):
            return {'phase':'overworld','objective':'Wait.','available_actions':['wait'],'goal':'field_transaction_pending'},step['id']
        if [x,y]==list(target.values()) and step['kind'] in {'interact','heal'}:
            direction=step.get('face','up')
            return {'phase':'overworld','objective':'Confirm the current selection.' if previous and previous[-1]==direction else f'Move {direction.upper()}.',
                    'available_actions':['a','b'] if previous and previous[-1]==direction else ['up','down','left','right','wait'],
                    'goal':step['id'],'route_step':step['id'],'controller_interaction':True},step['id']
        grid=read_world_grid(pyboy,loc)
        blocked=[tuple(p) for p in plan.get('blocked',{}).get(str(mid),[])]
        from .observation import read_visible_text
        ready=campaign_transactions.ui_overworld_ready(read_visible_text(pyboy),grid) if pyboy is not None and grid else False
        npcs=(world_map.read_npc_obstacles(pyboy,grid,blocked,overworld_ready=True) if ready
              else world_map.read_npc_obstacles(pyboy,grid,blocked)) if grid else None
        if npcs:
            hidden=npcs.get('hidden_source_positions',[]) if npcs.get('toggle_source_calibrated') is True else []
            blocked=list((set(blocked)-set(map(tuple,hidden)))|set(npcs['positions']))
        cleared=[]
        if mid==3:
            if progress['story_event_bits'].get('got_ss_ticket'):cleared.append((27,12))
            if any(i['item']==228 for i in progress.get('inventory') or []):cleared.append((30,8))
        if mid==88 and progress['story_event_bits'].get('bill_said_use_cell_separator'):cleared.append((6,5))
        if mid==61:
            if progress['story_event_bits'].get('got_helix_fossil'):cleared.append((13,6))
            if progress['story_event_bits'].get('got_dome_fossil'):cleared.append((12,6))
        blocked=[p for p in blocked if p not in cleared]
        learned=_LEARNED_EDGES.get(mid,set())
        hint=world_direction(grid,loc,target,blocked,learned) if grid else None
        if not hint and abs(target['x']-x)+abs(target['y']-y)==1 and step.get('terminal') and ((x,y),(target['x'],target['y'])) not in learned:
            direction='up' if target['y']<y else 'down' if target['y']>y else 'left' if target['x']<x else 'right'
            hint={'direction':direction,'kind':'source_verified_terminal_step','path_length':1}
        if hint:
            if npcs:hint['npc_obstacles']=npcs
            if cleared:hint['cleared_story_objects']=cleared
            if learned:hint['observed_blocked_edges']=[list(edge) for edge in sorted(learned)]
            key=(mid,x,y,step['id'])
            if pyboy is not None and (_LAST_ATTEMPT is None or _LAST_ATTEMPT['key']!=key or _LAST_ATTEMPT['direction']!=hint['direction']):
                _LAST_ATTEMPT={'key':key,'direction':hint['direction'],'misses':0}
            return {'phase':'overworld','objective':f"Move {hint['direction'].upper()}.",'available_actions':['up','down','left','right','wait'],
                    'goal':step['id'],'route_step':step['id'],'world_path_hint':hint},step['id']
        return {'phase':'overworld','objective':'Wait.','available_actions':['wait','b'],'navigation_warning':'no_verified_path',
                'goal':step['id'],'route_step':step['id']},step['id']
    return {'phase':'campaign_review','review_reason':'route_extension_required','route_step':'complete'},'complete'
