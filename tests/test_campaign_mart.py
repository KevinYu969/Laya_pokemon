"""購物橋接只傳遞正常Laya子目標；fake memory禁止寫入。"""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from laya_pokemon import campaign_transactions as tx
from laya_pokemon.mart_purchase import INTENT
from tests.test_mart_purchase import progress, text_at, main

class Memory:
    facing=8
    def __getitem__(self,address):
        assert address==0xC109
        return self.facing
    def __setitem__(self,*args):
        raise AssertionError('No memory mutation')

@pytest.fixture(autouse=True)
def clean():
    for x in (tx._CONTROLLERS,tx._BINDINGS,tx._TURNS,tx._COMPLETED):x.clear()
    yield
    for x in (tx._CONTROLLERS,tx._BINDINGS,tx._TURNS,tx._COMPLETED):x.clear()

def setup():
    game=SimpleNamespace(memory=Memory())
    state={'phase':'unclassified','frame':1,'location':{'map_id':150,'x':2,'y':5},
           'battle_state':{'raw':0,'active':False,'kind':'none'},'progress':progress()}
    step={'id':'buy','kind':'interact','mechanic':'lavender_great_balls','map_id':150,
          'target':[2,5],'purchase_intent':deepcopy(INTENT)}
    return game,state,{'steps':[step,{'id':'after'}]}

def call(args,text=None,grid=None):
    return tx.context(*args,'buy',text if text is not None else text_at(window=False),{} if grid is None else grid)

@pytest.mark.parametrize('change',[lambda s:s['purchase_intent'].update(quantity=19),
    lambda s:s['purchase_intent'].update(unit_price=True),lambda s:s.update(target=[3,5]),
    lambda s:s.pop('purchase_intent')])
def test_fixed_purchase_intent_required(change):
    a=setup();change(a[2]['steps'][0])
    assert call(a)[0]['review_reason']=='mart_explicit_purchase_intent_unverified'
    assert not tx._CONTROLLERS

def test_arrival_and_turn_must_be_verified_before_talking():
    a=setup();a[1]['location']['x']=3
    assert call(a) is None
    a[1]['location']['x']=2;a[0].memory.facing=4
    assert call(a,main())[0]['review_reason']=='mart_turn_requires_verified_overworld'
    result,_=call(a)
    assert result['available_actions']==['left','wait']
    assert not tx._CONTROLLERS


@pytest.mark.parametrize('bad',[{'cells':[[' ']*20 for _ in range(18)]},
    text_at((1,0,'YES'),window=False),text_at((1,0,'NO'),window=False)])
def test_turn_rejects_legacy_proof_and_unknown_upper_text(bad):
    a=setup();a[0].memory.facing=4
    assert call(a,bad)[0]['review_reason']=='mart_turn_requires_verified_overworld'
    assert not tx._CONTROLLERS

def test_one_controller_preserves_purchase_baseline_and_never_executes_inputs():
    a=setup();before=deepcopy(a[1]);result,next_id=call(a)
    assert result['available_actions']==['a','wait'] and next_id=='buy'
    c=tx._CONTROLLERS['buy'];baseline=deepcopy(c.inventory_before)
    a[1]['frame']=2
    result,_=call(a,main())
    assert result['available_actions']==['a','wait']
    assert tx._CONTROLLERS['buy'] is c and c.inventory_before==baseline
    a[1]['frame']=1
    assert a[1]==before

def test_started_purchase_cannot_change_quantity_or_location():
    a=setup();call(a);a[2]['steps'][0]['purchase_intent']['quantity']=21
    assert call(a)[0]['review_reason']=='mart_explicit_purchase_intent_unverified'
    a[2]['steps'][0]['purchase_intent']=deepcopy(INTENT);a[1]['location']['x']=3
    assert call(a)[0]['review_reason']=='transaction_location_changed'

def test_unknown_or_conflicting_battle_does_not_open_mart():
    a=setup();a[1]['battle_state']['active']=True
    assert call(a)[0]['review_reason']=='transaction_nonbattle_signal_conflict'
    assert not tx._CONTROLLERS

def test_bridge_advances_only_on_pure_controller_receipt(monkeypatch):
    class Fake:
        error=None
        def __init__(self,*args):pass
        def context(self,*args,**kwargs):
            return {'phase':'mart_complete','available_actions':['wait'],'mart_purchase_complete':True}
    monkeypatch.setattr(tx.mart_purchase,'MartPurchaseController',Fake)
    a=setup();result,next_id=call(a)
    assert result['field_move_complete'] and result['field_move_kind']=='lavender_great_balls'
    assert next_id=='after' and 'buy' in tx._COMPLETED
