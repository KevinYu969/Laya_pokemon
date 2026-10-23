"""純假觀測；不建立模擬器、不讀ROM/state，不執行按鍵。"""
from copy import deepcopy
import ast
import json
from pathlib import Path
import pytest

from laya_pokemon.snorlax_escape import SnorlaxEscapeController,INTENT,PLAYER_PROFILE
from tests import test_snorlax_switch as sw

LOCATION=deepcopy(sw.LOCATION);WILD=deepcopy(sw.WILD)
NONE={'raw':0,'active':False,'kind':'none','opponent_species':None,'wild_opponent_species':None}


def readers(p,frame,active=2,player_speed=60,enemy_speed=30):
    m=p['party'][active]
    def stats(mon,speed,types):
        return {**deepcopy(mon),'internal_id':mon['species'],'speed':speed,'attack':60,
                'defense':60,'special':60,'types':types,'dvs':[0,0],
                'pp_remaining':[v&63 for v in mon['pp']],'pp_ups':[v>>6 for v in mon['pp']]}
    e=sw.enemy(frame)
    e['enemy']=stats({**e['enemy'],'moves':[29,133,156,0],'pp':[15,20,10,0]},enemy_speed,[0,0])
    player={'profile':PLAYER_PROFILE,'source_commit':sw.SOURCE_COMMIT,'read_valid':True,
            'unknown_reason':None,'observation_frame':frame,'location':deepcopy(LOCATION),
            'battle_kind':'wild','active_party_index':active,'player':stats(m,player_speed,[0,2])}
    return e,player


def baseline(cursor=(9,16),active=2,player_speed=60,enemy_speed=30):
    p=sw.progress();e,player=readers(p,100,active,player_speed,enemy_speed)
    return {'frame':100,'now':10.,'text':sw.command(p,active,cursor),'progress':p,
            'location':deepcopy(LOCATION),'battle_state':deepcopy(WILD),
            'enemy_snapshot':e,'player_snapshot':player}


def success(p,active=2,prompt=True):
    return sw.dialogue(p,active,'Got away safely!',prompt=prompt)


def grid(frame):
    return {'observation_frame':frame,'verified_location':[23,10,61],
            'screen_cells_verified':12,'visible_verified_cells':[[x,y] for y in range(60,63) for x in range(8,12)]}


class Session:
    def __init__(self,b=None,**limits):
        self.b=baseline() if b is None else b;self.p=deepcopy(self.b['progress'])
        self.c=SnorlaxEscapeController(self.b,deepcopy(INTENT),**limits)
        self.frame=100;self.now=10.;self.active=self.c.active_index
    def call(self,t=None,world=False,**kw):
        self.frame+=16;self.now+=.1
        frame=kw.pop('frame',self.frame);e,player=readers(self.p,frame,self.active)
        return self.c.context(sw.text_at(window=False) if t is None else t,self.p,
            location=kw.pop('location',deepcopy(LOCATION)),battle_state=kw.pop('battle_state',deepcopy(NONE if world else WILD)),
            enemy_snapshot=kw.pop('enemy_snapshot',None if world else e),
            player_snapshot=kw.pop('player_snapshot',None if world else player),frame=frame,
            now=kw.pop('now',self.now),overworld_ready=kw.pop('overworld_ready',world),
            grid=kw.pop('grid',grid(frame) if world else None),**kw)
    def run(self):
        cursor=next((x,y) for y,r in enumerate(self.b['text']['cells']) for x,c in enumerate(r) if c=='▶')
        while cursor!=(15,16):
            action='down' if cursor[1]==14 else 'right'
            assert self.call(sw.command(self.p,self.active,cursor))['available_actions']==[action,'wait']
            cursor=(cursor[0],16) if action=='down' else (15,16)
        assert self.call(sw.command(self.p,self.active,cursor))['available_actions']==['a','wait']
    def acknowledge(self):
        self.run();assert self.call(success(self.p,self.active))['available_actions']==['a','wait']


@pytest.mark.parametrize('cursor',[(9,14),(15,14),(9,16),(15,16)])
def test_normal_run_success_two_world_frames_preserves_every_party_and_item(cursor):
    s=Session(baseline(cursor));before=deepcopy(s.p);s.acknowledge()
    r=s.call(world=True);assert not r['escape_complete'] and r['available_actions']==['wait']
    r=s.call(world=True)
    assert r['escape_complete'] and r['captured'] is False and r['acknowledge_loses_route12_snorlax']
    assert s.p==before and r['party_order_and_inventory_preserved']
    assert r['completion_observation_frame']>r['first_world_observation_frame']


@pytest.mark.parametrize('case',['missing_ack','false_ack','bool_as_int','no_run_profile','slow','unknown_speed',
                               'bool_speed','wrong_active','hp_divergence','wrong_move','enemy_unknown','player_frame','bad_money','faint'])
