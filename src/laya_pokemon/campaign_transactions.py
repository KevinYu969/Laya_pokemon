"""已明確指定的正常禮物／TM選單橋接；只讀取觀測並提供Laya子目標。"""
import importlib

from . import gift_eevee, teach_bubblebeam

importlib.reload(gift_eevee)
importlib.reload(teach_bubblebeam)
_CONTROLLERS = globals().get('_CONTROLLERS', {})
_BINDINGS = globals().get('_BINDINGS', {})
_TURNS = globals().get('_TURNS', {})
_COMPLETED = globals().get('_COMPLETED', set())
_COMPLETED.update(k for k,c in _CONTROLLERS.items() if getattr(c,'stage',None)=='complete')
SUPPORTED = {'gift_eevee', 'teach_bubblebeam'}


def _review(reason):
    return {'phase': 'campaign_review', 'review_reason': reason,
            'objective': 'Wait.', 'available_actions': ['wait']}


def applies(step_id, step):
    return bool(set(_BINDINGS)-_COMPLETED) or step_id in _BINDINGS or bool(step and 'mechanic' in step)


def ui_overworld_ready(text, grid):
    """背景格網可在Window選單後方成立；必須另外排除實際可見UI。"""
    rows=gift_eevee._rows(text)
    if grid is None or rows is None:
        return False
    if any(c in ''.join(rows) for c in ('▶','▷','▼')) or ''.join(rows[12:18]).strip():
        return False
    labels={'POKÉDEX','POKÉMON','POKEDEX','POKEMON','ITEM','SAVE','OPTION','EXIT','USE','TOSS','CANCEL'}
    return not any(row.strip() in labels for row in rows)


def context(pyboy, state, plan, step_id, text, grid):
    """僅kind=interact且明確mechanic的單一步驟可接管；不傳送或執行按鍵。"""
    active = set(_BINDINGS)-_COMPLETED
    if active and active != {step_id}:
        return _review('unfinished_transaction_step_changed'), step_id
    step = next((s for s in plan['steps'] if s['id'] == step_id), None)
    if step_id in _BINDINGS and (not step or 'mechanic' not in step):
        return _review('transaction_intent_changed'), step_id
    if not step or 'mechanic' not in step:
        return None
    mechanic = step['mechanic']
    if step['kind'] != 'interact' or mechanic not in SUPPORTED:
        return _review('unsupported_explicit_transaction'), step_id
    binding = (mechanic, step['map_id'], tuple(step['target']))
    if step_id in _BINDINGS and _BINDINGS[step_id] != binding:
        return _review('transaction_intent_changed'), step_id
    loc = dict(state['location'])
    if loc['map_id'] != step['map_id'] or [loc['x'], loc['y']] != step['target']:
        if step_id in _BINDINGS:
            return _review('transaction_location_changed'), step_id
        return None
    battle = state.get('battle_state', {})
    if battle.get('kind') != 'none' or battle.get('active') is not False:
        return _review('transaction_nonbattle_signal_conflict'), step_id
    loc['facing'] = {0: 'down', 4: 'up', 8: 'left', 12: 'right'}.get(int(pyboy.memory[0xC109]))
    ready=ui_overworld_ready(text,grid)
    controller = _CONTROLLERS.get(step_id)
    if controller is not None:
        revision=step.get('reviewed_controller_revision',0)
        if (type(revision) is int and revision>getattr(controller,'_reviewed_revision',0)
                and controller.error is not None and controller.error==step.get('reviewed_controller_error')):
            controller.error=None
            controller._reviewed_revision=revision
    delegated_review = None
    if state.get('phase') in {'strategy_review', 'campaign_review', 'review'}:
        # 泛用自然學招分類器不認得TM教學；只有已開始、已綁定的專用TM
        # 可以接這兩種guard，仍由其完整來源文字／基線檢查決定是否送鍵。
        reason = state.get('review_reason', 'transaction_preexisting_review')
        if (state['phase']=='strategy_review' and mechanic=='teach_bubblebeam'
                and controller is not None and getattr(controller,'stage','initial')!='initial'
                and reason in {'learning_case_not_verified','forget_move_menu_requires_live_calibration'}):
            delegated_review = reason
        else:
            return _review(reason), step_id
    if mechanic == 'gift_eevee':
        if controller is None and loc['facing'] != 'left':
            if not ready or state.get('phase') not in {'unclassified', 'overworld'}:
                return _review('gift_turn_requires_verified_overworld'), step_id
            rows = gift_eevee._rows(text)
            error = gift_eevee.initial_screen_error(rows, True)
            if error:
                return _review(error), step_id
            _BINDINGS[step_id] = binding
            _TURNS[step_id] = _TURNS.get(step_id, 0) + 1
            if _TURNS[step_id] > 3:
                return _review('gift_turn_budget_exhausted'), step_id
            return {'phase': 'gift_menu', 'objective': 'Move LEFT.',
                    'available_actions': ['left', 'wait'],
                    'controller_menu_verified': True}, step_id
        if controller is None:
            controller = gift_eevee.EeveeGiftController()
            _CONTROLLERS[step_id] = controller
            _BINDINGS[step_id] = binding
        controller.__class__ = gift_eevee.EeveeGiftController
        hidden = gift_eevee.gift_removed_flag(int(pyboy.memory[gift_eevee.GIFT_REMOVED_FLAG_ADDRESS]))
        result = controller.context(text, state['progress'], location=loc,
                                    overworld_ready=ready,
                                    gift_object_hidden=hidden, battle_active=False)
        done = result.get('gift_eevee_complete') is True
    else:
        if controller is None:
            controller = teach_bubblebeam.BubbleBeamController(teach_bubblebeam.INTENT)
            _CONTROLLERS[step_id] = controller
            _BINDINGS[step_id] = binding
        controller.__class__ = teach_bubblebeam.BubbleBeamController
        result = controller.context(text, state['progress'], overworld_ready=ready,
                                    battle_active=False)
        done = result.get('tm_teaching_complete') is True
    next_id = step_id
    if delegated_review:
        result = {**result, 'delegated_generic_learning_guard': delegated_review}
    if done:
        _COMPLETED.add(step_id)
        result = {**result, 'field_move_complete': True, 'field_move_kind': mechanic}
        index = plan['steps'].index(step) + 1
        next_id = plan['steps'][index]['id'] if index < len(plan['steps']) else 'complete'
    return result, next_id
