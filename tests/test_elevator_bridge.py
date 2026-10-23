"""B1F/B4F正常電梯意圖綁定；不執行模擬器。"""
from types import SimpleNamespace

import pytest

from laya_pokemon import campaign_transactions as tx
from tests.test_rocket_elevator import text_at,grid,movement,animation,location,inventory


@pytest.fixture(autouse=True)
def registry():
    for r in (tx._CONTROLLERS,tx._BINDINGS,tx._TURNS,tx._COMPLETED,tx._BATTLE_PAUSES):r.clear()
    yield
    for r in (tx._CONTROLLERS,tx._BINDINGS,tx._TURNS,tx._COMPLETED,tx._BATTLE_PAUSES):r.clear()


def setup(monkeypatch,floor='B1F'):
    emulator=SimpleNamespace(frame_count=100,memory={0xC109:4})
    state={'phase':'unclassified','frame':100,'location':location(),
           'battle_state':{'kind':'none','active':False},'progress':inventory()}
    plan={'steps':[{'id':'lift','kind':'interact','mechanic':'rocket_elevator',
                    'target_floor':floor,'map_id':203,'target':[1,2]},{'id':'after'}]}
    monkeypatch.setattr(tx.rocket_movement,'read_rocket_movement',lambda *a,**k:movement(state['frame']))
    monkeypatch.setattr(tx.rocket_elevator,'read_elevator_animation',lambda *a,**k:animation(state['frame']))
    return emulator,state,plan


@pytest.mark.parametrize('floor',['B1F','B4F'])
def test_explicit_floor_is_bound_before_normal_panel_interaction(monkeypatch,floor):
    args=setup(monkeypatch,floor)
    result,next_id=tx.context(*args,'lift',text_at(),grid(args[1]['location'],100))
    assert result['available_actions']==['a','wait'] and next_id=='lift'
    assert tx._CONTROLLERS['lift'].target_floor==floor
    args[2]['steps'][0]['target_floor']='B4F' if floor=='B1F' else 'B1F'
    result,_=tx.context(*args,'lift',text_at(),{})
    assert result['review_reason']=='transaction_intent_changed'


def test_unknown_floor_cannot_start(monkeypatch):
    args=setup(monkeypatch,'B2F')
    result,_=tx.context(*args,'lift',text_at(),{})
    assert result['review_reason']=='elevator_explicit_intent_unverified' and not tx._CONTROLLERS


def test_normal_guard_battle_suspends_field_keys_without_discarding_transaction(monkeypatch):
    args=setup(monkeypatch)
    tx.context(*args,'lift',text_at(),grid(args[1]['location'],100))
    controller=tx._CONTROLLERS['lift']
    args[1].update(phase='battle_menu',battle_state={'kind':'trainer','active':True},location=location((25,18),199))
    assert tx.context(*args,'lift',text_at(),None) is None
    assert tx._CONTROLLERS['lift'] is controller and 'lift' not in tx._COMPLETED
    args[1]['battle_state']['active']=False
    result,_=tx.context(*args,'lift',text_at(),None)
    assert result['review_reason']=='transaction_nonbattle_signal_conflict'


def test_nonbattle_ram_with_battle_phase_cannot_start_panel(monkeypatch):
    args=setup(monkeypatch);args[1]['phase']='battle_menu'
    result,_=tx.context(*args,'lift',text_at(),grid(args[1]['location'],100))
    assert result['review_reason']=='transaction_nonbattle_phase_conflict'
    assert not tx._CONTROLLERS


def test_long_confirmed_battle_does_not_consume_field_timer_or_replace_controller(monkeypatch):
    args=setup(monkeypatch);clock=[0.]
    monkeypatch.setattr(tx.time,'monotonic',lambda:clock[0])
    tx.context(*args,'lift',text_at(),grid(args[1]['location'],100))
    controller=tx._CONTROLLERS['lift'];controller.stage='exit_up_requested'
    original_calls,original_waits=controller.calls,controller.waits
    args[1].update(phase='battle_menu',frame=200,battle_state={'kind':'trainer','active':True},location=location((25,18),199))
    clock[0]=5.
    assert tx.context(*args,'lift',text_at(),None) is None
    assert (controller.calls,controller.waits)==(original_calls,original_waits)
    args[1].update(phase='unclassified',frame=300,battle_state={'kind':'none','active':False})
    clock[0]=66.
    result,next_id=tx.context(*args,'lift',text_at(),grid(args[1]['location'],300))
    assert tx._CONTROLLERS['lift'] is controller and controller.started_at==61.
    assert result['field_move_complete'] and next_id=='after'


@pytest.mark.parametrize('floor',['B1F','B4F'])
def test_only_verified_completion_uses_distinct_floor_checkpoint_name(monkeypatch,floor):
    class Complete:
        stage='initial';error=None
        def __init__(self,intent):self.target_floor=intent['target_floor']
        def context(self,*a,**k):return {'rocket_elevator_complete':True,'available_actions':['wait']}
    args=setup(monkeypatch,floor)
    monkeypatch.setattr(tx.rocket_elevator,'RocketElevatorController',Complete)
    result,next_id=tx.context(*args,'lift',text_at(),{})
    assert result['field_move_complete'] and result['field_move_kind']=='rocket-elevator-'+floor
    assert next_id=='after'
