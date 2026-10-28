"""Portable synthetic source memory, real progress/NPC/toggle readers, no game."""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
gate=importlib.import_module('laya_pokemon.victory_east_entry')
shared=importlib.import_module('laya_pokemon.owned_field_medicine')
nav=importlib.import_module('laya_pokemon.victory_road_navigation')
world=importlib.import_module('laya_pokemon.world_map')
later=importlib.import_module('laya_pokemon.victory_later_boulders_bridge')
for module,filename in ((gate,'victory_east_entry.py'),(shared,'owned_field_medicine.py'),
    (nav,'victory_road_navigation.py'),(world,'world_map.py'),(later,'victory_later_boulders_bridge.py')):
    assert Path(module.__file__).resolve()==(ROOT/'src/laya_pokemon'/filename).resolve()
bh=importlib.import_module('test_victory_later_boulders')
hh=importlib.import_module('test_overworld_hyper')
for module,filename in ((bh,'test_victory_later_boulders.py'),(hh,'test_overworld_hyper.py')):
    assert Path(module.__file__).resolve()==(ROOT/'tests'/filename).resolve()
from laya_pokemon.progress import read_progress


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(gate,'_WAITS',{});monkeypatch.setattr(gate,'_ERROR',None)
    for name,value in (('_SESSIONS',{}),('_ERRORS',{}),('_REGISTRY_ERROR',None)):
        monkeypatch.setattr(shared,name,value)


def plan(prefix='arbitrary-outing-1'):
    return dict(mode='league_campaign',source_commit=gate.COMMIT,training_job=gate.JOB,
        training_supervisor=gate.SUPERVISOR,lead_species=154,steps=[
            dict(id=prefix+'-source',kind='move',map_id=34,target=[14,31],next_map=194,terminal=True),
            dict(id=prefix+'-landing',kind='move',map_id=194,target=[29,7]),
            dict(id=prefix+'-next',kind='move',map_id=194,target=[28,7])])


class Session:
    def __init__(self,prefix='arbitrary-outing-1',source_cursor=False):
        self.game=hh.Game();self.game.frame_count=23433;self.plan=plan(prefix)
        self.sid=self.plan['steps'][0 if source_cursor else 1]['id']
        p=bh.progress()
        for m in p['party']:m.update(hp=m['max_hp'],status=0)
        self.game.game_wrapper=SimpleNamespace(party=p['party'],inventory=p['inventory'],money=p['money'])
        self.prepare(same=True)

    def prepare(self,*,loaded=False,same=False,frames=40,joy=0,motion=4,flags5=0,no_grid=False):
        if not same:self.game.frame_count+=frames
        self.game.memory.update(bh.Memory('2f_switch2').values)
        loc=deepcopy(gate.LANDING if loaded else gate.SOURCE)
        header=gate.NEW_HEADER if loaded else gate.OLD_HEADER
        self.game.memory.update(dict(zip((0xD367,0xD368,0xD369,0xD4E1),header)))
        self.game.memory.update({0xD35E:194,0xD362:loc['x'],0xD361:loc['y'],0xD356:255,
            sdk.PARTY_COUNT_ADDRESS:6,sdk.PLAYER_MONEY_ADDRESS:0x05,
            sdk.PLAYER_MONEY_ADDRESS+1:0x43,sdk.PLAYER_MONEY_ADDRESS+2:0x21,
            0xCD6B:joy,0xD736:motion,0xD730:flags5,0xFF40:0x91})
        enc={v:k for k,v in sdk.POKEMON_TEXT_DECODING.items() if type(k) is int and 0<=k<=255}
        for i,ch in enumerate('KEVIN'):self.game.memory[sdk.PLAYER_NAME_ADDRESS+i]=enc[ch]
        self.game.memory[sdk.PLAYER_NAME_ADDRESS+5]=0x50
        self.game.cells=hh.blank();self.text=hh.read_visible_text(self.game)
        f=self.game.frame_count
        if loaded:
            self.grid=bh.grid('2f_switch2',f,(29,7),self.game.memory);self.grid['source']=nav.GRID_SOURCE
        else:
            self.grid=dict(source=nav.GRID_SOURCE,tileset_id=23,observation_frame=f,
                verified_location=[194,14,31],screen_cells_verified=12,
                visible_verified_cells=[[x,31] for x in range(12)],
                tiles=[[1]*20 for _ in range(144)],walkable=[[1]*20 for _ in range(144)])
        if no_grid:self.grid=None
        self.state=dict(frame=f,phase='overworld',location=loc,progress=read_progress(self.game,sdk),
            battle_state=dict(raw=0,active=False,kind='none',observation_frame=f))
        self.npcs=self.read_npcs()
        return self

    def read_npcs(self):
        from laya_pokemon.campaign_transactions import verified_blank_transaction_world
        return nav.read_victory_road_npcs(self.game,self.grid,self.state['location'],
            world_map_module=world,boulder_module=later.boulder,
            overworld_ready=verified_blank_transaction_world(self.text,self.grid))

    def kwargs(self):
        return dict(shared=shared,native_owner=self.game,game_id='game29',
                    peer_owners={k:set() for k in shared.PEER_NAMES})

    def call(self,**kwargs):
        args=self.kwargs();args.update(kwargs)
        before=deepcopy((dict(self.game.memory),self.plan,self.state,self.text,self.grid,self.npcs))
        out=gate.context(self.game,self.state,self.plan,self.sid,self.text,self.grid,self.npcs,**args)
        assert before==(dict(self.game.memory),self.plan,self.state,self.text,self.grid,self.npcs)
        return out


