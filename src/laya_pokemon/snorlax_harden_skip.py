"""卡比獸41級自然略過變硬；純觀測回子目標，不讀寫模擬器。

固定原生路徑：Delete選NO、Abandon選YES、DidNotLearn的cont頁後關閉。
保留完整六人基線；未知文字、舊招選單或資料漂移都鎖定review。
"""
from copy import deepcopy
import re

from .mart_purchase import _party
from .observation import PROFILE as TEXT_PROFILE
from .party_control import command
from .team_strategy import learn_move_plan, normalize, reference

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCES = [f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/{p}' for p in (
    'data/pokemon/evos_moves.asm', 'engine/pokemon/learn_move.asm',
    'data/text/text_4.asm', 'engine/menus/text_box.asm', 'data/yes_no_menu_strings.asm',
    'engine/battle/core.asm', 'data/text/text_2.asm', 'data/trainers/parties.asm')]
MOVES = [70, 133, 156, 34]
MAX_SAFE_WAITS = 30
_SESSION = globals().get('_SESSION')
_INTRO = ('SNORLAXISTRYINGTOLEARN', 'SNORLAXISTRYINGTOLEARNHARDEN',
          'TRYINGTOLEARNHARDEN', 'HARDEN', 'BUTSNORLAXCANTLEARNMORE',
          'BUTSNORLAXCANTLEARNMORETHAN4MOVES', 'CANTLEARNMORETHAN4MOVES', 'THAN4MOVES')
_DELETE = ('DELETEANOLDERMOVETOMAKEROOM', 'DELETEANOLDERMOVETOMAKEROOMFORHARDEN',
           'MOVETOMAKEROOMFORHARDEN', 'FORHARDEN')
_ABANDON = ('ABANDONLEARNINGHARDEN',)
_PREFIX = 'SNORLAXDIDNOTLEARN'
_RESULT = ('DIDNOTLEARNHARDEN', 'HARDEN')
_NEXT_TRAINER_LINE, _NEXT_MON_LINE = 'GIOVANNI SENT', 'OUT RHYHORN!'
_ABOUT_TRAINER_LINE, _ABOUT_ACTION_LINE = 'GIOVANNI IS', 'ABOUT TO USE'


def _rows(text):
    """保留20個實體tile；只在底部正文展開SDK 0xBE的合法單tile縮寫't。"""
    cells = text.get('cells') if isinstance(text, dict) else None
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(row, (list, tuple)) or len(row) != 20 for row in cells)):
        return None
    for y, row in enumerate(cells):
        if any(not isinstance(c, str) or not (len(c) == 1 or y >= 12 and c == "'t") for c in row):
            return None
    return tuple(''.join(row).upper() for row in cells)


def _decoder_verified(text, window):
    return (text.get('profile') == TEXT_PROFILE and text.get('read_valid') is True
            and text.get('alignment_verified') is True and text.get('read_error') is None
            and text.get('window_visible') is window)


def _reviewed_token_recovery(text, progress, rows, compact):
    """僅解除已人工審查的intro縮寫誤停；不清其他錯誤、不重設原WAIT額度。"""
    if (_SESSION.get('error') != 'text_unreadable' or _SESSION.get('stage') != 'intro'
            or _SESSION.get('seen_move') is not True
            or _SESSION.get('delete_no') is not False or _SESSION.get('abandon_yes') is not False
            or _SESSION.get('result_prefix') is not False or 'reviewed_token_migration' in _SESSION
            or not _decoder_verified(text, True)
            or not any(c == "'t" for row in text['cells'][12:] for c in row)
            or not compact.startswith('BUTSNORLAXCANT')
            or not _prefix(compact, ('BUTSNORLAXCANTLEARNMORE', 'BUTSNORLAXCANTLEARNMORETHAN4MOVES'))
            or any(re.search(r'(?<![A-Z])(?:YES|NO)(?![A-Z])|▶|▷|▼', row) for row in rows)
            or any(re.search(r'[A-ZÉ0-9!?]', rows[y]) for y in (12, 13, 15, 17))
            or any(re.search(r'[A-ZÉ0-9!?]', text['cells'][y][x])
                   for y in (14, 16) for x in (0, 19))):
        return
    party = _party(progress)
    if party is None or len(party) != 6 or party != _SESSION.get('party'):
        return
    _SESSION['error'] = None
    _SESSION['reviewed_token_migration'] = {
        'cleared_error': 'text_unreadable', 'allowed_single_tile_token': "'t", 'sdk_byte': 0xBE,
        'verified_page_prefix': compact, 'stage': 'intro', 'party_unchanged': True,
        'no_selection_requested': True, 'wait_budget_preserved': True, 'recovery_action': 'wait_only'}


