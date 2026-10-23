"""正常月石交易與持續行程的邊界；純觀測、不操作遊戲。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from laya_pokemon import campaign_transactions as tx
from tests.test_battle import text_at
from tests.test_moon_stone import progress


@pytest.fixture(autouse=True)
def isolated_registry():
    for registry in (tx._CONTROLLERS,tx._BINDINGS,tx._TURNS,tx._COMPLETED):registry.clear()
    yield
    for registry in (tx._CONTROLLERS,tx._BINDINGS,tx._TURNS,tx._COMPLETED):registry.clear()


def inputs():
    emulator=SimpleNamespace(memory={0xC109:4})
    state={'phase':'unclassified','location':{'map_id':200,'x':1,'y':12},
           'battle_state':{'kind':'none','active':False},'progress':progress()}
    step={'id':'evolve','kind':'interact','mechanic':'moon_stone','map_id':200,'target':[1,12]}
    return emulator,state,{'steps':[step,{'id':'after'}]}


def test_only_explicit_normal_stone_intent_can_open_start():
    args=inputs();before=deepcopy(args[1])
    result,next_id=tx.context(*args,'evolve',text_at(),{})
    assert result['phase']=='moon_stone_menu' and result['available_actions']==['start','wait']
    assert next_id=='evolve' and args[1]==before
    assert not result.get('field_move_complete')


@pytest.mark.parametrize('change',['location','intent','step'])
def test_started_evolution_cannot_escape_to_navigation_or_other_transaction(change):
    args=inputs();tx.context(*args,'evolve',text_at(),{})
    step_id='evolve'
    if change=='location':args[1]['location']['x']=2
    elif change=='intent':args[2]['steps'][0]['mechanic']='gift_eevee'
    else:step_id='after'
    result,next_id=tx.context(*args,step_id,text_at(),{})
    assert result['phase']=='campaign_review' and result['available_actions']==['wait']
    assert not result.get('field_move_complete')


def test_incomplete_real_decoder_never_opens_stone_menu():
    args=inputs();text={**text_at(),'profile':tx.observation.PROFILE,'read_valid':False,
                       'alignment_verified':False,'window_visible':True}
    result,_=tx.context(*args,'evolve',text,{})
    assert result['phase']=='campaign_review' and result['available_actions']==['wait']
    assert not tx._CONTROLLERS


def test_only_controller_complete_records_stone_transaction(monkeypatch):
    class Fake:
        stage='initial';error=None
        def __init__(self,*args):pass
        def context(self,*args,**kwargs):
            assert isinstance(kwargs['now'],float)
            return {'phase':'moon_stone_complete','moon_stone_complete':True,'available_actions':['wait']}
    monkeypatch.setattr(tx.moon_stone,'MoonStoneController',Fake)
    result,next_id=tx.context(*inputs(),'evolve',text_at(),{})
    assert result['field_move_complete'] is True and result['field_move_kind']=='moon_stone'
    assert next_id=='after'
