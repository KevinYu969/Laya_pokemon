"""真純controller＋真readonly reader經bridge接線；無遊戲、模型或按鍵。"""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from laya_pokemon import saffron_guard_bridge as bridge


def text(words=None,arrow=False):
    cells=[[' ']*20 for _ in range(18)]
    if words:
        for y,word in zip((14,16),words):
            if y==14 and word=='to SAFFRON CITY...':word=word[:17]
            chars=list(word.replace("'l",'\ue100').replace("'m",'\ue101'))
            cells[y][1:1+len(chars)]=["'l" if c=='\ue100' else "'m" if c=='\ue101' else c for c in chars]
    if arrow:cells[16][18]='▼'
    return {'profile':bridge.saffron_guard.TEXT_PROFILE,'read_valid':True,'alignment_verified':True,
            'read_error':None,'window_visible':words is not None,'cells':cells}


@pytest.fixture
def session(monkeypatch):
    for name,value in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_COMPLETED',set())):
        monkeypatch.setattr(bridge,name,value)
    from laya_pokemon import campaign_transactions as tx
    monkeypatch.setattr(tx,'ui_overworld_ready',lambda t,g:g is not None and not t['window_visible'])
    class Memory(dict):
        def __setitem__(self,k,v):raise AssertionError('reader must not write game memory')
    memory=Memory({0xD728:1,0xD35E:76,0xD361:4,0xD362:2})
    emulator=SimpleNamespace(frame_count=40,memory=memory)
    state={'frame':40,'location':{'map_id':76,'x':2,'y':4},
           'battle_state':{'kind':'none','active':False,'raw':0,'observation_frame':40},
           'progress':{'profile':'gen1-wrapper-ram-progress-v1-unvalidated','initialization_candidate':True,
               'party_read_valid':True,'party_count':1,'money':40366,
               'inventory':[{'item':198,'quantity':1},{'item':60,'quantity':1},{'item':199,'quantity':1}],
               'party':[{'species':132,'species_name':'SNORLAX','level':35,'hp':168,'max_hp':168,
                         'exp':56987,'status':0,'moves':[70,133,156,34],'pp':[15,20,10,15]}]}}
    plan={'steps':[{'id':'guard','kind':'interact','map_id':76,'target':[2,4],
             'mechanic':bridge.MECHANIC,'guard_intent':deepcopy(bridge.saffron_guard.INTENT)},
             {'id':'exit','kind':'move','map_id':76,'target':[6,4],'next_map':18,'terminal':True}]}
    def call(t=None,step='guard',advance=True):
        if advance:
            state['frame']+=40;emulator.frame_count=state['frame']
            state['battle_state']['observation_frame']=state['frame']
        return bridge.context(emulator,state,plan,step,text() if t is None else t,{})
    def arrive():
        state['location']['x']=3;dict.__setitem__(memory,0xD362,3)
        state['progress']['inventory']=[i for i in state['progress']['inventory'] if i['item']!=60]
    return SimpleNamespace(call=call,arrive=arrive,state=state,plan=plan,emulator=emulator,memory=memory)


def test_real_reader_and_controller_need_all_source_pages_one_removal_and_two_closed_frames(session):
    s=session;before=deepcopy(s.state['progress'])
    result,step=s.call();assert result['objective']=='Move RIGHT.' and step=='guard'
    assert s.call(advance=False)[0]['available_actions']==['wait']
    s.arrive()
    for page in bridge.saffron_guard.PAGES[:-1]:
        assert s.call(text(page,True))[0]['available_actions']==['a','wait']
    final=text(bridge.saffron_guard.PAGES[-1])
    assert s.call(final)[0]['available_actions']==['wait']
    assert s.call(final)[0]['available_actions']==['a','wait']
    dict.__setitem__(s.memory,0xD728,65)
    assert not s.call()[0].get('saffron_guard_complete')
    result,step=s.call();assert result['saffron_guard_complete'] and step=='exit'
    c=bridge._CONTROLLERS['guard'];assert c.actions==16 and c.consumed and 'guard' in bridge._COMPLETED
    assert s.state['progress']['party']==before['party'] and s.state['progress']['money']==40366


def test_wrong_owner_or_changed_explicit_intent_cannot_replace_original_baseline(session):
    s=session;s.call();c=bridge._CONTROLLERS['guard'];baseline=c.baseline
    assert s.call(step='exit')[0]['review_reason']=='saffron_guard_owner_changed'
    s.plan['steps'][0]['guard_intent']['trigger_at']=[4,4]
    assert s.call()[0]['review_reason']=='saffron_guard_explicit_intent_unverified'
    assert c.baseline is baseline and c.actions==1


def test_unknown_source_reader_and_mismatched_text_frame_never_move(session):
    s=session;dict.__setitem__(s.memory,0xD35E,77)
    assert s.call()[0]['available_actions']==['wait']
    assert bridge._CONTROLLERS['guard'].actions==0


def test_explicit_text_frame_is_checked_by_real_controller_before_right(session):
    s=session;t=text();t['observation_frame']=999
    result,_=s.call(t);assert result['review_reason']=='saffron_guard_observation_frame_or_ready_unverified'
    assert bridge._CONTROLLERS['guard'].baseline is None


def test_review_revision_keeps_consumed_baseline_and_pending_page(session):
    s=session;s.call();s.arrive();s.call(text(bridge.saffron_guard.PAGES[0],True))
    c=bridge._CONTROLLERS['guard'];baseline=c.baseline;page=c.page;pending=c.pending
    c.error='source-page-calibration'
    s.plan['steps'][0].update(reviewed_guard_revision=1,reviewed_guard_error=c.error)
    result,_=s.call(text(bridge.saffron_guard.PAGES[0],True))
    assert result['available_actions']==['wait'] and c.error is None
    assert c.baseline is baseline and c.page==page and c.pending==pending and c.consumed and c.actions==2


def test_initial_wrong_stance_is_left_to_normal_navigation(session):
    session.state['location']['x']=1
    assert session.call() is None and not bridge._BINDINGS


def test_live_router_cannot_hide_an_unfinished_water_purchase(session,monkeypatch):
    from laya_pokemon import campaign_route as route
    monkeypatch.setattr(route.saffron_guard_bridge,'applies',lambda *a:True)
    monkeypatch.setattr(route.safari_entry,'_BINDINGS',{})
    monkeypatch.setattr(route.safari_entry,'_RUN_CONTROLLER',None)
    monkeypatch.setattr(route.vending_bridge,'_BINDINGS',{'water':'bound'})
    monkeypatch.setattr(route.vending_bridge,'_COMPLETED',set())
    result,_=route.field_context(session.emulator,session.state,session.plan,'guard')
    assert result['review_reason']=='saffron_guard_other_transaction_active'
