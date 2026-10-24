"""11F真SDK門事件與坂木WAIT分派的純合成測試。"""
from copy import deepcopy
import pytest
from laya_pokemon.progress import read_progress
from laya_pokemon import campaign_route as route
from tests.test_progress import fuchsia_constants,fuchsia_game
from tests.test_silph_giovanni_wait import state,step as source_step


@pytest.mark.parametrize('bit',range(8))
def test_fixed_sdk_door_bit_is_independent_from_giovanni_and_no_writes(bit):
    c=fuchsia_constants();assert c.EVENT_FLAGS['silph_co_11_unlocked_door']==0x788
    g=fuchsia_game(c,0);g.memory.data[0xD838]=1<<bit
    before=dict(g.memory.data);p=read_progress(g,c)
    assert p['story_event_bits']['silph_co_11_unlocked_door'] is (bit==0)
    assert p['story_event_bits']['beat_silph_co_giovanni'] is (bit==7)
    assert g.memory.data==before and g.memory.reads[0xD838]==1
    assert p['hall_of_fame_confirmed'] is None


@pytest.mark.parametrize('change',['missing','shifted','boolean','float','base','bool_base'])
def test_unverified_door_contract_is_unknown(change):
    c=fuchsia_constants();c.EVENT_FLAGS=dict(c.EVENT_FLAGS)
    if change=='missing':c.EVENT_FLAGS.pop('silph_co_11_unlocked_door')
    elif change=='shifted':c.EVENT_FLAGS['silph_co_11_unlocked_door']=0x789
    elif change=='boolean':c.EVENT_FLAGS['silph_co_11_unlocked_door']=True
    elif change=='float':c.EVENT_FLAGS['silph_co_11_unlocked_door']=1928.0
    elif change=='base':c.EVENT_FLAGS_ADDRESS=0xD748
    else:c.EVENT_FLAGS_ADDRESS=True
    g=fuchsia_game(c,0);g.memory.data[0xD838]=255
    assert read_progress(g,c)['story_event_bits']['silph_co_11_unlocked_door'] is None


def test_route_dispatches_only_giovanni_module_and_preserves_other_cases(monkeypatch):
    route.silph_giovanni_wait._GIOVANNI_WAITS.clear()
    s=state();step=source_step()
    out=route.coordinate_script_wait(s,step)
    assert out['available_actions']==['wait'] and out['choice_source']=='silph_giovanni_coordinate_script_wait'
    assert route.coordinate_script_wait(s,{**step,'target':[6,14]})['phase']=='campaign_review'
    sentinel={'phase':'other_existing_case'}
    monkeypatch.setattr(route.silph_rival_wait,'silph_rival_script_wait',lambda *args:sentinel)
    assert route.coordinate_script_wait({},dict(id='rival',map_id=212,event='beat_silph_co_rival'))==sentinel
    route.silph_giovanni_wait._GIOVANNI_WAITS.clear()
