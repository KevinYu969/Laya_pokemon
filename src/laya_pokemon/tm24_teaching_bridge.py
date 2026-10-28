"""唯一聯盟TM24 step 的同幀唯讀橋接；registry獨立於既有HM。"""
from copy import deepcopy
import importlib

from . import tm24_teaching
from .rocket_movement import read_rocket_movement
importlib.reload(tm24_teaching)

_BINDINGS = globals().get('_BINDINGS', {})
_CONTROLLERS = globals().get('_CONTROLLERS', {})
_OWNERS = globals().get('_OWNERS', {})
_COMPLETED = globals().get('_COMPLETED', set())
_ERRORS = globals().get('_ERRORS', {})
_CONTROLLER_TYPES = globals().get('_CONTROLLER_TYPES', ())
if type(_CONTROLLER_TYPES) is tuple and all(isinstance(cls, type) for cls in _CONTROLLER_TYPES):
    _CONTROLLER_TYPES = tuple(dict.fromkeys((*_CONTROLLER_TYPES, tm24_teaching.TM24TeachingController)))
JOB = 'league27-lapras-thunderbolt-20261028'
MECHANIC = 'lapras_tm24'
MECHANICS = frozenset((MECHANIC,))
GRID_SOURCE = 'wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM'
_CORRUPT_OWNER = 'tm24-invalid-registry'


def _keys(registry):
    if type(registry) is not dict or any(type(k) is not str or not k for k in registry):
        return {_CORRUPT_OWNER}
    return set(registry)


def _active():
    """Orphan controllers/owners and every sticky error still reserve ownership."""
    keys = _keys(_BINDINGS) | _keys(_CONTROLLERS) | _keys(_OWNERS)
    if type(_COMPLETED) is not set or any(type(k) is not str or not k for k in _COMPLETED):
        return keys | _keys(_ERRORS) | {_CORRUPT_OWNER}
    if _registry_problem():
        return keys | _keys(_ERRORS) or {_CORRUPT_OWNER}
    return (keys - _COMPLETED) | _keys(_ERRORS)


def applies(step_id, step):
    return bool(_active()) or step_id in _keys(_BINDINGS) or bool(
        isinstance(step, dict) and step.get('mechanic') in MECHANICS)


def _known_controller(controller):
    return (type(_CONTROLLER_TYPES) is tuple
            and all(isinstance(cls, type) and cls.__module__ == tm24_teaching.__name__
                    and cls.__name__ == 'TM24TeachingController' for cls in _CONTROLLER_TYPES)
            and type(controller) in _CONTROLLER_TYPES)


def _review(owner, reason):
    reason = 'tm24_bridge_' + reason.removeprefix('tm24_bridge_')
    if type(_ERRORS) is dict:
        original = _ERRORS.setdefault(owner, reason)
        if type(original) is str:
            reason = original
    controller = _CONTROLLERS.get(owner) if type(_CONTROLLERS) is dict else None
    if _known_controller(controller):
        return controller.fail(reason), owner
    return dict(phase='campaign_review', objective='Wait.', available_actions=['wait'], review_reason=reason), owner


def _valid_step(step):
    return (type(step) is dict
            and set(step) == {'id', 'kind', 'mechanic', 'map_id', 'target', 'teaching_intent'}
            and type(step.get('id')) is str and bool(step['id'])
            and step.get('kind') == 'interact' and step.get('mechanic') == 'lapras_tm24'
            and type(step.get('map_id')) is int and step['map_id'] == 174
            and type(step.get('target')) is list and len(step['target']) == 2
            and all(type(v) is int and v == 7 for v in step['target'])
            and tm24_teaching._intent(step.get('teaching_intent')))