def _post_skip_sendout(text, progress, rows, *, about=False):
    """僅本次Silph坂木原生下一隻提示；不聲稱API能讀取battle_state。"""
    if (not _decoder_verified(text, True) or _SESSION.get('stage') != 'complete'
            or any(_SESSION.get(k) is not True for k in ('seen_move', 'delete_no', 'abandon_yes', 'result_prefix'))
            or _party(progress) != _SESSION.get('party')):
        return None
    events = progress.get('story_event_bits')
    if (not isinstance(events, dict) or events.get('beat_silph_co_rival') is not True
            or events.get('silph_co_11_unlocked_door') is not True
            or events.get('beat_silph_co_giovanni') is not False
            or any(re.search(r'(?<![A-Z])(?:YES|NO)(?![A-Z])|▶|▷', row) for row in rows)
            or any(re.search(r'[A-ZÉ0-9!?]', rows[y]) for y in (12, 13, 15, 17))
            or any(re.search(r'[A-ZÉ0-9!?]', text['cells'][y][x])
                   for y in (14, 16) for x in (0, 19))
            or any(c == "'t" for row in text['cells'][12:] for c in row)):
        return None
    first = rows[14][1:19].replace('▼', ' ').rstrip()
    second = rows[16][1:19].replace('▼', ' ').rstrip()
    arrows = [(x, y) for y, row in enumerate(text['cells']) for x, c in enumerate(row) if c == '▼']
    trainer_line = _ABOUT_TRAINER_LINE if about else _NEXT_TRAINER_LINE
    action_line = _ABOUT_ACTION_LINE if about else _NEXT_MON_LINE
    if (not first or not trainer_line.startswith(first)
            or arrows not in ([], [(18, 16)]) or arrows and not about):
        return None
    if first != trainer_line:
        return 'partial' if not second and not arrows else None
    if not action_line.startswith(second):
        return None
    if second != action_line:
        return 'partial' if not arrows else None
    if about:
        return 'full' if arrows == [(18, 16)] else 'partial'
    return 'full'


def _reviewed_post_skip_recovery(text, progress, rows):
    """只解已審查的完成後交棒誤停；保留原party／WAIT計數與早先縮寫稽核。"""
    if (_SESSION.get('error') == 'closed_after_skip_unverified'
            and 'reviewed_post_skip_migration' not in _SESSION
            and _post_skip_sendout(text, progress, rows) is not None):
        _SESSION['error'] = None
        _SESSION['reviewed_post_skip_migration'] = {
            'cleared_error': 'closed_after_skip_unverified', 'verified_stage': 'complete',
            'delete_no_and_abandon_yes_requested': True, 'did_not_learn_prefix_observed': True,
            'party_unchanged': True, 'wait_budget_preserved': True,
            'next_source_message': 'GIOVANNI sent / out RHYHORN!',
            'partial_action': 'wait_only', 'full_action': 'handoff_no_button'}


def _reviewed_about_recovery(text, progress, rows):
    """第二次具名校準：保留第一次SendOut假設的歷史及原WAIT預算。"""
    if (_SESSION.get('error') == 'closed_after_skip_unverified'
            and isinstance(_SESSION.get('reviewed_post_skip_migration'), dict)
            and 'reviewed_about_to_use_migration' not in _SESSION
            and rows[14][1:19].rstrip() == _ABOUT_TRAINER_LINE
            and rows[16][1:19].rstrip().startswith('ABOUT')
            and _post_skip_sendout(text, progress, rows, about=True) is not None):
        _SESSION['error'] = None
        _SESSION['reviewed_about_to_use_migration'] = {
            'cleared_error': 'closed_after_skip_unverified', 'verified_stage': 'complete',
            'prior_migration_preserved': True, 'party_unchanged': True, 'wait_budget_preserved': True,
            'source_page': 'GIOVANNI is / about to use', 'full_requires_cont_arrow': [18, 16],
            'handoff_means_learning_finished_only': True,
            'partial_action': 'wait_only', 'full_action': 'handoff_no_button'}


def _fail(reason):
    global _SESSION
    if _SESSION is None:
        _SESSION = {'error': reason}
    else:
        _SESSION['error'] = reason
    return {'phase': 'strategy_review', 'objective': 'Wait.', 'available_actions': ['wait'],
            'review_reason': 'snorlax_harden_skip_' + reason,
            'learning_controller': 'snorlax41_harden_skip'}


def _hint(action, tactic, **extra):
    data = {'learning_controller': 'snorlax41_harden_skip', 'learning_tactic': tactic,
            'learn_move_plan': deepcopy(_SESSION['plan']), 'protected_moves': MOVES.copy(), **extra}
    for key in ('reviewed_post_skip_migration', 'reviewed_about_to_use_migration'):
        if key in _SESSION:
            data[key] = deepcopy(_SESSION[key])
    if action == 'wait':
        return {'phase': 'learning_menu', 'objective': 'Wait.', 'available_actions': ['wait'], **data}
    return command(action, 'learning_menu', data)