def review(out):
    assert out[0]['phase']=='campaign_review',out
    assert out[0]['available_actions']==['wait']


@pytest.mark.parametrize('source_cursor',[False,True])
@pytest.mark.parametrize('motion',[0,4])
def test_source_semantics_wait_native_load_then_true_idle_npcs_release_original_nav(source_cursor,motion):
    s=Session(source_cursor=source_cursor);owner=s.sid
    assert s.npcs['read_error']=='frame_or_grid_unverified'
    out,cur=s.call();assert cur==owner and out['available_actions']==['wait']
    assert 'field_move_complete' not in out and 'field_move_kind' not in out
    s.prepare(loaded=True,joy=255,motion=5,flags5=0x26,no_grid=True)
    assert s.call()[0]['available_actions']==['wait']
    s.sid=s.plan['steps'][1]['id']  # genuine next_map resolution cannot bypass the active buffer
    s.prepare(loaded=True,flags5=0x24);assert s.call()[1]==owner
    s.prepare(loaded=True,motion=motion)
    assert s.call() is None and gate._active()==set()
    assert gate._WAITS[s.plan['steps'][1]['id']]['done'] is True


def test_unique_future_outing_ids_reuse_semantics_without_resetting_old_history():
    first=Session('first');first.call();first.prepare(loaded=True);assert first.call() is None
    record=gate._WAITS[first.plan['steps'][1]['id']]
    second=Session('future-generated-094');second.call();second.prepare(loaded=True);assert second.call() is None
    assert len(gate._WAITS)==2 and gate._WAITS[first.plan['steps'][1]['id']] is record


def test_same_frame_and_reload_preserve_baseline_native_and_wait_budget():
    s=Session();s.call();r=gate._WAITS[s.plan['steps'][1]['id']]
    for _ in range(20):assert s.call()[0]['available_actions']==['wait']
    assert r['waits']==1
    gate.__spec__.loader.exec_module(gate)
    assert gate._WAITS[s.plan['steps'][1]['id']] is r
    s.prepare(loaded=True);assert s.call() is None


@pytest.mark.parametrize('bad',['job','mode','supervisor','commit','source_target','nextmap','source_kind',
    'terminal','landing_target','landing_kind','extra_mechanic','float','duplicate_id','nonadjacent'])
def test_semantic_scope_never_expands_to_other_training_or_warps(bad):
    s=Session();p=s.plan;a,b=p['steps'][:2]
    if bad=='job':p['training_job']='other'
    if bad=='mode':p['mode']='other'
    if bad=='supervisor':p['training_supervisor']='other'
    if bad=='commit':p['source_commit']='other'
    if bad=='source_target':a['target']=[14,32]
    if bad=='nextmap':a['next_map']=198
    if bad=='source_kind':a['kind']='interact'
    if bad=='terminal':a.pop('terminal')
    if bad=='landing_target':b['target']=[29,8]
    if bad=='landing_kind':b['kind']='interact'
    if bad=='extra_mechanic':a['mechanic']='unknown'
    if bad=='float':b['target'][0]=29.0
    if bad=='duplicate_id':b['id']=a['id']
    if bad=='nonadjacent':p['steps'].insert(1,dict(id='between',kind='move',map_id=34,target=[14,32]))
    assert not gate.applies(p,s.sid,s.state['location']) and gate._active()==set()


