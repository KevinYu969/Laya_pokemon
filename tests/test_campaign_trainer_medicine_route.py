"""Route ownership remains with a live medicine UI; legacy battle stays reachable."""
import pytest
from laya_pokemon import campaign_route as route,observation


@pytest.fixture
def env(monkeypatch):
    bridge=route.trainer_medicine_ui_bridge
    monkeypatch.setattr(bridge,'_BINDINGS',{})
    monkeypatch.setattr(bridge,'_CONTROLLERS',{})
    monkeypatch.setattr(bridge,'_COMPLETED',set())
    step=dict(id='giovanni-live',kind='interact',map_id=45,target=[2,2],face='up',
              event='beat_viridian_gym_giovanni',battle_supply=bridge.SUPPLY)
    text=object();monkeypatch.setattr(observation,'read_visible_text',lambda pb:text)
    return step,dict(steps=[step]),text


def test_original_previous_reaches_switch_and_field_never_claims_it(env,monkeypatch):
    step,plan,text=env;seen=[];state=object();pb=object();previous=['up','a']
    def dispatch(*args):
        seen.append(args);return dict(phase='trainer_medicine_menu'),step['id']
    monkeypatch.setattr(route.trainer_medicine_dispatch,'context',dispatch)
    assert route.field_context(pb,state,plan,step['id']) is None and not seen
    assert route.switch_context(pb,state,plan,step['id'],previous)[0]['phase']=='trainer_medicine_menu'
    assert seen==[(pb,state,plan,step['id'],text,previous)]


def test_active_medicine_catches_foreign_fly_before_its_dispatch(env,monkeypatch):
    step,plan,text=env;route.trainer_medicine_ui_bridge._BINDINGS['medicine']=object()
    foreign=dict(id='foreign-fly',kind='interact',mechanic='fly_viridian',map_id=8,target=[18,4])
    plan['steps'].append(foreign)
    monkeypatch.setattr(route.fly_viridian_bridge,'context',lambda *a:pytest.fail('foreign transaction started'))
    monkeypatch.setattr(observation,'read_visible_text',lambda pb:pytest.fail('foreign owner UI read'))
    monkeypatch.setattr(route.trainer_medicine_dispatch,'context',lambda *a:pytest.fail('foreign medicine dispatch'))
    assert route.field_context(object(),{},plan,'foreign-fly') is None
    result,step_id=route.switch_context(object(),{},plan,'foreign-fly',[])
    assert result['review_reason']=='trainer_medicine_owner_changed' and step_id=='foreign-fly'


def test_non_command_none_falls_through_to_existing_route_dispatch(env,monkeypatch):
    step,plan,text=env
    monkeypatch.setattr(route.trainer_medicine_dispatch,'context',lambda *a:None)
    reached=[]
    def next_branch(*args):reached.append(True);return False
    monkeypatch.setattr(route.cinnabar_purchase_bridge,'applies',next_branch)
    assert route.switch_context(object(),{},plan,step['id'],[]) is None
    assert reached  # None must not cut off the established dispatch chain.


def test_existing_opponent_gate_keeps_priority_before_new_policy(env,monkeypatch):
    step,plan,text=env;step['opponent_review']='existing-native-intro'
    expected=dict(phase='campaign_review',review_reason='existing_gate')
    monkeypatch.setattr(route.opponent_review_gate,'read_intro_signal',lambda pb:{})
    monkeypatch.setattr(route.opponent_review_gate,'context',lambda *a,**kw:expected)
    monkeypatch.setattr(route.trainer_medicine_dispatch,'context',lambda *a:pytest.fail('policy preceded intro'))
    assert route.switch_context(object(),{},plan,step['id'],[])==(expected,step['id'])
