from tests.test_pallet_surf_bridge import env
from laya_pokemon import campaign_route as route
from laya_pokemon import pallet_surf_bridge as bridge


def test_surf_dispatch_preserves_real_history_before_generic_menus(env,monkeypatch):
 for mod in (route.fly_pallet_bridge,route.safari_entry,route.hm_teaching_bridge,route.vending_bridge,
             route.saffron_guard_bridge,route.silph_card_bridge,route.lapras_bridge,route.player_pc_bridge,
             route.campaign_transactions):
  monkeypatch.setattr(mod,'_BINDINGS',{});monkeypatch.setattr(mod,'_COMPLETED',set())
 monkeypatch.setattr(route.safari_entry,'_RUN_CONTROLLER',None)
 monkeypatch.setattr(route.capture_transaction,'_SESSIONS',{})
 from laya_pokemon import observation
 monkeypatch.setattr(observation,'read_visible_text',lambda p:dict(ready=True))
 monkeypatch.setattr(route,'read_world_grid',lambda *a:{})
 assert route.field_context(env.fake,env.state,env.plan,'surf-pallet') is None
 actual=['down','start','a']
 result=route.switch_context(env.fake,env.state,env.plan,'surf-pallet',actual)
 assert result[1]=='surf-pallet' and bridge._CONTROLLERS['surf-pallet'].args['previous'] is actual
 monkeypatch.setattr(route.fly_pallet_bridge,'_BINDINGS',{'pending-fly':('old',)})
 result=route.switch_context(env.fake,env.state,env.plan,'surf-pallet',actual)
 assert result[0]['review_reason']=='pallet_surf_other_transaction_active'
