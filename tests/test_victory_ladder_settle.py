"""Real source NPC/toggle/progress readers, artificial memory; no saved outputs."""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
gate = importlib.import_module('laya_pokemon.victory_ladder_settle')
shared = importlib.import_module('laya_pokemon.owned_field_medicine')
recovery = importlib.import_module('laya_pokemon.league_recovery')
nav = importlib.import_module('laya_pokemon.victory_road_navigation')
world = importlib.import_module('laya_pokemon.world_map')
later = importlib.import_module('laya_pokemon.victory_later_boulders_bridge')
for module, filename in ((gate,'victory_ladder_settle.py'),(shared,'owned_field_medicine.py'),
    (recovery,'league_recovery.py'),(nav,'victory_road_navigation.py'),(world,'world_map.py'),
    (later,'victory_later_boulders_bridge.py')):
    assert Path(module.__file__).resolve() == (ROOT/'src/laya_pokemon'/filename).resolve()
bh = importlib.import_module('test_victory_later_boulders')
hh = importlib.import_module('test_overworld_hyper')
for module, filename in ((bh,'test_victory_later_boulders.py'),(hh,'test_overworld_hyper.py')):
    assert Path(module.__file__).resolve() == (ROOT/'tests'/filename).resolve()

from laya_pokemon.progress import read_progress


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(gate, '_WAITS', {})
    monkeypatch.setattr(gate, '_ERROR', None)
    for name, value in (('_SESSIONS', {}), ('_ERRORS', {}), ('_REGISTRY_ERROR', None)):
        monkeypatch.setattr(shared, name, value)


def plan():
    steps = recovery.expected_steps()
    return dict(mode='league_campaign', training_job=recovery.JOB, lead_species=35, steps=steps,
        reviewed_fnt_recovery=dict(kind=recovery.KIND, source_frame=32809,
            source_location=dict(map_id=198, x=6, y=1), fainted_species=7,
            steps_sha256=recovery.digest(steps), review_sha256=recovery.SOURCE_REVIEW_SHA256,
            state_sha256=recovery.SOURCE_STATE_SHA256))


class Session:
    def __init__(self, sid='league28-fnt-recovery-07'):
        self.sid = sid; self.plan = plan(); self.game = hh.Game(); self.game.frame_count = 10833
        p = bh.progress()
        for mon in p['party']: mon.update(hp=mon['max_hp'], status=0)
        next(mon for mon in p['party'] if mon['species'] == 7)['hp'] = 0
        self.game.game_wrapper = SimpleNamespace(party=p['party'], inventory=p['inventory'], money=p['money'])
        self.prepare(loaded=False, same=True)

    def prepare(self, *, loaded=False, same=False, frames=40, joy=0, movement=0, flags5=0):
        if not same: self.game.frame_count += frames
        mid, source, landing, old_count, new_count = gate.PAIRS[self.sid]
        floor = mid if loaded else 194 if mid == 198 else 198
        key = '3f_hole' if floor == 198 else '2f_switch2'
        self.game.memory.update(bh.Memory(key).values)
        loc = dict(map_id=mid, x=(landing if loaded else source)[0], y=(landing if loaded else source)[1])
        self.game.memory.update({0xD35E: mid, 0xD362: loc['x'], 0xD361: loc['y'], 0xD356: 255,
            sdk.PARTY_COUNT_ADDRESS: 6, sdk.PLAYER_MONEY_ADDRESS: 0x05,
            sdk.PLAYER_MONEY_ADDRESS+1: 0x43, sdk.PLAYER_MONEY_ADDRESS+2: 0x21,
            0xCD6B: joy, 0xD736: movement, 0xD730: flags5, 0xFF40: 0x91})
        enc = {v: k for k, v in sdk.POKEMON_TEXT_DECODING.items() if type(k) is int and 0 <= k <= 255}
        for i, ch in enumerate('KEVIN'): self.game.memory[sdk.PLAYER_NAME_ADDRESS+i] = enc[ch]
        self.game.memory[sdk.PLAYER_NAME_ADDRESS+5] = 0x50
        self.game.cells = hh.blank(); self.text = hh.read_visible_text(self.game)
        self.grid = bh.grid(key, self.game.frame_count, (loc['x'], loc['y']), self.game.memory)
        self.grid.update(source=nav.GRID_SOURCE, verified_location=[mid, loc['x'], loc['y']])
        self.state = dict(frame=self.game.frame_count, phase='overworld', location=loc,
            progress=read_progress(self.game, sdk), battle_state=dict(raw=0, active=False,
                kind='none', observation_frame=self.game.frame_count))
        self.npcs = nav.read_victory_road_npcs(self.game, self.grid, loc, world_map_module=world,
                                            boulder_module=later.boulder, overworld_ready=True)
        return self

    def kwargs(self):
        return dict(shared=shared, recovery=recovery, native_owner=self.game, game_id='game29',
                    peer_owners={name: set() for name in shared.PEER_NAMES})

    def call(self, sid=None, **kwargs):
        args = self.kwargs(); args.update(kwargs)
        before = deepcopy((dict(self.game.memory), self.state, self.plan, self.text, self.grid, self.npcs))
        out = gate.context(self.game, self.state, self.plan, self.sid if sid is None else sid,
                           self.text, self.grid, self.npcs, **args)
        assert before == (dict(self.game.memory), self.state, self.plan, self.text, self.grid, self.npcs)
        return out


def review(out):
    assert out[0]['phase'] == 'campaign_review', out
    assert out[0]['available_actions'] == ['wait']


