import math
from types import SimpleNamespace
import pytest
from laya_pokemon import campaign_route as route


def test_native_clock_retains_anchor_and_spent_budget_across_engineering_pause(monkeypatch):
    c=SimpleNamespace(last_now=12.5,last_frame=107929,elapsed=7.,started=4.)
    monkeypatch.setattr(route.league_native_wait,'_WAITS',{'native':c})
    before=dict(vars(c))
    assert route._native_wait_clock('native',107929)==12.5
    assert route._native_wait_clock('native',107969)==pytest.approx(12.5+40/60)
    assert vars(c)==before
    assert route._native_wait_clock('new',107969) is None


@pytest.mark.parametrize('field,value',[('last_frame',True),('last_frame',108000),('last_now',False),('last_now',float('inf'))])
def test_invalid_old_clock_is_never_reanchored_to_new_wall_time(monkeypatch,field,value):
    c=SimpleNamespace(last_now=12.5,last_frame=107929);setattr(c,field,value)
    monkeypatch.setattr(route.league_native_wait,'_WAITS',{'native':c})
    assert math.isnan(route._native_wait_clock('native',107969))
