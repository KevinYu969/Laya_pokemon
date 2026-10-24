from tests.test_route21_water_bridge import env
from laya_pokemon import campaign_route as route
from laya_pokemon import route21_water_bridge as bridge


def test_first_wild_still_delivers_real_water_direction_then_returns_none(env,monkeypatch):
 for mod in (route.pallet_surf_bridge,route.fly_pallet_bridge,route.safari_entry,route.hm_teaching_bridge,
             route.vending_bridge,route.saffron_guard_bridge,route.silph_card_bridge,route.lapras_bridge,
             route.player_pc_bridge,route.campaign_transactions):
  monkeypatch.setattr(mod,'_BINDINGS',{});monkeypatch.setattr(mod,'_COMPLETED',set())
 monkeypatch.setattr(route.safari_entry,'_RUN_CONTROLLER',None)
 monkeypatch.setattr(route.capture_transaction,'_SESSIONS',{})
 from laya_pokemon import observation
 monkeypatch.setattr(observation,'read_visible_text',lambda p:dict(ready=True))
 monkeypatch.setattr(route,'read_world_grid',lambda *a:{})
 assert route.field_context(env.fake,env.state,env.plan,'route21') is None
 actual=['a','down'];route.switch_context(env.fake,env.state,env.plan,'route21',actual)
 c=bridge._CONTROLLERS['route21'];assert c.args['previous'] is actual
 env.state.update(frame=140,location=dict(map_id=32,x=4,y=1))
 env.state['battle_state'].update(raw=1,kind='wild',active=True,observation_frame=140)
 c.result=None
 assert route.field_context(env.fake,env.state,env.plan,'route21') is None
 assert route.switch_context(env.fake,env.state,env.plan,'route21',actual) is None
 assert bridge._CONTROLLERS['route21'] is c and c.args['previous'] is actual
 monkeypatch.setattr(route.pallet_surf_bridge,'_BINDINGS',{'pending-surf':('old',)})
 result=route.switch_context(env.fake,env.state,env.plan,'route21',actual)
 assert result[0]['review_reason']=='route21_water_other_transaction_active'
