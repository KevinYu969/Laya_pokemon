"""非戰鬥隊伍損耗閘門候選；純函式，不按鍵、不改進度或行程。"""
from __future__ import annotations

from numbers import Integral


def _review(reason, step_id, **details):
    return {'phase': 'campaign_review', 'objective': 'Wait.', 'available_actions': ['wait'],
            'review_reason': reason, 'route_step': step_id,
            'phase_source': '唯讀非戰鬥隊伍損耗檢查；需正常回中心恢復',
            'party_attrition': details}


def _recovery_step(plan, step_id):
    """只接受唯一、明確標記且屬move/heal的當前步驟；其他操作不可豁免。"""
    steps = plan.get('steps')
    if not isinstance(steps, list) or not isinstance(step_id, str) or not step_id:
        return False
    matches = [step for step in steps if isinstance(step, dict) and step.get('id') == step_id]
    return (len(matches) == 1 and matches[0].get('recovery_route') is True
            and matches[0].get('kind') in ('move', 'heal'))


def attrition_context(state, plan, step_id):
    """在下一個導航按鍵之前攔截損耗；戰敗閘門必須由呼叫端先執行。

    只檢查league_campaign的overworld/unclassified。非戰鬥須同時有
    kind='none'、active=False；任一倒下或首位HP≤2/3就要求回中心。
    未知讀值一律要求檢討。正常回中心豁免
    仍須有效隊伍／HP證據，不能拿flag繞過未知訊號或interact/use_cut。
    """
    if plan.get('mode') != 'league_campaign' or state.get('phase') not in ('overworld', 'unclassified'):
        return None
    battle = state.get('battle_state')
    if not isinstance(battle, dict):
        return _review('party_attrition_state_unverified', step_id, issue='battle_state_missing')
    if battle.get('active') is True or battle.get('kind') in ('wild', 'trainer', 'lost_transition'):
        return None
    if battle.get('kind') != 'none' or battle.get('active') is not False:
        return _review('party_attrition_state_unverified', step_id, issue='nonbattle_not_verified')
    progress = state.get('progress')
    if not isinstance(progress, dict) or progress.get('party_read_valid') is not True:
        return _review('party_attrition_state_unverified', step_id, issue='party_read_not_verified')
    party = progress.get('party')
    if not isinstance(party, list) or not 1 <= len(party) <= 6:
        return _review('party_attrition_state_unverified', step_id, issue='party_roster_invalid')
    if 'party_count' in progress and (type(progress['party_count']) is not int
                                      or progress['party_count'] != len(party)):
        return _review('party_attrition_state_unverified', step_id, issue='party_count_mismatch')
    health = []
    for index, mon in enumerate(party):
        if not isinstance(mon, dict):
            return _review('party_attrition_state_unverified', step_id, issue='party_member_invalid', party_index=index)
        hp, maximum = mon.get('hp'), mon.get('max_hp')
        if (not isinstance(hp, Integral) or isinstance(hp, bool)
                or not isinstance(maximum, Integral) or isinstance(maximum, bool)
                or maximum <= 0 or not 0 <= hp <= maximum):
            return _review('party_attrition_state_unverified', step_id, issue='party_hp_invalid', party_index=index)
        health.append((int(hp), int(maximum)))
    fainted = [index for index, (hp, _) in enumerate(health) if hp == 0]
    lead_hp, lead_max = health[0]
    low_lead = lead_hp * 3 <= lead_max * 2
    if not fainted and not low_lead:
        return None
    if not fainted:
        from .capture_closing_gate import eligible
        if eligible(state,plan,step_id):
            return None  # 同owner只作閉合WAIT驗收；下一步仍回本損耗閘門。
    if _recovery_step(plan, step_id):
        return None
    return _review('party_attrition_requires_center', step_id,
                   fainted_party_indices=fainted, lead_hp=lead_hp, lead_max_hp=lead_max,
                   lead_at_or_below_two_thirds=low_lead)
