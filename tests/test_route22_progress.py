"""Source-derived Route22 second-rival flags, independently toggled, read only."""
from copy import deepcopy
import pytest
from laya_pokemon.progress import read_progress,STORY_EVENT_NAMES
from tests.test_progress import fuchsia_constants,fuchsia_game

EXPECTED={'got_tm27':0x50,'beat_route22_rival_2nd_battle':0x526,'route22_rival_wants_battle':0x527}


@pytest.mark.parametrize('name',EXPECTED)
def test_real_sdk_source_bits_do_not_imply_champion_or_hall(name):
    c=fuchsia_constants();g=fuchsia_game(c,0)
    assert set(EXPECTED)<=set(STORY_EVENT_NAMES)
    assert {n:c.EVENT_FLAGS[n] for n in EXPECTED}==EXPECTED
    for eid in EXPECTED.values():g.memory.data[0xD747+eid//8]=0
    eid=EXPECTED[name];g.memory.data[0xD747+eid//8]=1<<(eid%8)
    before=deepcopy(g.memory.data);p=read_progress(g,c)
    assert {n:p['story_event_bits'][n] for n in EXPECTED}=={n:n==name for n in EXPECTED}
    assert p['champion_observed'] is False and p['hall_of_fame_confirmed'] is None
    assert g.memory.data==before