def _registry_problem():
    registries = (_BINDINGS, _CONTROLLERS, _OWNERS, _ERRORS)
    if (any(type(r) is not dict or any(type(k) is not str or not k for k in r) for r in registries)
            or type(_COMPLETED) is not set
            or any(type(k) is not str or not k for k in _COMPLETED)):
        return 'typed_registry_invalid'
    if (type(_CONTROLLER_TYPES) is not tuple or not _CONTROLLER_TYPES
            or any(not isinstance(cls, type) or cls.__module__ != tm24_teaching.__name__
                   or cls.__name__ != 'TM24TeachingController' for cls in _CONTROLLER_TYPES)):
        return 'typed_controller_class_registry_invalid'
    keys = set(_BINDINGS)
    if keys != set(_CONTROLLERS) or keys != set(_OWNERS) or not _COMPLETED <= keys:
        return 'binding_controller_or_owner_missing_or_orphaned'
    if any(type(value) is not str or not value.startswith('tm24_') for value in _ERRORS.values()):
        return 'typed_error_registry_invalid'
    for owner in keys:
        binding, record, controller = _BINDINGS[owner], _OWNERS[owner], _CONTROLLERS[owner]
        if (type(binding) is not dict or set(binding) != {'step', 'job'}
                or not _valid_step(binding['step']) or binding['step']['id'] != owner
                or type(binding['job']) is not str or binding['job'] != JOB
                or not _known_controller(controller)
                or type(record) is not dict or set(record) != {'pyboy', 'controller'}
                or record['pyboy'] is None or record['controller'] is not controller):
            return 'typed_binding_controller_or_owner_invalid'
    return None


def _world_ready(text, grid, frame):
    if type(grid) is not dict or grid.get('source') != GRID_SOURCE:
        return False
    if (type(grid.get('observation_frame')) is not int or grid['observation_frame'] != frame
            or type(grid.get('verified_location')) is not list
            or any(type(v) is not int for v in grid['verified_location'])
            or grid['verified_location'] != [174, 7, 7]
            or type(grid.get('screen_cells_verified')) is not int or grid['screen_cells_verified'] < 12):
        return False
    cells, walkable, tiles = (grid.get(k) for k in ('visible_verified_cells', 'walkable', 'tiles'))
    if (type(walkable) is not list or len(walkable) <= 7 or type(walkable[0]) is not list
            or len(walkable[0]) <= 7 or type(tiles) is not list or len(tiles) != len(walkable)):
        return False
    width = len(walkable[0])
    if (any(type(row) is not list or len(row) != width
            or any(type(v) is not int or v not in (0, 1) for v in row) for row in walkable)
            or any(type(row) is not list or len(row) != width
                   or any(type(v) is not int or not 0 <= v <= 255 for v in row) for row in tiles)
            or walkable[7][7] != 1):
        return False
    return (type(cells) is list and len(cells) == grid['screen_cells_verified']
            and all(type(p) is list and len(p) == 2
                    and all(type(v) is int and v >= 0 for v in p)
                    and p[0] < width and p[1] < len(walkable) for p in cells)
            and len({tuple(p) for p in cells}) == len(cells) and [7, 7] in cells
            and text.get('window_visible') is False
            and tm24_teaching._rows(text) == (' ' * 20,) * 18)


def _completion_valid(controller, state, text, grid, movement, frame, original_pending, result):
    if (original_pending is not None or controller.pending is not None or controller.error is not None
            or controller.stage != 'complete' or controller.learned_acked is not True or controller.consumed is not True
            or type(controller.last_frame) is not int or controller.last_frame != frame
            or type(controller.closed_frame) is not int or not controller.closed_frame < frame
            or result.get('first_closed_observation_frame') != controller.closed_frame
            or type(result.get('first_closed_observation_frame')) is not int
            or result.get('closed_observation_frame') != frame or type(result.get('closed_observation_frame')) is not int
            or result.get('quantity_used') != 1 or type(result.get('quantity_used')) is not int
            or result.get('item') != 224 or type(result.get('item')) is not int
            or result.get('machine_kind') != 'TM' or result.get('moves_verified') != [57,34,58,85]
            or result.get('new_move_pp') != 15 or type(result.get('new_move_pp')) is not int
            or not tm24_teaching._intent(controller.intent)
            or not _world_ready(text, grid, frame) or not tm24_teaching._idle(movement, frame)):
        return False
    try:
        before = controller.party_before
        target = controller.target_index
        if (type(before) is not list or len(before) != 6 or type(target) is not int
                or not 0 <= target < 6 or before[target]['species'] != 19
                or before[target]['moves'] != [57,34,58,109]
                or type(controller.inventory_before) is not list
                or controller.inventory_before.count((224, 1)) != 1):
            return False
        expected_party = deepcopy(before)
        expected_party[target]['moves'] = [57,34,58,85]
        expected_party[target]['pp'] = before[target]['pp'][:3] + [15]
        expected_bag = [item for item in controller.inventory_before if item[0] != 224]
        progress = state['progress']
        bag = [] if progress.get('inventory') == [] else tm24_teaching._inventory(progress.get('inventory'))
        return (controller.inventory_after == expected_bag and bag == expected_bag
                and progress.get('party') == expected_party and type(progress.get('party_count')) is int
                and progress['party_count'] == 6 and progress.get('party_read_valid') is True
                and progress.get('initialization_candidate') is True
                and type(progress.get('money')) is int and progress['money'] == controller.money_before
                and progress.get('player_name_raw') == controller.player_name)
    except (KeyError, IndexError, TypeError, AttributeError):
        return False