def test_constructor_never_approves_unknown_irreversible_or_unproven_speed(case):
    b=baseline();intent=deepcopy(INTENT)
    if case=='missing_ack':intent.pop('acknowledge_loses_route12_snorlax')
    elif case=='false_ack':intent['acknowledge_loses_route12_snorlax']=False
    elif case=='bool_as_int':intent['map_id']=True
    elif case=='no_run_profile':b['player_snapshot']['profile']='fake'
    elif case=='slow':b['player_snapshot']['player']['speed']=29
    elif case=='unknown_speed':b['enemy_snapshot']['enemy'].pop('speed')
    elif case=='bool_speed':b['player_snapshot']['player']['speed']=True
    elif case=='wrong_active':b['player_snapshot']['active_party_index']=3
    elif case=='hp_divergence':b['player_snapshot']['player']['hp']-=1
    elif case=='wrong_move':b['player_snapshot']['player']['moves'][0]=1
    elif case=='enemy_unknown':b['enemy_snapshot']['read_valid']=False
    elif case=='player_frame':b['player_snapshot']['observation_frame']-=1
    elif case=='bad_money':b['progress']['money']=True
    else:b['progress']['party'][0]['hp']=0
    with pytest.raises(ValueError):SnorlaxEscapeController(b,intent)


def test_equal_actual_speeds_are_accepted_without_claiming_generic_random_escape():
    assert SnorlaxEscapeController(baseline(player_speed=30,enemy_speed=30),deepcopy(INTENT)).stage=='command'


def test_cursor_and_run_a_pending_survive_blank_and_old_ui_without_resend():
    s=Session();old=sw.command(s.p,s.active,(9,16))
    assert s.call(old)['available_actions']==['right','wait']
    assert s.call()['available_actions']==['wait']
    assert s.call(old)['available_actions']==['wait']
    run=sw.command(s.p,s.active,(15,16));assert s.call(run)['available_actions']==['a','wait']
    for t in [run,sw.text_at(),run]:assert s.call(t)['available_actions']==['wait']
    assert s.c.run_requested and not s.c.prompt_confirmed


def test_success_prompt_partial_never_confirms_and_only_full_page_is_acknowledged_once():
    s=Session();s.run();full=success(s.p,s.active)
    for t in [success(s.p,s.active,prompt=False),sw.text_at(),full]:
        r=s.call(t)
    assert r['available_actions']==['a','wait'] and s.c.prompt_confirmed
    for t in [full,sw.text_at(),full]:assert s.call(t)['available_actions']==['wait']


@pytest.mark.parametrize('text', ["Can't escape!",'SNORLAX was caught!','Delete','Got away safely!X'])
def test_failure_or_unknown_ui_reviews_instead_of_confirming(text):
    s=Session();s.run();r=s.call(sw.dialogue(s.p,s.active,text,prompt=True))
    assert r['phase']=='campaign_review' and r['available_actions']==['wait'] and not s.c.prompt_confirmed


@pytest.mark.parametrize('case',['party_hp','party_pp','party_exp','party_order','party_status','inventory','money',
                               'location','battle','enemy_speed','player_speed','player_hp','text_proof'])
def test_every_source_guard_is_rechecked_before_success_a(case):
    s=Session();s.run();kw={};t=success(s.p,s.active)
    if case=='party_hp':s.p['party'][0]['hp']-=1
    elif case=='party_pp':s.p['party'][0]['pp'][0]-=1
    elif case=='party_exp':s.p['party'][0]['exp']+=1
    elif case=='party_order':s.p['party'].reverse()
    elif case=='party_status':s.p['party'][0]['status']=64
    elif case=='inventory':s.p['inventory'][1]['quantity']-=1
    elif case=='money':s.p['money']-=1
    elif case=='location':kw['location']={**LOCATION,'x':11}
    elif case=='battle':kw['battle_state']=deepcopy(NONE)
    elif case=='text_proof':t['read_valid']=False
    else:
        e,p=readers(s.p,s.frame+16,s.active)
        if case=='enemy_speed':e['enemy']['speed']=61
        elif case=='player_speed':p['player']['speed']=29
        else:p['player']['hp']-=1
        kw.update(enemy_snapshot=e,player_snapshot=p)
    r=s.call(t,**kw)
    assert r['phase']=='campaign_review' and r['available_actions']==['wait'] and not s.c.prompt_confirmed


@pytest.mark.parametrize('case',['before_run','extra_text','wrong_error','cross_frame','world_ready'])
def test_native_blank_is_only_a_bounded_wait_after_run_and_never_decoder_upgrade(case):
    s=Session()
    if case!='before_run':s.run()
    t=sw.text_at();t.update(read_valid=False,alignment_verified=False,read_error='visible_tile_alignment_incomplete')
    kw={}
    if case=='extra_text':sw.put(t,0,0,'Delete')
    elif case=='wrong_error':t['read_error']='unknown'
    elif case=='cross_frame':t['observation_frame']=s.frame
    elif case=='world_ready':kw['overworld_ready']=True
    r=s.call(t,**kw)
    assert r['phase']=='campaign_review' and r['available_actions']==['wait'] and t['read_valid'] is False


