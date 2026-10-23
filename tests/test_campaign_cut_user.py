"""主線在自然進化後仍選實際學會Cut的唯一使用者。"""
from types import SimpleNamespace
import pytest
from laya_pokemon import campaign_route as route,observation

class Memory:
    def __getitem__(self,key):
        assert key==0xC109;return 8
    def __setitem__(self,*args):raise AssertionError('No game memory writes')

@pytest.fixture(autouse=True)
def clean():
    route._FIELD_CONTROLLERS.clear();yield;route._FIELD_CONTROLLERS.clear()

def call(monkeypatch,party):
    class Fake:
        def __init__(self,intent):self.intent=intent
        def context(self,*args,**kwargs):return {'selected_intent':self.intent,'available_actions':['wait']}
    monkeypatch.setattr(route.field_moves_module,'CutController',Fake)
    monkeypatch.setattr(route.campaign_transactions,'applies',lambda *a:False)
    monkeypatch.setattr(route,'read_world_grid',lambda *a:{})
    monkeypatch.setattr(observation,'read_visible_text',lambda *a:{})
    state={'location':{'map_id':19,'x':42,'y':10},'battle_state':{'kind':'none'},
           'progress':{'party_read_valid':True,'party':party}}
    step={'id':'cut','kind':'use_cut','map_id':19,'target':[42,10],'tree':[41,10],'face':'left'}
    return route.field_context(SimpleNamespace(memory=Memory()),state,{'steps':[step]},'cut')[0]

@pytest.mark.parametrize('species',[9,154])
def test_unique_actual_cut_user_preserves_evolution_form(monkeypatch,species):
    result=call(monkeypatch,[{'species':species,'moves':[75,15,73,22]},{'species':7,'moves':[61,33,30,40]}])
    assert result['selected_intent']['species']==species

@pytest.mark.parametrize('party',[
    [{'species':154,'moves':[75,33,73,22]}],
    [{'species':9,'moves':[15,0,0,0]},{'species':154,'moves':[15,0,0,0]}],[]])
def test_missing_or_ambiguous_cut_user_pauses(monkeypatch,party):
    assert call(monkeypatch,party)['review_reason']=='unique_current_cut_user_unverified'
