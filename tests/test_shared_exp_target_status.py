"""支援者換上後受狀態招，正常交回原戰鬥與回城保護。"""
from test_shared_experience_training import Harness,command,packet
from laya_pokemon import balanced_training as training


def test_poisoned_target_command_completes_switch_without_selecting_it_again(monkeypatch):
    env=Harness(monkeypatch);env.call()
    target=env.party[-1];target['status']=8
    rows=command(env.party,active=-1)
    rows['cells'][8]=list(' '*15+'PSN'+' '*2)
    # packet補齊與真decoder一致的lines/line_rows，不能沿用健康時摘要。
    rows=packet([''.join(row) for row in rows['cells']])
    assert env.call(rows) is None
    assert training._SHARED_EXPERIENCE_PENDING is None
    assert training._SHARED_EXPERIENCE_LAST_COMPLETION['target_status']==8


def test_poisoned_target_in_moves_menu_also_hands_back_to_normal_battle(monkeypatch):
    env=Harness(monkeypatch);env.call()
    target=env.party[-1];target['status']=8
    rows=[''.join(row) for row in command(env.party,active=-1)['cells']]
    rows[8]=' '*15+'PSN'+' '*2
    rows[12:]=[' '*20]*6
    rows[13]='     ▶STRENGTH      '
    rows[14]='      AMNESIA       '
    rows[15]='      REST          '
    rows[16]='      BODY SLAM     '
    env.state['battle_menu']='moves'
    assert env.call(packet(rows)) is None
    assert training._SHARED_EXPERIENCE_PENDING is None
