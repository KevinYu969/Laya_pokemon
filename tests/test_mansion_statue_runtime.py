from tests.test_mansion_statue_bridge import env
from laya_pokemon import campaign_route as route
from laya_pokemon import mansion_statue_bridge as bridge


def test_statue_receives_actual_previous_before_generic_navigation(env,monkeypatch):
 for mod in (route.mansion_native_landing,route.route21_water_bridge,route.pallet_surf_bridge,
  route.fly_pallet_bridge,route.safari_entry,route.hm_teaching_bridge,route.vending_bridge,
  route.saffron_guard_bridge,route.silph_card_bridge,route.lapras_bridge,route.player_pc_bridge,
  route.campaign_transactions):
  monkeypatch.setattr(mod,'_BINDINGS',{});monkeypatch.setattr(mod,'_COMPLETED',set())
 monkeypatch.setattr(route.safari_entry,'_RUN_CONTROLLER',None)
 monkeypatch.setattr(route.capture_transaction,'_SESSIONS',{})
 from laya_pokemon import observation
 monkeypatch.setattr(observation,'read_visible_text',lambda p:dict(ready=True))
 monkeypatch.setattr(route,'read_world_grid',lambda *a:{})
 actual=['up','a'];seen=[]
 monkeypatch.setattr(bridge,'context',lambda *a:seen.append(a) or ({'phase':'mansion_statue'},'statue'))
 assert route.field_context(None,env.state,env.plan,env.step['id']) is None
 out=route.switch_context(None,env.state,env.plan,env.step['id'],actual)
 assert out[0]['phase']=='mansion_statue' and seen[-1][-1] is actual
 monkeypatch.setattr(route.mansion_native_landing,'_BINDINGS',{'other':('bound',)})
 assert route.switch_context(None,env.state,env.plan,env.step['id'],actual)[0]['review_reason']=='mansion_statue_other_transaction_active'
