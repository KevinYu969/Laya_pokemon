"""接線只在明示訓練的普通移動步驟；交易與原戰鬥審查優先。"""
from copy import deepcopy
import pytest
from laya_pokemon import campaign_route as route


def test_move_training_routes_same_state_and_preserves_step(monkeypatch):
    state={'phase':'battle_menu'};emulator=object()
    plan={'mode':'league_campaign','training_shared_experience':True,
          'steps':[{'id':'grass','kind':'move','map_id':26,'target':[18,8]}]}
    hint={'phase':'battle_menu','objective':'Move RIGHT.','available_actions':['right']}
    def training(p,s,q):
        assert p is emulator and s is state and q is plan
        return hint
    monkeypatch.setattr(route.balanced_training,'shared_experience_battle_context',training)
    assert route.field_context(emulator,state,plan,'grass')==(hint,'grass')


@pytest.mark.parametrize('change',[
    {'training_shared_experience':False},{'training_shared_experience':1},
    {'mode':'balanced_training'},{'steps':[]},
    {'steps':[{'id':'grass','kind':'heal'}]},
])
def test_unrelated_routes_do_not_dispatch_shared_training(monkeypatch,change):
    plan={'mode':'league_campaign','training_shared_experience':True,
          'steps':[{'id':'grass','kind':'move','map_id':26,'target':[18,8]}]}
    plan.update(deepcopy(change))
    def forbidden(*args):raise AssertionError('unexpected training dispatch')
    monkeypatch.setattr(route.balanced_training,'shared_experience_battle_context',forbidden)
    assert route.field_context(None,{},plan,'grass') is None


def test_shared_none_keeps_original_battle_result(monkeypatch):
    state={'phase':'strategy_review','review_reason':'capture_unknown'}
    before=deepcopy(state)
    plan={'mode':'league_campaign','training_shared_experience':True,
          'steps':[{'id':'grass','kind':'move'}]}
    assert route.field_context(None,state,plan,'grass') is None
    assert state==before


def test_owned_transaction_has_priority(monkeypatch):
    plan={'mode':'league_campaign','training_shared_experience':True,
          'steps':[{'id':'grass','kind':'move'}]}
    monkeypatch.setattr(route.capture_transaction,'applies',lambda *args:True)
    monkeypatch.setattr(route.capture_transaction,'context',lambda *args:('capture','grass'))
    monkeypatch.setattr(route.capture_closing_gate,'eligible',lambda *args:False)
    monkeypatch.setattr(route,'read_world_grid',lambda *args:None)
    monkeypatch.setattr('laya_pokemon.observation.read_visible_text',lambda *args:{})
    def forbidden(*args):raise AssertionError('training displaced capture transaction')
    monkeypatch.setattr(route.balanced_training,'shared_experience_battle_context',forbidden)
    assert route.field_context(None,{'location':{}},plan,'grass')==('capture','grass')
