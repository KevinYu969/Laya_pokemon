"""Fixed five-case Route23 land-guard bridge; readonly getters and pure UI hints.

The parent must provide true previous actions and serialize all same-frame reads.
Registers, original controller/pending/error/baseline/budgets survive reload.
"""
import importlib
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

from . import route23_land_guards as guard
from . import route23_surf as surf
from .rocket_movement import read_rocket_movement

importlib.reload(guard)
MECHANIC = 'route23_land_guard'
_CONTROLLERS = globals().get('_CONTROLLERS', {})
_BINDINGS = globals().get('_BINDINGS', {})
_COMPLETED = globals().get('_COMPLETED', set())
_ERRORS = globals().get('_ERRORS', {})
_STEP_KEYS = {'id', 'kind', 'mechanic', 'map_id', 'target', 'guard_case', 'guard_intent'}
_PEERS = ('route23_bridge', 'battle_medicine_bridge', 'trainer_medicine_ui_bridge',
    'pallet_surf_bridge', 'route21_water_bridge', 'fly_viridian_bridge', 'fly_pallet_bridge',
    'player_pc_bridge', 'cinnabar_purchase_bridge', 'victory_strength_bridge',
    'victory_first_boulder_bridge', 'victory_later_boulders_bridge', 'safari_entry',
    'hm_teaching_bridge', 'vending_bridge', 'saffron_guard_bridge', 'silph_card_bridge',
    'lapras_bridge', 'mansion_native_landing', 'mansion_transition_ready',
    'mansion_statue_bridge', 'mansion_secret_key_bridge', 'campaign_transactions')


def _active():
    if (type(_CONTROLLERS) is not dict or type(_BINDINGS) is not dict
            or type(_COMPLETED) is not set or type(_ERRORS) is not dict):
        return None
    return (set(_CONTROLLERS) | set(_BINDINGS) | set(_ERRORS)) - _COMPLETED


def _review(reason, step_id):
    active = _active()
    owner = next(iter(active)) if active is not None and len(active) == 1 else step_id
    message = 'route23_land_guard_bridge_' + reason
    if type(_ERRORS) is dict and type(owner) is str and owner:
        _ERRORS.setdefault(owner, message)
        message = _ERRORS[owner]
    return dict(phase='campaign_review', objective='Wait.', available_actions=['wait'],
                review_reason=message, route23_land_guard_owner=owner), step_id


def applies(step_id, step):
    active = _active()
    return (active is None or bool(active) or step_id in _BINDINGS or step_id in _ERRORS
            or isinstance(step, dict) and step.get('mechanic') == MECHANIC)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _source_path():
    here = Path(__file__).resolve().parent
    allowed = ((here.name in ('staged-route23-land-guards-20261028','staged-route23-guard-eventfix-20261028') and here.parent.name == '.local')
               or (here.name == 'laya_pokemon' and here.parent.name == 'src'))
    return allowed and Path(guard.__file__).resolve() == here / 'route23_land_guards.py'


def _explicit(step):
    if (type(step) is not dict or set(step) != _STEP_KEYS or step.get('kind') != 'interact'
            or step.get('mechanic') != MECHANIC or type(step.get('map_id')) is not int or step['map_id'] != 34
            or type(step.get('guard_case')) is not str or step['guard_case'] not in guard.CASES
            or not guard._intent(step.get('guard_intent')) or step['guard_intent']['case'] != step['guard_case']):
        return None
    case = guard.CASES[step['guard_case']]
    if (type(step.get('target')) is not list or len(step['target']) != 2
            or any(type(v) is not int for v in step['target']) or step['target'] != [case['x'], case['y']]):
        return None
    return case, step['guard_intent']


def _peer_conflict():
    for name in _PEERS:
        module = sys.modules.get('laya_pokemon.' + name)
        if module is None:
            continue
        bindings = getattr(module, '_BINDINGS', {})
        controllers = getattr(module, '_CONTROLLERS', {})
        completed = getattr(module, '_COMPLETED', set())
        if type(bindings) is not dict or type(controllers) is not dict or type(completed) is not set:
            return name + '_registry_unknown'
        if (set(bindings) | set(controllers)) - completed:
            return name + '_active'
    safari = sys.modules.get('laya_pokemon.safari_entry')
    if safari is not None and getattr(safari, '_RUN_CONTROLLER', None) is not None:
        return 'safari_run_active'
    capture = sys.modules.get('laya_pokemon.capture_transaction')
    if capture is not None:
        sessions = getattr(capture, '_SESSIONS', None)
        if type(sessions) is not dict:
            return 'capture_registry_unknown'
        if any(type(s) is not dict or s.get('done') is not True for s in sessions.values()):
            return 'capture_active'
    return None