@pytest.mark.parametrize('sid', tuple(gate.PAIRS))
def test_fixed_ladder_mixed_header_waits_then_true_loaded_idle_npcs_release_original_navigation(sid):
    s = Session(sid); assert s.npcs['read_valid'] is False
    out, cursor = s.call(); assert cursor == sid and out['available_actions'] == ['wait']
    assert 'field_move_complete' not in out and 'field_move_kind' not in out
    s.prepare(loaded=True, joy=255, movement=1, flags5=0x26)
    assert s.npcs['read_valid'] is True
    assert s.call()[0]['available_actions'] == ['wait']
    s.prepare(loaded=True, flags5=0x24)
    assert s.call()[0]['available_actions'] == ['wait']  # DISABLE_JOYPAD is still native.
    s.prepare(loaded=True)
    assert s.call() is None and gate._active() == set()
    assert gate._WAITS[sid]['done'] is True
    assert s.call() is None
    assert nav.blocked_for_move([], s.npcs, location=s.state['location'], target={'x':26,'y':8}) is not None


def test_same_frame_reentry_and_reload_preserve_native_budget_without_restarting_record():
    s = Session(); s.call(); r = gate._WAITS[s.sid]
    for _ in range(30): assert s.call()[0]['available_actions'] == ['wait']
    assert r['waits'] == 1
    gate.__spec__.loader.exec_module(gate)
    assert gate._WAITS[s.sid] is r
    s.prepare(loaded=True); assert s.call() is None


@pytest.mark.parametrize('bad', ['native','game','job','steps','peer','peer_unknown','missing_peer',
    'status','new_fnt','battle','unknown_review','cursor','frame','coordinates','fullprogress'])
def test_preflight_is_before_memory_or_ui_and_rejects_changed_authority(bad):
    s = Session(); s.call(); args = s.kwargs(); sid = s.sid
    if bad == 'native': args['native_owner'] = object()
    if bad == 'game': args['game_id'] = 'other'
    if bad == 'job': s.plan['training_job'] = 'other'
    if bad == 'steps': s.plan['steps'][7]['target'][0] -= 1
    if bad == 'peer': args['peer_owners']['victory_strength'] = {'foreign'}
    if bad == 'peer_unknown': args['peer_owners']['victory_strength'] = None
    if bad == 'missing_peer': args['peer_owners'].pop('tm24_teaching')
    if bad == 'status': s.state['progress']['party'][0]['status'] = 8
    if bad == 'new_fnt': s.state['progress']['party'][0]['hp'] = 0
    if bad == 'battle': s.state['battle_state']['raw'] = 1
    if bad == 'unknown_review': s.state.update(phase='campaign_review',review_reason='unknown')
    if bad == 'cursor': sid = 'league28-fnt-recovery-08'
    if bad == 'frame': s.state['frame'] -= 1
    if bad == 'coordinates': s.state['location']['x'] -= 1
    if bad == 'fullprogress': s.state['progress']['money'] -= 1
    reads = len(s.game.memory.reads)
    review(gate.preflight(s.game,s.state,s.plan,sid,**args))
    assert len(s.game.memory.reads) == reads and gate._active()
    review(s.call())


@pytest.mark.parametrize('address,value', [(0xD4E1,9),(0xD367,0),(0xCD38,1),(0xCD6B,0xFC),
    (0xCFC5,1),(0xD736,2),(0xD730,1),(0xD733,4),(0xD72D,16),(0xD057,1)])
def test_other_native_motion_does_not_borrow_the_buffer(address,value):
    s = Session(); s.call(); s.game.memory[address] = value
    review(s.call())


@pytest.mark.parametrize('bad',['frame_budget','wait_budget','reversed','sameframe','return_to_old_xy',
    'fresh_resource','fake_npcs','unknown_text','window'])
def test_active_budget_resources_closedworld_and_real_npc_receipts_remain_required(bad):
    s = Session(); s.call()
    if bad == 'frame_budget': s.prepare(frames=241)
    elif bad == 'wait_budget':
        for _ in range(7): s.prepare(frames=1); s.call()
        s.prepare(frames=1)
    elif bad == 'reversed': s.game.frame_count-=1; s.state['frame']-=1
    elif bad == 'sameframe': s.npcs['read_error']='changed'
    elif bad == 'return_to_old_xy':
        s.prepare(loaded=True,joy=255,movement=1,flags5=0x26);s.call();s.prepare()
    elif bad == 'fresh_resource': s.game.game_wrapper.party[0]['pp'][0]-=1
    elif bad == 'fake_npcs':
        s.prepare(loaded=True);s.npcs=dict(read_valid=True,fixed_floor=198,observation_frame=s.state['frame'])
    elif bad == 'unknown_text': s.text['read_error']='unknown'
    elif bad == 'window': s.text['window_visible']=True
    review(s.call())


def test_initial_named_review_can_reenter_same_frame_and_unknown_navigation_remains_review():
    s = Session();s.state.update(phase='campaign_review',review_reason='victory_navigation_native_header_or_objects_unverified')
    assert s.call()[0]['available_actions']==['wait']
    assert s.call()[0]['available_actions']==['wait'] and gate._WAITS[s.sid]['waits']==1


def test_unknown_floor_or_step_is_not_accepted_without_active_buffer():
    s = Session()
    assert not gate.applies('ordinary',s.state['location'])
    assert not gate.applies(None,s.state['location'])
    assert not gate.applies(s.sid,dict(map_id=194,x=25,y=14))
    assert gate._active()==set()