def _wait(tactic):
    _SESSION['waits'] += 1
    if _SESSION['waits'] > MAX_SAFE_WAITS:
        return _fail('safe_wait_exhausted')
    return _hint('wait', tactic, safe_wait_count=_SESSION['waits'], safe_wait_limit=MAX_SAFE_WAITS)


def _prefix(compact, pages):
    return bool(compact) and any(p.startswith(compact) for p in pages)


def _choice(rows, wanted):
    # learn_move.asm hl14,7 + text_box offset SCREEN_WIDTH+2；cursor在label左一格。
    positions = {word: [(m.start(), y) for y, row in enumerate(rows)
                        for m in re.finditer(r'(?<![A-Z])' + word + r'(?![A-Z])', row)]
                 for word in ('YES', 'NO')}
    active = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == '▶']
    if positions != {'YES': [(16, 8)], 'NO': [(16, 10)]} or active not in ([(15, 8)], [(15, 10)]):
        return None
    selected = 'YES' if active[0][1] == 8 else 'NO'
    if selected == wanted:
        return 'a'
    return 'down' if wanted == 'NO' else 'up'


def context(text, progress):
    """只接SNORLAX132／41／70,133,156,34；全隊與輸入維持原值。

    回傳的是候選子目標，不能認定Laya已實按；同一完整安全選單可重試。
    完整DidNotLearn頁與未變基線核對後才關頁；後續頁交回原caller。
    """
    global _SESSION
    rows = _rows(text)
    if rows is None:
        return _fail(_SESSION.get('error') or 'text_unreadable') if _SESSION is not None else None
    lower = '\n'.join(rows[12:]); compact = normalize(lower)
    if _SESSION is None:
        if not (compact.startswith('SNORLAXIS') and 'TRYINGTOLEARN' in compact):
            return None
        party = _party(progress)
        learners = [i for i, m in enumerate(party or []) if m['species'] == 132]
        if party is None or len(party) != 6 or len(learners) != 1 or any(m['hp'] <= 0 for m in party):
            return _fail('party_or_unique_learner_unverified')
        learner = party[learners[0]]
        ref = reference()
        if (learner['level'] != 41 or learner['moves'] != MOVES
                or ref.get('source_commit') != SOURCE_COMMIT
                or ref['moves'].get('HARDEN', {}).get('id') != 106
                or {'level': 41, 'move': 'HARDEN'} not in ref['species']['SNORLAX']['level_moves']):
            return _fail('natural_source_or_moves_unverified')
        plan = learn_move_plan(132, MOVES.copy(), 106, level=41)
        if plan != {'decision': 'skip', 'reason': 'preserve_higher_priority_moves', 'move': 'HARDEN'}:
            return _fail('strategy_skip_unverified')
        _SESSION = {'party': deepcopy(party), 'index': learners[0], 'stage': 'intro', 'plan': plan,
                    'seen_move': False, 'delete_no': False, 'abandon_yes': False,
                    'result_prefix': False, 'waits': 0, 'error': None}
    _reviewed_token_recovery(text, progress, rows, compact)
    _reviewed_post_skip_recovery(text, progress, rows)
    _reviewed_about_recovery(text, progress, rows)
    if _SESSION['error'] is not None:
        return _fail(_SESSION['error'])
    if _party(progress) != _SESSION['party']:
        return _fail('party_changed')
    if _SESSION['stage'] == 'complete' and compact not in _RESULT:
        sendout = _post_skip_sendout(text, progress, rows)
        if sendout == 'partial':
            return _wait('await_complete_giovanni_rhyhorn_sendout')
        if sendout == 'full':
            _SESSION = None
            return None  # 僅交回既有battle解析，不代按A、不宣稱打贏坂木。
        about = _post_skip_sendout(text, progress, rows, about=True)
        if about == 'partial':
            return _wait('await_complete_giovanni_about_to_use')
        if about == 'full':
            _SESSION = None
            return None  # cont提示完成，交回原battle；不宣稱第三隻已派出。
        # caller供應新observe；只有真decoder已關Window、無對話／游標才交還。
        if (_decoder_verified(text, False) and not compact
                and not any(c in '▶▷▼' for row in text['cells'] for c in row)):
            _SESSION = None
            return None
        if _decoder_verified(text, True) and not compact and not any('▶' in row for row in rows):
            return _wait('await_verified_skip_window_close')
        return _fail('closed_after_skip_unverified')
    if not _decoder_verified(text, True):
        return _fail('decoder_unverified')
    if any('▷' in row for row in rows):
        return _fail('unexpected_inactive_cursor')
    if any(re.search(r'[A-ZÉ0-9!?]', rows[y]) for y in (12, 13, 15, 17)):
        return _fail('dialogue_geometry_unverified')
    if any(re.search(r'[A-ZÉ0-9!?]', text['cells'][y][x]) for y in (14, 16) for x in (0, 19)):
        return _fail('dialogue_geometry_unverified')
    if any(c == '▼' and (x, y) != (18, 16) for y, row in enumerate(text['cells']) for x, c in enumerate(row)):
        return _fail('arrow_geometry_unverified')
    if any(x in compact for x in ('WHICH', 'FORGOT', 'POOF', 'LEARNED')):
        return _fail('unexpected_forget_or_learned_page')
    stage = _SESSION['stage']
    choices = any(re.search(r'(?<![A-Z])(?:YES|NO)(?![A-Z])', row) for row in rows)
    active = any('▶' in row for row in rows)
    if not compact and not choices and not active:
        return _wait('await_known_transition')
    if stage == 'complete':
        if choices or active:
            return _fail('result_cursor_or_choices_conflict')
        if '!' not in lower:
            return _wait('await_complete_skip_result_close')
        return _hint('a', 'dismiss_verified_harden_skip', learning_complete=True,
                     learning_result='skipped_unchanged', learning_moves_unchanged=True,
                     moves_verified=MOVES.copy())
    if stage == 'abandon_requested' and compact == _PREFIX and not choices and not active:
        if '▼' in lower:
            _SESSION['result_prefix'] = True
            return _hint('a', 'advance_verified_did_not_learn_prefix')
        return _wait('await_complete_result_prefix_arrow')
    if stage == 'abandon_requested' and _prefix(compact, (_PREFIX,)) and not choices and not active:
        return _wait('await_complete_did_not_learn_prefix')
    if stage == 'abandon_requested' and _SESSION['result_prefix'] and _prefix(compact, _RESULT):
        if choices or active:
            return _fail('result_cursor_or_choices_conflict')
        if compact in _RESULT and '!' in lower:
            _SESSION['stage'] = 'complete'
            return _hint('a', 'skip_harden_verified', learning_complete=True,
                         learning_result='skipped_unchanged', learning_moves_unchanged=True,
                         moves_verified=MOVES.copy())
        return _wait('await_complete_harden_result_tail')
    if stage in ('after_delete_no', 'abandon_question', 'abandon_requested') and _prefix(compact, _ABANDON):
        if compact != _ABANDON[0] or '?' not in lower:
            return _wait('await_complete_abandon_question') if not choices and not active else _fail('partial_question_has_choices')
        if stage != 'abandon_requested':
            _SESSION['stage'] = 'abandon_question'
        if not choices:
            return _wait('await_abandon_choices') if not active else _fail('cursor_without_choices')
        action = _choice(rows, 'YES')
        if action is None:
            return _fail('yes_no_geometry_unverified')
        if action == 'a':
            _SESSION['abandon_yes'] = True; _SESSION['stage'] = 'abandon_requested'
        return _hint(action, 'abandon_harden', menu_label='YES')
    if stage in ('intro', 'delete_question', 'after_delete_no') and _prefix(compact, _DELETE):
        if not _SESSION['seen_move']:
            return _fail('delete_before_verified_harden')
        if compact == 'DELETEANOLDERMOVETOMAKEROOM' and '▼' in lower and not choices and not active:
            _SESSION['stage'] = 'delete_question'
            return _hint('a', 'advance_verified_delete_cont')
        if compact not in _DELETE[1:] or '?' not in lower:
            return _wait('await_complete_delete_question') if not choices and not active else _fail('partial_question_has_choices')
        if stage != 'after_delete_no':
            _SESSION['stage'] = 'delete_question'
        if not choices:
            return _wait('await_delete_choices') if not active else _fail('cursor_without_choices')
        action = _choice(rows, 'NO')
        if action is None:
            return _fail('yes_no_geometry_unverified')
        if action == 'a':
            _SESSION['delete_no'] = True; _SESSION['stage'] = 'after_delete_no'
        return _hint(action, 'decline_harden_replacement', menu_label='NO')
    if stage == 'intro' and _prefix(compact, _INTRO) and not choices and not active:
        cont_page = compact in ('SNORLAXISTRYINGTOLEARN', 'BUTSNORLAXCANTLEARNMORE')
        if compact in _INTRO and (('▼' in lower if cont_page else '!' in lower)):
            if 'HARDEN' in compact:
                _SESSION['seen_move'] = True
            return _hint('a', 'advance_verified_harden_intro')
        return _wait('await_complete_harden_intro')
    return _fail('page_unknown_or_out_of_order')