def context(pyboy, state, plan, step_id, text, grid, previous):
    active = _active()
    if active is None:
        return _review('registries_unknown', step_id)
    if type(step_id) is not str or not step_id:
        return _review('step_id_unverified', step_id)
    if active and active != {step_id}:
        return _review('owner_changed', step_id)
    review_capsule=plan.get('route23_guard_event_review') if isinstance(plan,dict) else None
    reviewed_error='route23_land_guard_event_before_final_actual_a'
    if step_id in _ERRORS and not (_ERRORS[step_id]==reviewed_error and review_capsule is not None):
        return _review('sticky', step_id)
    if not _source_path():
        return _review('pure_source_path_unverified', step_id)
    if not isinstance(plan, dict) or type(plan.get('steps')) is not list:
        return _review('plan_unverified', step_id)
    ids = [s.get('id') if isinstance(s, dict) else None for s in plan['steps']]
    if any(type(i) is not str or not i for i in ids) or len(set(ids)) != len(ids):
        return _review('plan_ids_unverified', step_id)
    if step_id not in ids:
        return _review('step_missing', step_id) if active or step_id in _BINDINGS else None
    step = plan['steps'][ids.index(step_id)]
    if step.get('mechanic') != MECHANIC:
        return _review('intent_removed', step_id) if active or step_id in _BINDINGS else None
    explicit = _explicit(step)
    if explicit is None:
        return _review('explicit_fixed_intent_unverified', step_id)
    case, intent = explicit
    try:
        if plan.get('training_job') is None:
            raise ValueError('missing job')
        binding = (_canonical(step), _canonical(plan['training_job']))
    except (TypeError, ValueError):
        return _review('job_owner_unverified', step_id)
    if step_id in _BINDINGS and _BINDINGS[step_id] != binding:
        return _review('immutable_owner_or_intent_changed', step_id)
    controller = _CONTROLLERS.get(step_id)
    if step_id in _BINDINGS and controller is None:
        return _review('original_controller_missing', step_id)
    if (controller is not None or step_id in _COMPLETED) and step_id not in _BINDINGS:
        return _review('original_binding_missing', step_id)
    if step_id in _COMPLETED:
        return _review('completed_step_reentered', step_id)
    if not isinstance(state, dict):
        return _review('state_unverified', step_id)
    frame = state.get('frame')
    position = guard._position(state.get('location'))
    if not guard._int(frame) or position is None:
        return _review('frame_or_location_unverified', step_id)
    start = (34, case['x'], case['y'])
    if controller is None and position != start:
        return None
    conflict = _peer_conflict()
    if conflict:
        return _review('peer_transaction_' + conflict, step_id)
    if controller is None:
        controller = guard.Route23LandGuardController(intent)
        _CONTROLLERS[step_id] = controller
        _BINDINGS[step_id] = binding
    controller.__class__ = guard.Route23LandGuardController
    try:
        from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
        signal = surf.read_surf_observation(pyboy, frame, sdk)
        movement = read_rocket_movement(pyboy, observation_frame=frame)
    except Exception:
        return _review('readonly_getter_failed', step_id)
    if step_id in _ERRORS:
        if (type(review_capsule) is not dict or review_capsule.get('step_id') != step_id
                or review_capsule.get('step_sha256') != sha256(_canonical(step).encode('utf-8')).hexdigest()
                or review_capsule.get('job_sha256') != sha256(_canonical(plan['training_job']).encode('utf-8')).hexdigest()):
            return _review('reviewed_event_binding_unverified',step_id)
        result=controller.restore_reviewed_event_order({**state,'text':text},grid=grid,signal=signal,
            movement=movement,previous=previous,capsule=review_capsule)
        if result is None:return _review('reviewed_event_source_packet_unverified',step_id)
        history=globals().setdefault('_REVIEWED_ERRORS',{})
        history.setdefault(step_id,[]).append(dict(error=_ERRORS[step_id],capsule=review_capsule.copy()))
        del _ERRORS[step_id]  # Exact bound named repair only; never a generic error clear.
        return result,step_id
    now=time.monotonic()
    if getattr(controller,'reviewed_error_history',None):
        # Continue the original clock by real advanced frames, excluding the engineering pause.
        last_now,last_frame=controller.last_now,controller.last_frame
        now=(last_now+(frame-last_frame)/60 if type(last_now) in (int,float)
             and type(last_frame) is int and frame>=last_frame else float('nan'))
    result = controller.context({**state, 'text':text}, grid=grid, signal=signal,
        movement=movement, previous=previous, now=now)
    if not isinstance(result, dict):
        return _review('pure_result_unverified', step_id)
    if controller.error is not None or result.get('phase') == 'campaign_review':
        _ERRORS.setdefault(step_id, controller.error or result.get('review_reason') or 'route23_land_guard_bridge_pure_review')
        return {**result, 'route23_land_guard_owner':step_id}, step_id
    if result.get('route23_land_guard_complete') is True:
        closed = getattr(controller, 'closed_frames', None)
        offered, ack = getattr(controller, 'final_offer_frame', None), getattr(controller, 'final_ack_frame', None)
        if (position != start or not guard._source_signal(signal, start, frame)
                or signal['route23_script'] != 0 or signal['guard_flags'] != getattr(controller, 'expected_flags', None)
                or getattr(controller, 'expected_flags', None) != getattr(controller, 'flags', 128) | (1 << case['bit'])
                or controller.intent != intent or controller.contract != intent
                or controller.page != 3 or controller.stage != 'complete' or controller.pending is not None
                or controller.final_ack is not True or not guard._int(offered) or not guard._int(ack) or not offered < ack
                or getattr(controller, 'event_seen', None) is not True
                or not guard._int(getattr(controller, 'done_frame', None)) or not controller.done_frame < offered
                or type(getattr(controller, 'flags', None)) is not int or not 0 <= controller.flags < 128
                or controller.flags & (1 << case['bit']) or getattr(controller, 'fingerprint', None) is None
                or type(closed) is not list or len(closed) < 2 or any(not guard._int(f) for f in closed)
                or not ack <= closed[-2] < closed[-1] == frame
                or surf._idle(movement, frame) is not True or surf._rows(text) != surf._blank()
                or text.get('window_visible') is not False or not guard._world(grid, intent['case'], frame)
                or guard._fingerprint(state.get('progress')) != controller.fingerprint):
            return _review('completion_native_receipt_unverified', step_id)
        _COMPLETED.add(step_id)
        result = {**result, 'field_move_complete':True, 'field_move_kind':'route23-land-guard',
                  'route23_land_guard_owner':step_id}
        index = ids.index(step_id) + 1
        return result, ids[index] if index < len(ids) else 'complete'
    return {**result, 'route23_land_guard_owner':step_id}, step_id
