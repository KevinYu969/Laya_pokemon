"""紅蓮固定館戰補藥的唯讀橋接候選；父層明示意圖，不含治療策略。"""
from copy import deepcopy
import importlib
import math
import time

from laya_pokemon import battle_medicine as bm, trainer_opponent, player_battle

importlib.reload(bm)
importlib.reload(trainer_opponent)

SUPPLY = 'cinnabar-lapras38-hyper-fullheal-v1'
SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
_CONTROLLERS = globals().get('_CONTROLLERS', {})
_BINDINGS = globals().get('_BINDINGS', {})
_COMPLETED = globals().get('_COMPLETED', set())
_ACTIONS = {'a', 'b', 'up', 'down', 'left', 'right', 'start', 'wait'}


def _int(value):
    return type(value) is int and 0 <= value <= 0x7fffffffffffffff


def _exact(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_exact(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(_exact(x, y) for x, y in zip(a, b))
    return a == b


def _active():
    return (set(_CONTROLLERS) | set(_BINDINGS)) - _COMPLETED


def _review(reason, step_id, owner=None):
    record = _BINDINGS.get(owner)
    if isinstance(record, dict):
        if record.get('bridge_error') is None:
            record['bridge_error'] = reason
        reason = record['bridge_error']
    return dict(phase='campaign_review', objective='Wait.', available_actions=['wait'],
                review_reason='battle_medicine_bridge_' + reason), step_id


def _sdk_constants():
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    return constants


def _fixed_intent(intent):
    for expected in (bm.HYPER_POTION_INTENT, bm.FULL_HEAL_INTENT):
        if _exact(intent, expected):
            return deepcopy(expected)
    return None


def _clock(value):
    return type(value) in (int,float) and math.isfinite(value) and value >= 0


def _repair_marker(value):
    return (type(value) is dict and set(value)=={'kind','owner','frame','error'}
            and value['kind']=='native_hp_bar_animation_v1'
            and type(value['owner']) is str and 1 <= len(value['owner']) <= 128
            and _int(value['frame']) and value['error']=='medicine_receipt_unknown')


def _frame_clock(record,controller,owner,frame):
    anchor=record.get('reviewed_frame_clock')
    repair=record.get('reviewed_hp_animation_repair')
    if (type(anchor) is not dict or set(anchor)!= {'owner','frame','now'}
            or anchor['owner']!=owner or not _int(anchor['frame'])
            or not _clock(anchor['now']) or frame < anchor['frame']
            or type(repair) is not dict or not _repair_marker(repair.get('marker'))
            or repair['marker']['owner']!=owner or repair['marker']['frame']!=anchor['frame']
            or repair.get('anchor_now')!=anchor['now']):
        return None
    now=anchor['now']+(frame-anchor['frame'])/60
    return now if _clock(now) else None


def _signature(step_id, step):
    if (type(step) is not dict or step.get('kind') != 'interact'
            or type(step.get('map_id')) is not int or step['map_id'] != 166
            or type(step.get('target')) is not list or step['target'] != [3, 4]
            or any(type(v) is not int for v in step['target'])
            or step.get('face') != 'up' or step.get('event') != 'beat_blaine'
            or step.get('battle_supply') != SUPPLY
            or any(k in step for k in ('mechanic', 'next_map', 'terminal', 'item',
                                      'badge', 'await_script_event'))):
        return None
    return (step_id, 'interact', 166, (3, 4), 'up', 'beat_blaine', SUPPLY)


def applies(step_id, step):
    return bool(_active()) or bool(isinstance(step, dict) and step.get('battle_supply') == SUPPLY)


def _proof(snapshot, module, frame, location, *, enemy=False):
    if (type(snapshot) is not dict or snapshot.get('read_valid') is not True
            or snapshot.get('profile') != module.PROFILE
            or snapshot.get('source_commit') != SOURCE_COMMIT
            or not _int(snapshot.get('observation_frame')) or snapshot['observation_frame'] != frame
            or snapshot.get('battle_kind') != 'trainer'
            or not _exact(snapshot.get('location'), location)):
        return False
    if enemy:
        return (all(_int(snapshot.get(k)) and snapshot[k] == frame
                    for k in ('frame_before', 'frame_after'))
                and type(snapshot.get('raw')) is int and snapshot['raw'] == 2
                and type(snapshot.get('battle_type')) is int and snapshot['battle_type'] == 0
                and type(snapshot.get('current_opponent')) is int
                and 0 <= snapshot['current_opponent'] <= 255
                and type(snapshot.get('raw_record')) is list and len(snapshot['raw_record']) == 29
                and all(type(v) is int and 0 <= v <= 255 for v in snapshot['raw_record']))
    return True


def context(pyboy, state, plan, step_id, text, previous, *, intent=None):
    """回傳 (子目標, 原step_id) 或 None；None且無active不接管。

    完成只表示此用藥 UI 交易閉合，不表示館戰勝利或下一回合存活安全。
    父層每次新用藥須顯式傳固定 intent；active 時 None 沿原交易繼續。
    """
    active = _active()
    if not active and intent is None:
        return None
    if len(active) > 1:
        return _review('multiple_active_owners', step_id)
    owner = next(iter(active), None)
    record = _BINDINGS.get(owner)
    controller = _CONTROLLERS.get(owner)
    if owner is not None and (type(record) is not dict or controller is None):
        return _review('controller_or_binding_lost', step_id, owner)
    if owner is not None and record.get('bridge_error') is not None:
        return _review(record['bridge_error'], step_id, owner)
    if type(step_id) is not str or not step_id:
        return _review('step_id_unverified', step_id, owner)
    if owner is not None and record['step_id'] != step_id:
        return _review('owner_step_changed', step_id, owner)
    if type(plan) is not dict or type(plan.get('steps')) is not list:
        return _review('plan_unverified', step_id, owner)
    matches = [s for s in plan['steps'] if isinstance(s, dict) and s.get('id') == step_id]
    if len(matches) != 1:
        return _review('unique_step_required', step_id, owner)
    signature = _signature(step_id, matches[0])
    if signature is None:
        return _review('fixed_battle_supply_step_required', step_id, owner)
    if owner is not None and not _exact(signature, record['signature']):
        return _review('bound_step_changed', step_id, owner)
    marker=matches[0].get('reviewed_medicine_repair')
    needs_repair=False
    if 'reviewed_medicine_repair' in matches[0]:
        if not _repair_marker(marker):
            return _review('reviewed_repair_marker_invalid',step_id,owner)
        prior=_BINDINGS.get(marker['owner'])
        receipt=prior.get('reviewed_hp_animation_repair') if type(prior) is dict else None
        consumed=type(receipt) is dict and _exact(receipt.get('marker'),marker)
        if consumed and (marker['owner']==owner or marker['owner'] in _COMPLETED):
            pass  # exact consumed marker is retained history, never another repair
        elif (owner is None or marker['owner']!=owner
                or record.get('reviewed_hp_animation_repair') is not None):
            return _review('reviewed_repair_owner_or_history_unverified',step_id,owner)
        else:
            needs_repair=True
    requested = _fixed_intent(intent) if intent is not None else None
    if intent is not None and requested is None:
        return _review('explicit_intent_unverified', step_id, owner)
    if owner is not None:
        if requested is not None and not _exact(requested, record['intent']):
            return _review('active_intent_changed', step_id, owner)
        expected = record['intent']
    else:
        expected = requested
    if type(state) is not dict or not _int(state.get('frame')):
        return _review('state_frame_unverified', step_id, owner)
    frame, location, battle = state['frame'], state.get('location'), state.get('battle_state')
    if not _exact(location, {'map_id': 166, 'x': 3, 'y': 4}):
        return _review('location_unverified', step_id, owner)
    if (type(battle) is not dict or battle.get('kind') != 'trainer' or battle.get('active') is not True
            or type(battle.get('raw')) is not int or battle['raw'] != 2
            or not _int(battle.get('observation_frame')) or battle['observation_frame'] != frame
            or type(battle.get('opponent_species')) is not str or not battle['opponent_species'].strip()):
        return _review('runtime_trainer_packet_unverified', step_id, owner)
    if type(previous) not in (list, tuple) or any(type(a) is not str or a not in _ACTIONS for a in previous):
        return _review('actual_previous_unverified', step_id, owner)
    progress = state.get('progress')
    if type(text) is not dict or type(progress) is not dict:
        return _review('original_text_progress_required', step_id, owner)
    if needs_repair and (marker['frame']!=frame or controller.owner!=owner
            or controller.last_frame!=frame or type(controller.last_frame) is not int
            or controller.error!=marker['error'] or controller.stage!='receipt'):
        return _review('reviewed_repair_state_unverified',step_id,owner)
    for packet in (text, progress):
        if 'observation_frame' in packet and (not _int(packet['observation_frame'])
                                              or packet['observation_frame'] != frame):
            return _review('packet_frame_disagrees', step_id, owner)
    if owner is None:
        owner = step_id + '-medicine-' + str(frame)
        if len(owner) > 128:
            return _review('owner_length_unverified', step_id)
        if owner in _COMPLETED or owner in _BINDINGS or owner in _CONTROLLERS:
            return _review('owner_already_used', step_id)
        completed_frames = []
        for completed_owner in _COMPLETED:
            old = _BINDINGS.get(completed_owner)
            if (type(old) is not dict or completed_owner not in _CONTROLLERS
                    or not _int(old.get('completed_frame')) or type(old.get('receipt')) is not dict):
                return _review('completed_receipt_lost', step_id)
            completed_frames.append(old['completed_frame'])
        if completed_frames and frame <= max(completed_frames):
            return _review('new_owner_requires_fresh_frame', step_id)
    try:
        constants = _sdk_constants()
        before = pyboy.frame_count
        player = player_battle.read_player_battle(pyboy, observation_frame=frame,
            expected_location=location, constants=constants, profile=player_battle.PROFILE)
        enemy = trainer_opponent.read_trainer_opponent(pyboy, observation_frame=frame,
            expected_location=location, constants=constants, profile=trainer_opponent.PROFILE)
        after = pyboy.frame_count
    except Exception:
        return _review('readonly_snapshot_failed', step_id, owner if record is not None else None)
    if not _int(before) or not _int(after) or before != frame or after != frame:
        return _review('snapshot_frame_changed', step_id, owner if record is not None else None)
    if not _proof(player, player_battle, frame, location):
        return _review('player_snapshot_unverified', step_id, owner if record is not None else None)
    if not _proof(enemy, trainer_opponent, frame, location, enemy=True):
        return _review('trainer_snapshot_unverified', step_id, owner if record is not None else None)
    now=None
    if not needs_repair:
        if record is not None and record.get('reviewed_frame_clock') is not None:
            now=_frame_clock(record,controller,owner,frame)
        else:
            now=time.monotonic()
        if not _clock(now):
            return _review('clock_unverified',step_id,owner if record is not None else None)
    if controller is None:
        try:
            controller = bm.BattleMedicineController(expected, owner=owner,
                max_calls=240, max_seconds=60, max_waits=30)
        except Exception:
            return _review('controller_constructor_failed', step_id)
        record = dict(step_id=step_id, signature=signature, intent=deepcopy(expected),
                      initial_frame=frame, bridge_error=None, receipt=None, completed_frame=None)
        _BINDINGS[owner], _CONTROLLERS[owner] = record, controller
    try:
        controller.__class__ = bm.BattleMedicineController
    except Exception:
        return _review('controller_class_unverified',step_id,owner)
    if needs_repair:
        anchor_now=controller.last_now
        if (not _clock(anchor_now) or not _clock(controller.started)
                or anchor_now < controller.started):
            return _review('reviewed_repair_clock_unverified',step_id,owner)
        saved=deepcopy({k:v for k,v in controller.__dict__.items() if k!='error'})
        try:
            repaired=controller.reviewed_hp_animation_repair(text,progress,
                player_snapshot=player,enemy_proof=enemy,frame=frame,owner=owner)
        except Exception:
            return _review('reviewed_repair_failed',step_id,owner)
        if (repaired is not True or controller.error is not None
                or not _exact(saved,{k:v for k,v in controller.__dict__.items() if k!='error'})):
            return _review('reviewed_repair_failed',step_id,owner)
        receipt=dict(marker=deepcopy(marker),anchor_now=anchor_now,
                     calls=controller.calls,waits=controller.waits,started=controller.started,
                     last_now=controller.last_now,stage=controller.stage,
                     source_commit=SOURCE_COMMIT,error_cleared='medicine_receipt_unknown')
        record['reviewed_hp_animation_repair']=receipt
        record['reviewed_frame_clock']=dict(owner=owner,frame=frame,now=anchor_now)
        return {**controller._hint('wait','reviewed_hp_animation_repair_recorded'),
                'battle_medicine_owner':owner,
                'battle_medicine_reviewed_repair':deepcopy(receipt)},step_id
    try:
        controller.__class__ = bm.BattleMedicineController
        result = controller.context(text, progress, owner=owner, location=location,
            battle_state=battle, player_snapshot=player, enemy_proof=enemy,
            frame=frame, previous=previous, now=now)
    except Exception:
        return _review('controller_context_failed', step_id, owner)
    if type(result) is not dict:
        return _review('controller_result_unverified', step_id, owner)
    if result.get('battle_medicine_complete') is True:
        record['receipt'], record['completed_frame'] = deepcopy(result), frame
        _COMPLETED.add(owner)
        result = {**result, 'field_move_complete': True, 'field_move_kind': 'battle-medicine'}
    elif result.get('field_move_complete') is True:
        return _review('controller_completion_unverified', step_id, owner)
    if record.get('reviewed_hp_animation_repair') is not None:
        result={**result,'battle_medicine_reviewed_repair':deepcopy(record['reviewed_hp_animation_repair'])}
    return {**result, 'battle_medicine_owner': owner}, step_id