@pytest.mark.parametrize('bad',['native','game','peer','peer_unknown','missing_peer','party_status','party_fnt',
    'resource','cursor','changed_plan','coordinates','phase','review','battle','frame'])
def test_active_preflight_fail_closed_before_any_memory_or_ui_read(bad):
    s=Session();s.call();args=s.kwargs()
    if bad=='native':args['native_owner']=object()
    if bad=='game':args['game_id']='other'
    if bad=='peer':args['peer_owners']['tm24_teaching']={'foreign'}
    if bad=='peer_unknown':args['peer_owners']['tm24_teaching']=None
    if bad=='missing_peer':args['peer_owners'].pop('tm24_teaching')
    if bad=='party_status':s.state['progress']['party'][0]['status']=8
    if bad=='party_fnt':s.state['progress']['party'][0]['hp']=0
    if bad=='resource':s.state['progress']['party'][0]['exp']+=1
    if bad=='cursor':s.sid='unknown'
    if bad=='changed_plan':s.plan['lead_species']=35
    if bad=='coordinates':s.state['location']['x']+=1
    if bad=='phase':s.state['phase']='battle_menu'
    if bad=='review':s.state.update(phase='campaign_review',review_reason='unknown')
    if bad=='battle':s.state['battle_state']['raw']=1
    if bad=='frame':s.state['frame']+=1
    count=len(s.game.memory.reads)
    out=gate.preflight(s.game,s.state,s.plan,s.sid,**args)
    review(out);assert len(s.game.memory.reads)==count
    assert out[1]==s.plan['steps'][1]['id'] and gate._active()


@pytest.mark.parametrize('address,value',[(0xD367,0),(0xD368,71),(0xD4E1,6),(0xCD38,1),
    (0xCD6B,0xFC),(0xCFC5,1),(0xD736,2),(0xD736,8),(0xD730,1),(0xD733,4),(0xD72D,16),(0xD057,1)])
def test_unknown_header_or_native_bits_never_borrow_wait_buffer(address,value):
    s=Session();s.call();s.game.memory[address]=value
    review(s.call())


@pytest.mark.parametrize('bad',['frames','waits','reverse','sameframe','resource_getter','fake_npcs',
    'unknown_text','window','source_return'])
def test_finite_real_budget_and_complete_fresh_source_receipts_remain_required(bad):
    s=Session();s.call()
    if bad=='frames':s.prepare(frames=241)
    if bad=='waits':
        for _ in range(7):s.prepare(frames=1);s.call()
        s.prepare(frames=1)
    if bad=='reverse':s.game.frame_count-=1;s.state['frame']-=1
    if bad=='sameframe':s.npcs['read_error']='changed'
    if bad=='resource_getter':s.game.game_wrapper.party[0]['pp'][0]-=1
    if bad=='fake_npcs':s.prepare(loaded=True);s.npcs=dict(read_valid=True,fixed_floor=194,observation_frame=s.state['frame'])
    if bad=='unknown_text':s.text['read_error']='unknown'
    if bad=='window':s.text['window_visible']=True
    if bad=='source_return':s.prepare(loaded=True,joy=255,motion=5,flags5=0x26,no_grid=True);s.call();s.prepare()
    review(s.call())


def test_named_initial_grid_review_is_only_a_wait_and_sameframe_idempotent():
    s=Session();s.state.update(phase='campaign_review',review_reason='victory_navigation_frame_or_grid_unverified')
    assert s.call()[0]['available_actions']==['wait']
    assert s.call()[0]['available_actions']==['wait']
    assert gate._WAITS[s.plan['steps'][1]['id']]['waits']==1


def test_invalid_error_registry_returns_review_without_typeerror(monkeypatch):
    s=Session();monkeypatch.setattr(gate,'_ERROR',123)
    review(s.call());assert gate._ERROR=='registry_unverified'
