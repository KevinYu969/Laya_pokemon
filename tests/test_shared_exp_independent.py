"""共享經驗獨立複審：只用假讀值，不建立遊戲或模型。"""
from copy import deepcopy

from test_shared_experience_training import Harness, command, packet
from laya_pokemon import balanced_training as training
from laya_pokemon.battle import _trainer_half_party_view


def test_same_frame_target_hud_conflict_cannot_clear_pending(monkeypatch):
    env = Harness(monkeypatch)
    env.call()
    owner = training._SHARED_EXPERIENCE_PENDING
    original_packet = deepcopy(owner['last_packet'])
    calls = len(env.calls)

    # 同一個 frame 不可能同時是原 Lapras 與換人完成後的 Snorlax HUD。
    out = env.call(command(env.party, 5), advance=False)

    assert isinstance(out, dict), '矛盾同幀不得以 None 交回一般戰鬥策略'
    assert out['phase'] == 'campaign_review'
    assert out['available_actions'] == ['wait']
    assert out['review_reason'].endswith('same_frame_packet_conflict')
    assert training._SHARED_EXPERIENCE_PENDING is owner
    assert owner['last_packet'] == original_packet
    assert len(env.calls) == calls


def test_full_six_party_native_packet_shape_then_new_target_command_exits(monkeypatch):
    env = Harness(monkeypatch)

    def observed(text):
        # 保留 decoder 的實體 18×20 格網、首 12 行語意摘要及列座標。
        result = deepcopy(text)
        result['observation_frame'] = env.frame + 4
        assert len(result['cells']) == 18
        assert all(len(row) == 20 for row in result['cells'])
        assert len(result['lines']) == len(result['line_rows'])
        for line, y in zip(result['lines'], result['line_rows']):
            assert ''.join(result['cells'][y]).rstrip() == line
        return result

    out = env.call(observed(command(env.party)))
    assert out['objective'] == 'Move RIGHT.'
    owner = training._SHARED_EXPERIENCE_PENDING
    out = env.call(observed(command(env.party, cursor=(15, 14))))
    assert out['objective'] == 'Confirm the current selection.'
    for index in range(6):
        out = env.call(observed(packet(_trainer_half_party_view(env.party, index))))
        assert out['objective'] == ('Move DOWN.' if index < 5 else 'Confirm the current selection.')
        assert training._SHARED_EXPERIENCE_PENDING is owner
    out = env.call(observed(packet(_trainer_half_party_view(env.party, 5, True))))
    assert out['menu_label'] == 'SWITCH'
    assert out['available_actions'] == ['a', 'wait']
    assert training._SHARED_EXPERIENCE_PENDING is owner
    calls = len(env.calls)

    # 僅新 frame 上完整、相符的真目標 command 允許結束共享經驗換人。
    assert env.call(observed(command(env.party, 5))) is None
    assert training._SHARED_EXPERIENCE_PENDING is None
    assert len(env.calls) == calls
