"""希魯夫11F坂木座標腳本的有界WAIT；不讀寫遊戲或整合runner。

只等原生對話／NPC移動／開戰。事件成立交還caller，不冒稱勝利或已閉合。
"""
from copy import deepcopy
import math
import re
import time

from .mart_purchase import _inventory, _party

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE = f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/scripts/SilphCo11F.asm'
SOURCE_BLOB = '334b68063c55071743190bc6c6923032285f5c48'
EVENT = 'beat_silph_co_giovanni'
PREREQUISITES = ('beat_silph_co_rival', 'silph_co_11_unlocked_door')
TRIGGERS = ((6, 13), (7, 12))
MAX_CALLS, MAX_SECONDS = 25, 60
# 熱載入不重綁owner、不重設原預算或已鎖定的錯誤。
_GIOVANNI_WAITS = globals().get('_GIOVANNI_WAITS', {})


def _int(value):
    return type(value) is int and 0 <= value <= 0x7FFFFFFFFFFFFFFF


def _intent(step):
    return (isinstance(step, dict) and isinstance(step.get('id'), str)
            and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', step['id']) is not None
            and step.get('kind') == 'move' and type(step.get('map_id')) is int
            and step['map_id'] == 235 and type(step.get('target')) is list
            and len(step['target']) == 2 and all(type(n) is int for n in step['target'])
            and tuple(step['target']) in TRIGGERS and step.get('await_script_event') is True
            and step.get('event') == EVENT and 'next_map' not in step and 'terminal' not in step)


def silph_giovanni_script_wait(state, step, *, now=None):
    """同次observe的state＋精確step，只回WAIT／review／None，絕不回A或方向。

    raw1野生／raw2訓練家交回戰鬥；真事件交回既有路線／對話而非成功回執。
    loc及progress若附observation_frame必須同幀；battle的同幀標記不可省略。
    caller仍負責戰敗優先閘門、對話及最後勝利／閉合驗收。
    """
    sid = step.get('id') if isinstance(step, dict) else None
    record = _GIOVANNI_WAITS.get(sid) if isinstance(sid, str) else None

    def review(reason):
        if record is not None:
            record['error'] = reason
        return {'phase': 'campaign_review', 'objective': 'Wait.', 'available_actions': ['wait'],
                'review_reason': 'silph_giovanni_wait_' + reason, 'route_step': sid,
                'source_commit': SOURCE_COMMIT, 'choice_source': 'silph_giovanni_coordinate_script_wait'}

    if record is not None and record['error'] is not None:
        return review(record['error'])
    if not _intent(step):
        return review('intent_unverified')
    if record is not None and record['step'] != step:
        return review('step_id_binding_changed')
    if not isinstance(state, dict):
        return review('observation_unverified')
    frame, loc, battle = state.get('frame'), state.get('location'), state.get('battle_state')
    if (not _int(frame) or not isinstance(loc, dict)
            or any(type(loc.get(k)) is not int for k in ('map_id', 'x', 'y'))
            or (loc['map_id'], loc['x'], loc['y']) != (235, *step['target'])
            or not isinstance(battle, dict) or type(battle.get('observation_frame')) is not int
            or battle['observation_frame'] != frame or type(battle.get('raw')) is not int):
        return review('same_frame_location_or_battle_unverified')
    p = state.get('progress')
    for packet in (loc, p):
        if not isinstance(packet, dict) or ('observation_frame' in packet and
                (type(packet['observation_frame']) is not int or packet['observation_frame'] != frame)):
            return review('packet_frame_disagrees')
    now = time.monotonic() if now is None else now
    if (type(now) not in (int, float) or not math.isfinite(now) or now < 0
            or record is not None and (now < record['last_now'] or frame < record['last_frame'])):
        return review('clock_or_frame_regressed')
    packet = deepcopy((loc, p, battle))
    if record is not None and record['last_frame'] == frame and record['packet'] != packet:
        return review('same_frame_packet_conflict')
    if (battle.get('active') is True and
            (battle.get('kind'), battle['raw']) in (('wild', 1), ('trainer', 2))):
        return None
    if battle.get('kind') != 'none' or battle.get('active') is not False or battle['raw'] != 0:
        return review('nonbattle_unverified')
    party, inventory = _party(p), _inventory(p.get('inventory'))
    events = p.get('story_event_bits')
    if (party is None or len(party) != 6 or any(m['hp'] <= 0 for m in party)
            or any(m['status'] not in (*range(8), 8, 16, 32, 64) for m in party)
            or any(move == 0 and pp != 0 for m in party for move, pp in zip(m['moves'], m['pp']))
            or inventory is None
            or [i for i in inventory if i['item'] == 48] != [{'item': 48, 'quantity': 1}]
            or not isinstance(events, dict) or any(events.get(k) is not True for k in PREREQUISITES)
            or type(events.get(EVENT)) is not bool):
        return review('key_party_or_events_unverified')
    if events[EVENT] is True:
        return None  # 旗標不是本次勝利、對話完成或野外閉合證據。
    if record is None:
        record = {'step': deepcopy(step), 'started': now, 'last_now': now, 'last_frame': -1,
                  'packet': None, 'calls': 0, 'error': None}
        _GIOVANNI_WAITS[sid] = record
    record['calls'] += 1
    record['last_now'], record['last_frame'], record['packet'] = now, frame, packet
    if record['calls'] > MAX_CALLS or now - record['started'] > MAX_SECONDS:
        return review('budget_exhausted')
    return {'phase': 'overworld', 'objective': 'Wait.', 'available_actions': ['wait'],
            'goal': sid, 'route_step': sid, 'source_coordinate_script_wait': True,
            'source_commit': SOURCE_COMMIT, 'source': SOURCE,
            'silph_giovanni_wait_calls': record['calls'],
            'choice_source': 'silph_giovanni_coordinate_script_wait',
            'phase_source': 'SilphCo11F.asm:163–198,238–275；固定玩家觸發格等坂木原生DOWN三步及開戰，不當勝利。'}
