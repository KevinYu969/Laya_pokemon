"""正常導航的Safari RUN接管與收尾，純封包、無模擬器IO。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from laya_pokemon import safari_entry as entry
from laya_pokemon import campaign_transactions as tx
from tests.test_safari_battle import args,menu,text


@pytest.fixture
def bridge(monkeypatch):
    monkeypatch.setattr(entry,'_RUN_CONTROLLER',None)
    monkeypatch.setattr(entry,'_RUN_OWNER',None)
    monkeypatch.setattr(entry,'_CONTROLLERS',{})
    monkeypatch.setattr(entry,'_BINDINGS',{})
    monkeypatch.setattr(entry,'_COMPLETED',set())
    current={'a':args()}
    template=deepcopy(current['a'])
    monkeypatch.setattr(entry,'read_safari_state',lambda _:current['a']['safari'])
    monkeypatch.setattr(entry.safari_battle_module,'read_safari_battle_signal',lambda *a,**k:current['a']['battle_signal'])
    monkeypatch.setattr(tx,'ui_overworld_ready',lambda t,g:g.get('ready',False))
    plan={'steps':[{'id':'route-east','kind':'move','map_id':220,'target':[29,10]}]}
    def call(view,frame=10,raw=1,ready=False,step='route-east'):
        # 不再呼叫args內的reader：它正被bridge stub替換，否則會回上一幀。
        a=deepcopy(template)
        a['safari']['observation_frame']=frame
        a['battle_signal'].update(observation_frame=frame,raw=raw,
            enemy_species=18 if raw==1 else None,enemy_level=25 if raw==1 else None)
        a['battle_state'].update(observation_frame=frame,raw=raw,active=raw==1,
            kind='wild' if raw==1 else 'none',opponent_species='RHYHORN' if raw==1 else None)
        current['a']=a
        state={'frame':frame,'location':deepcopy(a['location']),'battle_state':a['battle_state']}
        return entry.field_context(SimpleNamespace(),state,plan,step,view,{'ready':ready})
    return call


def test_verified_safari_menu_claims_run_and_never_presses_ball(bridge):
    hint,step=bridge(menu())
    assert step=='route-east' and hint['available_actions']==['right','wait']
    assert entry._RUN_OWNER=='route-east' and not entry._RUN_CONTROLLER.run_sent
    result=bridge(menu((13,14)),11)[0]
    assert result['available_actions']==['down','wait'],result
    assert bridge(menu((13,16)),12)[0]['available_actions']==['a','wait']
    assert entry._RUN_CONTROLLER.run_sent


def test_run_owner_cannot_be_changed_by_route_update(bridge):
    bridge(menu())
    result,_=bridge(menu(),11,step='another-step')
    assert result['review_reason']=='safari_run_owner_changed' and result['available_actions']==['wait']


def test_run_claim_stays_through_nonbattle_until_two_closed_frames(bridge):
    bridge(menu((13,16)))
    closed=text(hud=False);closed['window_visible']=False
    hint,step=bridge(closed,11,raw=0,ready=True)
    assert not hint.get('safari_run_complete') and entry._RUN_CONTROLLER is not None
    hint,step=bridge(closed,12,raw=0,ready=True)
    assert hint.get('safari_run_complete') and step=='route-east',hint
    assert entry._RUN_CONTROLLER is None and entry._RUN_OWNER is None
    assert bridge(closed,13,raw=0,ready=True) is None
