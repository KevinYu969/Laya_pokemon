from laya_pokemon import victory_ladder_settle as gate


def test_nonstring_error_is_sticky_review_without_concat_exception(monkeypatch):
    monkeypatch.setattr(gate, '_WAITS', {})
    monkeypatch.setattr(gate, '_ERROR', 123)
    args = dict(shared=None, recovery=None, native_owner=None, game_id='game29', peer_owners={})
    out, _ = gate.preflight(None, {}, {}, None, **args)
    assert out['phase'] == 'campaign_review'
    assert out['review_reason'] == 'victory_ladder_settle_registry_unverified'
    assert gate._ERROR == 'registry_unverified'
    assert gate.preflight(None, {}, {}, None, **args)[0] == out