@pytest.mark.parametrize('offset',[0,-1])
def test_native_wait_records_packet_frame_before_any_later_prompt(offset):
    s=Session();s.run();t=sw.text_at();t.update(read_valid=False,alignment_verified=False,read_error='visible_tile_alignment_incomplete')
    r=s.call(t);assert r['available_actions']==['wait'] and not r['controller_menu_verified']
    r=s.call(success(s.p,s.active),frame=s.frame+offset)
    assert r['phase']=='campaign_review' and r['available_actions']==['wait']


def test_same_frame_identical_prompt_never_resends_a_and_conflict_reviews():
    s=Session();s.run();t=success(s.p,s.active);assert s.call(t)['available_actions']==['a','wait'];f=s.frame
    assert s.call(t,frame=f)['available_actions']==['wait']
    bad=deepcopy(t);sw.put(bad,0,0,'X')
    assert s.call(bad,frame=f)['phase']=='campaign_review'


@pytest.mark.parametrize('case',['grid_missing','grid_frame','grid_count','grid_duplicates','no_player','window','letters','battle_wild',
                               'reader_still_wild','party_changed','ready_not_bool'])
def test_world_completion_requires_two_original_clean_coherent_proofs(case):
    s=Session();s.acknowledge();frame=s.frame+16;g=grid(frame);t=sw.text_at(window=False);kw={}
    if case=='grid_missing':g=None
    elif case=='grid_frame':g['observation_frame']-=1
    elif case=='grid_count':g['screen_cells_verified']=True
    elif case=='grid_duplicates':g['visible_verified_cells'][-1]=g['visible_verified_cells'][0]
    elif case=='no_player':g['visible_verified_cells'][6]=[40,40]
    elif case=='window':t['window_visible']=True
    elif case=='letters':sw.put(t,0,0,'YES')
    elif case=='battle_wild':kw['battle_state']=deepcopy(WILD)
    elif case=='reader_still_wild':kw['player_snapshot']=readers(s.p,frame,s.active)[1]
    elif case=='party_changed':s.p['party'][0]['exp']+=1
    else:kw['overworld_ready']=1
    r=s.call(t,world=True,grid=g,**kw)
    assert r['phase']=='campaign_review' and r['available_actions']==['wait'] and not s.c.completion


def test_world_same_frame_cannot_count_twice_and_interrupted_proof_resets():
    s=Session();s.acknowledge();assert not s.call(world=True)['escape_complete'];f=s.frame
    assert not s.call(world=True,frame=f)['escape_complete']
    assert not s.call(battle_state=deepcopy(NONE),enemy_snapshot=None,player_snapshot=None)['escape_complete']
    assert not s.call(world=True)['escape_complete']
    assert s.call(world=True)['escape_complete']


@pytest.mark.parametrize('limit', ['time','calls','waits'])
def test_native_wait_and_normal_ui_share_original_locked_budget(limit):
    s=Session(max_calls=1 if limit=='calls' else 120,max_waits=1 if limit=='waits' else 60)
    if limit=='time':r=s.call(now=70.01)
    else:s.call();r=s.call()
    assert r['phase']=='campaign_review' and r['available_actions']==['wait']


@pytest.mark.parametrize('limits',[{'max_calls':121},{'max_calls':True},{'max_waits':61},{'max_seconds':61}])
def test_limits_cannot_expand(limits):
    with pytest.raises(ValueError):Session(**limits)


def test_intent_mutation_or_unexpected_success_before_run_never_confirms():
    s=Session();s.c.intent['acknowledge_loses_route12_snorlax']=1
    assert s.call()['phase']=='campaign_review'
    s=Session();assert s.call(success(s.p,s.active))['phase']=='campaign_review'


def test_completion_is_detached_wait_receipt_never_capture_and_no_runtime_io():
    s=Session();before=deepcopy(s.b);s.acknowledge();s.call(world=True);r=s.call(world=True)
    r['captured']=True
    done=s.c.context(None,None,location=None,battle_state=None,enemy_snapshot=None,player_snapshot=None,frame=-1,now=-1)
    assert done['escape_complete'] and done['captured'] is False and done['available_actions']==['wait'] and s.b==before
    source=(Path(__file__).parents[1]/'src/laya_pokemon/snorlax_escape.py').read_text(encoding='utf-8')
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):assert node.func.id not in {'open','eval','exec','__import__'}
        if isinstance(node,ast.Attribute):assert node.attr not in {'memory','tick','button','load_state','save_state'}


def test_public_fixture_fixed_source_speed_prompt_and_irreversible_route_proofs():
    f=json.loads((Path(__file__).parent/'data/snorlax-escape-source-fixture.json').read_text(encoding='utf-8'))
    assert f['source_commit']==sw.SOURCE_COMMIT and f['live_ui_calibrated'] is False
    excerpts='\n'.join(e['text'] for s in f['sources'] for e in s['excerpts'])
    for token in ['TryRunningFromBattle:', 'Got away safely!', 'EVENT_BEAT_ROUTE12_SNORLAX','StringCmp::']:
        assert token in excerpts
