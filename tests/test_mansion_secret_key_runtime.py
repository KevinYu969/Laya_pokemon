import pytest
from laya_pokemon import campaign_route as route
from tests.test_mansion_secret_key_bridge import env


@pytest.mark.parametrize('foreign',['mansion_statue_bridge','mansion_transition_ready','mansion_native_landing'])
def test_key_receives_actual_previous_before_generic_interact_and_blocks_foreign_transaction(env,monkeypatch,foreign):
    modules=(route.mansion_statue_bridge,route.mansion_transition_ready,route.mansion_native_landing,
        route.route21_water_bridge,route.pallet_surf_bridge,route.fly_pallet_bridge,route.safari_entry,
        route.hm_teaching_bridge,route.vending_bridge,route.saffron_guard_bridge,route.silph_card_bridge,
        route.lapras_bridge,route.player_pc_bridge,route.campaign_transactions)
    for module in modules:
        monkeypatch.setattr(module,'_BINDINGS',{});monkeypatch.setattr(module,'_COMPLETED',set())
    monkeypatch.setattr(route.safari_entry,'_RUN_CONTROLLER',None)
    monkeypatch.setattr(route.capture_transaction,'_SESSIONS',{})
    from laya_pokemon import observation
    monkeypatch.setattr(observation,'read_visible_text',lambda game:{'native':'full text'})
    monkeypatch.setattr(route,'read_world_grid',lambda *args:{'native':'grid'})
    seen=[];previous=['down','a']
    monkeypatch.setattr(route.mansion_secret_key_bridge,'context',
        lambda *args:seen.append(args) or ({'phase':'mansion_secret_key'},env.step['id']))
    assert route.field_context(env.game,env.state,env.plan,env.step['id']) is None
    result=route.switch_context(env.game,env.state,env.plan,env.step['id'],previous)
    assert result[0]['phase']=='mansion_secret_key' and seen[-1][-1] is previous
    monkeypatch.setattr(getattr(route,foreign),'_BINDINGS',{'another-transaction':('original',)})
    assert route.switch_context(env.game,env.state,env.plan,env.step['id'],previous)[0]['review_reason']=='mansion_secret_key_other_transaction_active'
