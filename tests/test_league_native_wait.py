"""Real readonly getter, pure wait, SDK anchors and native text decoder.

Synthetic RAM/tiles/frame/progress only; no ROM, tick, keys or game instance.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import laya_pokemon
from laya_pokemon import observation
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
import pytest

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-route22-reviewed-adoption-20261028'


def source_for_test(path):
    p=Path(path).resolve()
    if p==STAGE/'test_league_native_wait.py':return STAGE/'league_native_wait.py'
    if p==ROOT/'tests/test_league_native_wait.py':return ROOT/'src/laya_pokemon/league_native_wait.py'
    raise RuntimeError('Only exact staged/formal test source paths are supported')


@pytest.fixture
def control():
    spec=importlib.util.spec_from_file_location('laya_pokemon._league_native_test',source_for_test(__file__))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m._test_spec=spec;return m


def native_text(first=None,*,window=False):
    cells=[[' ']*20 for _ in range(18)]
    if first is not None:cells[14][1:1+len(first)]=first
    reverse={}
    for code,char in sdk.POKEMON_TEXT_DECODING.items():
        if type(code) is int and 0<=code<=255:reverse.setdefault(char,code)
    class Tiles:
        def __getitem__(self,xy):x,y=xy;return reverse[cells[y][x]]
    game=SimpleNamespace(memory={0xFF40:0xB1 if window else 0x91},
        screen=SimpleNamespace(tilemap_position_list=[(0,0,0,0)]*144),
        tilemap_background=Tiles(),tilemap_window=Tiles())
    text=observation.read_visible_text(game)
    assert text['read_valid'] and text['alignment_verified'];return text


def dialogue_text(first,second='',arrow=True):
    contractions=("'d","'l","'s","'t","'v","'r","'m")
    cells=[[' ']*20 for _ in range(18)]
    for y,value in ((14,first),(16,second)):
        x=1
        while value:
            token=next((c for c in contractions if value.startswith(c)),value[0])
            cells[y][x]=token;x+=1;value=value[len(token):]
    if arrow:cells[16][18]='▼'
    reverse={}
    for code,char in sdk.POKEMON_TEXT_DECODING.items():
        if type(code) is int and 0<=code<=255:reverse.setdefault(char,code)
    class Tiles:
        def __getitem__(self,xy):x,y=xy;return reverse[cells[y][x]]
    game=SimpleNamespace(memory={0xFF40:0xB1},screen=SimpleNamespace(tilemap_position_list=[(0,0,0,0)]*144),tilemap_background=Tiles(),tilemap_window=Tiles())
    result=observation.read_visible_text(game);assert result['read_valid'];return result


class Memory:
    def __init__(self):self.values={};self.reads=[];self.hook=None
    def __getitem__(self,a):
        self.reads.append(a);v=self.values[a];return self.hook(a,v) if self.hook else v
    def __setitem__(self,*args):raise AssertionError('RAM writes forbidden')


class Game:
    def __init__(self):self.frame_count=1000;self.memory=Memory()
    def tick(self,*args,**kw):raise AssertionError('tick forbidden')
    def button(self,*args,**kw):raise AssertionError('keys forbidden')


class Session:
    def __init__(self,m,map_id=33):
        self.m=m;self.game=Game();self.now=0.;cfg=m.CONFIG[map_id]
        self.step=dict(id='native-'+str(map_id),kind='interact',map_id=map_id,target=deepcopy(cfg['target']),
            face=cfg['face'],event=cfg['event'],await_script_event=True)
        self.location=dict(map_id=map_id,x=cfg['target'][0],y=cfg['target'][1])
        self.values=dict(script=0,raw=0,battle_type=0,current=cfg['opponent'],trainer=10 if map_id==33 else 1,
            simulated=0,ignored=0,status5=0,badges=255)
        self.events={cfg['won']:False}
        if cfg['auto'] is not None:self.events[cfg['auto']]=False
        if map_id==33:self.events.update({0x520:False,0x521:True,0x527:True})
        self.progress=dict(profile='gen1-wrapper-ram-progress-v1-unvalidated',initialization_candidate=True,
            party_read_valid=True,party_count=6,story_event_bits={cfg['event']:False},
            party=[dict(species=s,species_name=n,level=48,exp=100000,hp=100,max_hp=200,status=0,
                moves=[33,34,58,109],pp=[20,15,10,10]) for s,n in
                ((19,'LAPRAS'),(132,'SNORLAX'),(102,'EEVEE'),(154,'VENUSAUR'),(35,'FEAROW'),(7,'NIDOKING'))])
        self.text=native_text();self.state=None;self.signal=None
        self.progress.update(player_name_raw='KEVIN',money=1000,inventory=[dict(item=18,quantity=9)])
    def sync(self):
        cfg=self.m.CONFIG[self.location['map_id']];v=self.values;memory=self.game.memory.values
        memory.update({0xD35E:self.location['map_id'],0xD362:self.location['x'],0xD361:self.location['y'],
            0xD057:v['raw'],0xD05A:v['battle_type'],0xD059:v['current'],0xD05D:v['trainer'],
            0xD356:v['badges'],0xD730:v['status5'],0xCD38:v['simulated'],0xCD6B:v['ignored'],cfg['script']:v['script']})
        reverse={char:code for code,char in sdk.POKEMON_TEXT_DECODING.items() if type(code) is int and 0<=code<=255 and type(char) is str and len(char)==1}
        for address,name in ((0xD158,'KEVIN'),(0xD34A,'BLUE')):
            memory.update({address+i:(reverse[name[i]] if i<len(name) else 0x50) for i in range(11)})
        for i in self.events:memory[0xD747+i//8]=0
        for i,on in self.events.items():memory[0xD747+i//8]|=int(on)<<(i%8)
        self.progress['story_event_bits'][cfg['event']]=self.events[cfg['won']]
        raw=v['raw'];self.state=dict(frame=self.game.frame_count,location=deepcopy(self.location),
            progress=deepcopy(self.progress),battle_state=dict(raw=raw,active=raw in (1,2),
                kind={0:'none',1:'wild',2:'trainer'}.get(raw,'unknown'),observation_frame=self.game.frame_count))
    def call(self,*,fresh=True,previous=(),state_mutate=None):
        if self.state is not None and fresh:self.game.frame_count+=40;self.now+=.1
        self.sync()
        if state_mutate:state_mutate(self.state)
        before=deepcopy((self.state,self.step,self.text,self.game.memory.values))
        out=self.m.context(self.game,self.state,self.step,self.text,previous,now=self.now)
        assert before==(self.state,self.step,self.text,self.game.memory.values)
        if out is not None:
            assert out['available_actions']==(['a','wait'] if out.get('source_native_dialogue') else ['wait']) and not out.get('field_move_complete')
            assert not out.get('battle_medicine_complete') and not out.get('victory_confirmed')
        return out


def test_exact_stage_and_formal_paths(control):
    assert source_for_test(__file__).name=='league_native_wait.py'
    assert source_for_test(ROOT/'tests/test_league_native_wait.py')==ROOT/'src/laya_pokemon/league_native_wait.py'
    with pytest.raises(RuntimeError):source_for_test(STAGE/'not_allowed.py')


BEFORE=[('BLUE: What?','KEVIN! What a'),('KEVIN! What a','surprise to see'),
    ('surprise to see','you here!'),("So you're going to",'POKéMON LEAGUE?'),
    ('You collected all','the BADGEs too?'),('the BADGEs too?',"That's cool!"),
    ("Then I'll whip you",'KEVIN as a'),('KEVIN as a','warm up for'),
    ('warm up for','POKéMON LEAGUE!'),('Come on!','')]
AFTER=[('That loosened me',"up! I'm ready for"),("up! I'm ready for",'POKéMON LEAGUE!'),
    ('KEVIN, you need','more practice!'),('But hey, you know',"that! I'm out of"),
    ("that! I'm out of",'here. Smell ya!')]


def complete_dialogue(s,pages):
    previous=[]
    for i,(a,b) in enumerate(pages):
        final=i==len(pages)-1;s.text=dialogue_text(a,b,arrow=not final)
        r=s.call(previous=previous)
        if final:
            assert r['available_actions']==['wait']
            assert s.call(fresh=False,previous=previous)['available_actions']==['wait']
            r=s.call(previous=['wait'])
        assert r['available_actions']==['a','wait'] and r['source_native_dialogue']
        assert r['native_dialogue_page']==i
        previous=['a']


def test_route22_native_second_rival_lifecycle_no_false_completion(control):
    s=Session(control);assert s.call()['native_wait_reason']=='rival_native_approach_or_intro'
    s.values.update(script=4,status5=1);assert s.call()['available_actions']==['wait']
    s.values['status5']=0;complete_dialogue(s,BEFORE)
    s.values.update(raw=2,script=5);s.text=native_text()
    assert s.call(previous=['a'])['native_wait_reason']=='blank_trainer_intro'
    s.text=native_text('BLUE wants',window=True);assert s.call() is None
    s.text=native_text();assert s.call() is None
    s.values.update(raw=0,script=5);s.events[0x526]=True
    complete_dialogue(s,AFTER)
    s.values.update(script=6,status5=1);s.text=native_text()
    assert s.call(previous=['a'])['native_wait_reason']=='rival_native_exit'
    s.values.update(script=7,status5=0);s.events.update({0x521:False,0x527:False})
    assert s.call() is None and s.game.memory.reads.count(0xD60A)>=18


@pytest.mark.parametrize('map_id',[245,246,247])
def test_elite_six_native_up_stops_at_five_then_legacy_navigation(control,map_id):
    s=Session(control,map_id);s.location.update(x=5,y=11)
    assert s.call()['native_wait_reason']=='elite_native_entry_pending'
    cfg=control.CONFIG[map_id];s.events[cfg['auto']]=True;s.values['script']=3
    for y in range(11,4,-1):
        s.location['y']=y;s.values['simulated']=y-5
        assert s.call()['native_wait_reason']=='elite_native_six_up'
    s.values.update(script=0,simulated=0)
    assert s.location==dict(map_id=map_id,x=5,y=5) and s.call() is None


def test_lance_full_source_rle_ends_six_eleven_not_six_two(control):
    s=Session(control,113);s.location.update(x=24,y=16)
    assert s.call()['native_wait_reason']=='lance_native_entry_pending'
    x,y=24,16;s.values.update(script=3,simulated=37,ignored=255)
    remaining=37
    for dx,dy,n in ((0,-1,12),(-1,0,12),(0,1,7),(-1,0,6)):
        for _ in range(n):
            x+=dx;y+=dy;remaining-=1;s.location.update(x=x,y=y);s.values['simulated']=remaining
            assert s.call()['native_wait_reason']=='lance_native_rle'
    assert (x,y)==(6,11)
    s.values.update(script=0,ignored=0);assert s.call() is None


def test_champion_native_entry_and_real_trainer_intro_handoff(control):
    s=Session(control,120);s.values.update(script=1,ignored=255)
    for x,y in ((3,7),(3,6),(4,6),(4,5),(4,4),(4,3)):
        s.location.update(x=x,y=y);assert s.call()['native_wait_reason']=='champion_native_entry';s.values['script']=2
    s.values.update(raw=2,script=3,ignored=0)
    assert s.call()['native_wait_reason']=='blank_trainer_intro'
    s.text=native_text('BLUE sent',window=True);assert s.call() is None


@pytest.mark.parametrize('map_id',[33,245,246,247,113,120])
def test_complete_intro_text_hands_to_existing_battle_and_never_presses_a(control,map_id):
    s=Session(control,map_id);s.values.update(raw=2,script=5 if map_id==33 else 3 if map_id==120 else 2)
    assert s.call()['native_wait_reason']=='blank_trainer_intro'
    s.text=native_text('Trainer wants',window=True);assert s.call() is None
    assert control._WAITS[s.step['id']].intro_handoff
    if map_id==246:assert s.values['current']==233


@pytest.mark.parametrize('bad',['wild','lost','wrong_location','wrong_opponent','trainer_early_set','badges','second_flag','wants_flag','first_flag','unknown_script','unknown_text','foreign_frame','foreign_text_frame','fnt'])
def test_bad_native_facts_stop_with_bounded_review(control,bad):
    s=Session(control);mutate=None
    if bad=='wild':s.values['raw']=1
    elif bad=='lost':s.values['raw']=255
    elif bad=='wrong_location':s.location['x']=28
    elif bad=='wrong_opponent':s.values.update(raw=2,current=247)
    elif bad=='trainer_early_set':s.values.update(raw=2,trainer=9)
    elif bad=='badges':s.values['badges']=127
    elif bad=='second_flag':s.events[0x521]=False
    elif bad=='wants_flag':s.events[0x527]=False
    elif bad=='first_flag':s.events[0x520]=True
    elif bad=='unknown_script':s.values['script']=8
    elif bad=='unknown_text':s.text['read_error']='other_error'
    elif bad=='foreign_frame':mutate=lambda state:state['battle_state'].update(observation_frame=0)
    elif bad=='foreign_text_frame':s.text['observation_frame']=0
    else:s.progress['party'][0]['hp']=0
    r=s.call(state_mutate=mutate);assert r['phase']=='campaign_review'
    assert control._WAITS[s.step['id']].error is not None


@pytest.mark.parametrize('bad',['frame','byte','sdk','double_read'])
def test_true_getter_rejects_bad_frame_byte_sdk_and_changing_ram(control,bad):
    s=Session(control);s.sync();constants=sdk
    if bad=='frame':s.game.frame_count+=1
    elif bad=='byte':s.game.memory.values[0xCD38]=False
    elif bad=='sdk':constants=SimpleNamespace(**{k:v for k,v in vars(sdk).items() if k.isupper()});constants.STATUS_FLAGS3_ADDRESS=0
    else:
        counts={}
        def hook(a,v):
            counts[a]=counts.get(a,0)+1
            return v+1 if a==0xD60A and counts[a]>1 else v
        s.game.memory.hook=hook
    r=control.read_native_signal(s.game,observation_frame=s.state['frame'],constants=constants)
    assert r['read_valid'] is False and r['values'] is None


def test_exact_known_blank_alignment_wait_is_not_generic_error_suppression(control):
    s=Session(control);s.values.update(raw=2,script=5)
    s.text.update(read_valid=False,alignment_verified=False,read_error='visible_tile_alignment_incomplete')
    assert s.call()['native_wait_reason']=='blank_trainer_intro'
    s.text['read_error']='anything_else';assert s.call()['phase']=='campaign_review'


@pytest.mark.parametrize('limit',['time','calls'])
def test_duplicate_same_frame_still_consumes_lifetime_budget(control,limit):
    s=Session(control);s.call()
    if limit=='time':s.now=60.01;r=s.call(fresh=False)
    else:
        for _ in range(59):assert s.call(fresh=False)['available_actions']==['wait']
        r=s.call(fresh=False)
    assert r['review_reason'].endswith('budget_exhausted')


def test_hot_reload_keeps_same_instance_owner_clock_counter_and_sticky_error(control):
    s=Session(control);s.call();c=control._WAITS[s.step['id']];before=deepcopy((c.signature,c.started,c.last_now,c.calls))
    control._test_spec.loader.exec_module(control)
    assert s.call(fresh=False)['available_actions']==['wait'] and control._WAITS[s.step['id']] is c
    assert (c.signature,c.started,c.last_now,c.calls)==(*before[:3],before[3]+1)
    s.step['face']='up';assert s.call()['phase']=='campaign_review'
    s.step['face']='left';assert s.call()['phase']=='campaign_review'


def test_other_active_owner_is_never_rebound(control):
    s=Session(control);s.call();other=Session(control,245)
    assert other.call()['review_reason'].endswith('active_step_owner_changed')
    assert len(control._WAITS)==1


def test_same_frame_packet_conflict_and_regressing_clock_fail_closed(control):
    s=Session(control);s.call();s.values['status5']=1
    assert s.call(fresh=False)['review_reason'].endswith('same_frame_packet_conflict')
    other=Session(control);other.step['id']='different';control._WAITS.clear();other.call();other.now=-1
    assert other.call()['review_reason'].endswith('clock_regressed_or_invalid')


def test_long_existing_battle_does_not_reset_or_exhaust_native_wait_budget(control):
    s=Session(control);s.call();c=control._WAITS[s.step['id']]
    s.values.update(raw=2,script=5);s.text=native_text('BLUE wants',window=True)
    assert s.call() is None;before=(c.started,c.calls,c.elapsed)
    s.now+=600
    for _ in range(70):assert s.call() is None
    assert (c.started,c.calls,c.elapsed)==before
    s.values.update(raw=0,script=6,status5=1);s.events[0x526]=True;s.text=native_text()
    assert s.call()['native_wait_reason']=='rival_native_exit'
    assert c.started==before[0] and c.calls==before[1]+1 and c.elapsed==before[2]


@pytest.mark.parametrize('bad',['unknown_script','wrong_phase_events'])
def test_raw2_cannot_enable_unknown_script_or_wrong_second_rival_flags(control,bad):
    s=Session(control);s.values.update(raw=2,script=8 if bad=='unknown_script' else 5)
    if bad=='wrong_phase_events':s.events[0x521]=False
    assert s.call()['phase']=='campaign_review'


def test_after_intro_handoff_existing_battle_owns_native_contractions_and_animations(control):
    s=Session(control);s.values.update(raw=2,script=5);s.text=native_text('BLUE wants',window=True)
    assert s.call() is None
    s.text['cells'][14][5]="'s"
    assert s.call() is None
    s.text.update(read_valid=False,alignment_verified=False,read_error='later_battle_animation')
    assert s.call() is None  # Not an error-clear or success claim: route still invokes battle's guards.


def test_unhashable_step_id_is_bounded_review(control):
    s=Session(control);s.step['id']=[]
    assert s.call()['review_reason'].endswith('fixed_step_required')


def before_session(control):
    s=Session(control);s.values['script']=4;return s


def test_empty_native_window_and_exact_prefix_wait_instead_of_legacy_handoff(control):
    s=before_session(control);s.text=native_text(window=True)
    assert s.call()['available_actions']==['wait']
    s.text=dialogue_text('BL',arrow=False);assert s.call()['native_wait_reason']=='native_dialogue_printing'
    s.text=dialogue_text('BLUE: What?','KEVIN! What a',arrow=False)
    assert s.call()['native_wait_reason']=='native_dialogue_prompt_blink'
    s.text=dialogue_text('BLUE: What?','KEVIN! What a')
    assert s.call()['available_actions']==['a','wait']
    assert s.call(fresh=False)['available_actions']==['wait']


@pytest.mark.parametrize('bad',['wrong_name','missing_char','upper_pollution','wrong_contraction_position'])
def test_source_page_exact_positions_and_names_are_required(control,bad):
    s=before_session(control)
    s.text=dialogue_text('GARY: What?' if bad=='wrong_name' else 'BLUE: What?','KEVIN! What a')
    if bad=='missing_char':s.text['cells'][14][2]=' '
    elif bad=='upper_pollution':s.text['cells'][3][3]='A'
    elif bad=='wrong_contraction_position':s.text['cells'][14][2]="'s"
    if bad!='wrong_name':
        rows=[''.join(r) for r in s.text['cells']];idx=[i for i,r in enumerate(rows) if __import__('re').search(r'[A-Za-z0-9]{2,}',r)][:12]
        s.text.update(lines=[rows[i].rstrip() for i in idx],line_rows=idx)
    assert s.call()['phase']=='campaign_review'


def test_native_page_cannot_advance_without_actual_previous_a(control):
    s=before_session(control);s.text=dialogue_text(*BEFORE[0]);s.call()
    s.text=dialogue_text(*BEFORE[1]);assert s.call(previous=['wait'])['review_reason'].endswith('native_page_changed_without_actual_a')


def test_actual_a_waits_on_old_page_and_tolerates_native_arrow_blink(control):
    s=before_session(control);s.text=dialogue_text(*BEFORE[0]);s.call()
    s.text=dialogue_text(*BEFORE[0],arrow=False)
    assert s.call(previous=['a'])['native_wait_reason']=='native_dialogue_after_actual_a'
    s.text=dialogue_text(*BEFORE[1]);assert s.call(previous=['wait'])['native_dialogue_page']==1


def offer_before_done(s):
    for i,pair in enumerate(BEFORE[:-1]):
        s.text=dialogue_text(*pair);assert s.call(previous=['a'] if i else [])['available_actions'][0]=='a'
    s.text=dialogue_text(*BEFORE[-1],arrow=False)
    assert s.call(previous=['a'])['available_actions']==['wait']
    assert s.call(previous=['wait'])['available_actions'][0]=='a'


def test_final_done_never_invents_arrow_and_needs_actual_a_before_battle(control):
    s=before_session(control);offer_before_done(s)
    s.values.update(raw=2,script=5);s.text=native_text()
    assert s.call(previous=['wait'])['review_reason'].endswith('native_dialogue_advanced_without_actual_a')


def test_final_done_arrow_is_rejected_and_partial_resets_stability(control):
    s=before_session(control)
    for i,pair in enumerate(BEFORE[:-1]):
        s.text=dialogue_text(*pair);s.call(previous=['a'] if i else [])
    s.text=dialogue_text(*BEFORE[-1],arrow=True)
    assert s.call(previous=['a'])['review_reason'].endswith('native_done_unexpected_arrow')


def test_source_names_are_really_double_read_and_unterminated_name_fails(control):
    s=before_session(control);s.text=dialogue_text(*BEFORE[0]);assert s.call()['available_actions'][0]=='a'
    assert s.game.memory.reads.count(0xD158)==2 and s.game.memory.reads.count(0xD34A)==2
    other=before_session(control);control._WAITS.clear()
    other.game.memory.hook=lambda a,v:0x80 if 0xD34A<=a<0xD34A+11 else v
    assert other.call()['phase']=='campaign_review'


def test_after_done_needs_actual_a_before_native_exit(control):
    s=Session(control);s.values['script']=5;s.events[0x526]=True
    complete_dialogue(s,AFTER)
    s.values.update(script=6,status5=1);s.text=native_text()
    assert s.call(previous=['wait'])['review_reason'].endswith('native_dialogue_advanced_without_actual_a')