def context(pyboy, state, plan, step_id, text, grid, previous, *, peer_owners=None, now=None):
    """Root須先掃全部peer。只讀frame/movement；default now只累積真frame/60。"""
    active = _active()
    owner = next(iter(sorted(active))) if active and active != {step_id} else step_id
    problem = _registry_problem()
    if problem:
        return _review(owner, problem)
    if active and active != {step_id}:
        return _review(owner, 'owner_changed')
    if owner in _ERRORS:
        return _review(owner, _ERRORS[owner])
    if (type(plan) is not dict or type(plan.get('steps')) is not list
            or len([s for s in plan['steps'] if type(s) is dict and s.get('id') == step_id]) != 1):
        return _review(owner, 'original_step_missing_or_ambiguous')
    step = next(s for s in plan['steps'] if type(s) is dict and s.get('id') == step_id)
    if not applies(step_id, step):
        return None
    if not _valid_step(step) or plan.get('training_job') != JOB or type(plan.get('training_job')) is not str:
        return _review(owner, 'fixed_complete_step_or_job_invalid')
    binding = dict(step=deepcopy(step), job=deepcopy(plan['training_job']))
    if owner in _BINDINGS and _BINDINGS[owner] != binding:
        return _review(owner, 'original_complete_step_or_job_changed')
    if not isinstance(peer_owners, (list, tuple, set, frozenset)) or peer_owners:
        return _review(owner, 'peer_owner_proof_missing_or_not_empty')
    if owner in _OWNERS and _OWNERS[owner]['pyboy'] is not pyboy:
        return _review(owner, 'original_pyboy_identity_changed')
    if owner not in _BINDINGS:
        controller = tm24_teaching.TM24TeachingController(step['teaching_intent'])
        _BINDINGS[owner], _CONTROLLERS[owner] = binding, controller
        _OWNERS[owner] = dict(pyboy=pyboy, controller=controller)
    controller = _CONTROLLERS[owner]
    controller.__class__ = tm24_teaching.TM24TeachingController
    if type(state) is not dict:
        return _review(owner, 'state_invalid')
    frame = state.get('frame')
    try:
        before = pyboy.frame_count
        if type(frame) is not int or type(before) is not int or frame != before:
            return _review(owner, 'observation_frame_not_current')
        for packet in (text, state.get('progress'), state.get('location'), state.get('battle_state')):
            if (not isinstance(packet, dict) or 'observation_frame' in packet and (
                    type(packet['observation_frame']) is not int or packet['observation_frame'] != frame)):
                return _review(owner, 'packet_frame_conflict')
        battle = state['battle_state']
        if type(battle.get('observation_frame')) is not int or battle['observation_frame'] != frame:
            return _review(owner, 'battle_frame_required')
        if grid is not None and (not isinstance(grid, dict)
                or type(grid.get('observation_frame')) is not int or grid['observation_frame'] != frame):
            return _review(owner, 'grid_frame_conflict')
        movement = read_rocket_movement(pyboy, observation_frame=frame)
        after = pyboy.frame_count
    except Exception:
        return _review(owner, 'readonly_getter_failed')
    if type(after) is not int or after != before:
        return _review(owner, 'frame_changed_during_read')
    if now is None:
        now = (0.0 if controller.last_now is None and controller.last_frame is None else
               controller.last_now + (frame - controller.last_frame) / 60)
    original_pending = deepcopy(controller.pending)
    result = controller.context(text, state['progress'], location=state['location'],
        battle_state=battle, movement=movement, frame=frame, now=now,
        overworld_ready=_world_ready(text, grid, frame), previous=previous)
    if result.get('tm24_complete') is True:
        if not _completion_valid(controller, state, text, grid, movement, frame, original_pending, result):
            return _review(owner, 'completion_receipt_or_closed_world_invalid')
        _COMPLETED.add(owner)
        index = plan['steps'].index(step) + 1
        return dict(result, field_move_complete=True, field_move_kind='lapras-tm24'), (
            plan['steps'][index]['id'] if index < len(plan['steps']) else 'complete')
    return result, owner
