"""自然學招工程候選：妙蛙草30級換飛葉快刀、大嘴雀25級略過模仿。

純文字／唯讀進度輸入，只回傳 Laya 子目標；不啟動模擬器、不執行按鍵。
其他已知候選只提供策略並要求檢討；尚未宣稱實機校準成功。
"""
from __future__ import annotations

import re

from .party_control import command
from .team_strategy import learn_move_plan, move_key, normalize, reference, species_key


SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCES = [f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/{path}' for path in (
    'data/pokemon/evos_moves.asm', 'engine/pokemon/learn_move.asm', 'data/text/text_4.asm')]
MAX_SAFE_WAITS = 30
_SESSION = globals().get('_SESSION')
_CASES = {
    (9, 30): (75, (77, 15, 73, 22), True),
    # 固定紅版 source 是32級，不是30級；尼多力諾此案例僅提供計畫。
    (167, 32): (31, (43, 33, 30, 40), False),
    (35, 25): (119, (64, 45, 43, 31), True),
}
_INTRO = ('IVYSAURISTRYINGTOLEARNRAZORLEAF', 'TRYINGTOLEARNRAZORLEAF', 'RAZORLEAF',
          'LEAF', 'BUTIVYSAURCANTLEARNMORETHAN4MOVES', 'IVYSAURCANTLEARNMORETHAN4MOVES',
          'CANTLEARNMORETHAN4MOVES', 'THAN4MOVES')
_DELETE = ('DELETEANOLDERMOVETOMAKEROOMFORRAZORLEAF', 'MOVETOMAKEROOMFORRAZORLEAF', 'FORRAZORLEAF')
_ABANDON = ('ABANDONLEARNINGRAZORLEAF', 'STOPLEARNINGRAZORLEAF', 'LEARNINGRAZORLEAF', 'RAZORLEAF')
_FORGET = ('WHICHMOVESHOULDBEFORGOTTEN', 'BEFORGOTTEN')
_POOF = ('12ANDPOOF', '12AND', 'POOF')
_FORGOT = ('IVYSAURFORGOTPOISONPOWDER', 'FORGOTPOISONPOWDER', 'POISONPOWDER')
_LEARNED = ('IVYSAURLEARNEDRAZORLEAF', 'LEARNEDRAZORLEAF', 'RAZORLEAF')
_DID_NOT = ('IVYSAURDIDNOTLEARNRAZORLEAF', 'DIDNOTLEARNRAZORLEAF', 'LEARNRAZORLEAF')


def candidate_plan(species, level, moves):
    """固定 source 自然等級核對；不以『小於目前等級』推測本次正在學哪招。"""
    case = _CASES.get((species, level))
    if case is None:
        if (species, level) == (167, 30):
            return {'decision': 'review', 'reason': 'source_fury_attack_level_is_32_not_30',
                    'move': 'FURY_ATTACK', 'natural_level': 32}
        return None
    new, before, calibrated = case
    ref = reference()
    name = species_key(species)
    learned = move_key(new)
    if (ref.get('source_commit') != SOURCE_COMMIT or name is None or learned is None
            or ref['moves'][learned]['id'] != new
            or not any(row['level'] == level and row['move'] == learned
                       for row in ref['species'][name]['level_moves'])):
        return {'decision': 'review', 'reason': 'natural_learning_source_not_verified'}
    if tuple(moves) != before:
        return {'decision': 'review', 'reason': 'natural_learning_initial_moves_not_verified'}
    result = learn_move_plan(species, list(before), new, level=level)
    return {**result, 'natural_level': level, 'new_move_id': new,
            'ui_candidate_implemented': calibrated, 'sources': SOURCES}


def _fail(reason, **extra):
    if _SESSION is not None:
        _SESSION['error'] = reason
    return {'phase': 'strategy_review', 'objective': 'Wait.', 'available_actions': ['wait'],
            'review_reason': reason, 'learning_controller': 'bounded_natural_move_candidate', **extra}


def _hint(action, tactic, **extra):
    data = {'learning_tactic': tactic, 'learning_controller': 'bounded_natural_move_candidate',
            'learn_move_plan': _SESSION['plan'], **extra}
    if action == 'wait':
        return {'phase': 'learning_menu', 'objective': 'Wait.', 'available_actions': ['wait'], **data}
    _SESSION['waits'] = 0
    return command(action, 'learning_menu', data)


def _wait(tactic):
    _SESSION['waits'] += 1
    if _SESSION['waits'] > MAX_SAFE_WAITS:
        return _fail('natural_learning_known_transition_wait_exhausted')
    return _hint('wait', tactic, safe_wait_count=_SESSION['waits'], safe_wait_limit=MAX_SAFE_WAITS)


def _fingerprint(party):
    return tuple((mon.get('species'), tuple(mon.get('moves', ()))) for mon in party)


def _prefix(compact, pages):
    return bool(compact) and any(page.startswith(compact) for page in pages)


def _choice(rows, label):
    options = {word: [(match.start(), y) for y, row in enumerate(rows)
                      for match in re.finditer(r'(?<![A-Z])' + word + r'(?![A-Z])', row)]
               for word in ('YES', 'NO')}
    if any(len(found) != 1 for found in options.values()):
        return None
    yes, no = options['YES'][0], options['NO'][0]
    if yes[0] != no[0] or not 0 < no[1] - yes[1] <= 3:
        return None
    # ▷ 是殘留／靜態標記；不可將它當作不可逆確認所需的主動游標。
    active = [(x, y) for y, row in enumerate(rows) for x, char in enumerate(row) if char == '▶']
    if (len(active) != 1 or active[0][1] not in (yes[1], no[1])
            or not 1 <= yes[0] - active[0][0] <= 2):
        return None
    target = options[label][0]
    return 'a' if active[0][1] == target[1] else 'up' if active[0][1] > target[1] else 'down'


def _forget_action(rows):
    before = _SESSION['before']
    expected = [normalize(move_key(move)) for move in before]
    actual = [normalize(rows[y][6:]) for y in range(8, 12)]
    if actual != expected:
        # 問句先逐字顯示，招式框稍後才覆蓋battle HUD；等級／HP不能當作四招。
        formed = (any(rows[y][5] == '▶' for y in range(8, 12))
                  or all(label and label.isalpha() for label in actual))
        if not formed:
            return _wait('await_source_ordered_four_move_menu')
        return _fail('natural_learning_forget_four_move_layout_mismatch')
    active = [(x, y) for y, row in enumerate(rows) for x, char in enumerate(row) if char == '▶']
    if len(active) != 1 or active[0][0] != 5 or active[0][1] not in range(8, 12):
        return _fail('natural_learning_forget_active_cursor_unreadable')
    action = 'a' if active[0][1] == 8 else 'up'
    if action == 'a':
        _SESSION['stage'] = 'forget_selected'
    return _hint(action, 'forget_only_verified_poisonpowder', forgotten_move=77,
                 protected_moves=[15, 73, 22], menu_label='POISONPOWDER')


def _fearow_skip(rows, progress):
    """封閉個案：Delete NO→Abandon YES→Did not learn；絕不進入四招刪除頁。"""
    global _SESSION
    if _SESSION.get('error'):
        return _fail(_SESSION['error'])
    party = progress.get('party', [])
    index = _SESSION['index']
    if (progress.get('party_read_valid') is not True or len(party) <= index
            or party[index].get('species') != 35 or party[index].get('level') != 25
            or _fingerprint(party) != _SESSION['baseline']):
        return _fail('fearow_skip_party_changed_unexpectedly')
    lower = '\n'.join(rows[12:])
    compact = normalize(lower)
    stage = _SESSION['stage']
    full_result = 'FEAROWDIDNOTLEARNMIRRORMOVE'
    if stage == 'complete':
        if compact == full_result:
            return _hint('a', 'dismiss_verified_mirror_move_skip', learning_complete=True,
                         learning_moves_unchanged=True)
        _SESSION = None
        return None
    if any(marker in compact for marker in ('WHICH', 'FORGOT', 'POOF', '12AND', 'LEARNED')):
        return _fail('fearow_skip_unexpected_forget_or_learned_screen')
    if compact != _SESSION['last_page']:
        _SESSION['history'] = (_SESSION['history'] + compact)[-2048:]
        _SESSION['last_page'] = compact
    if 'MIRRORMOVE' in _SESSION['history']:
        _SESSION['seen_move'] = True
    choices = any(re.search(r'(?<![A-Z])(?:YES|NO)(?![A-Z])', row) for row in rows)
    intro_pages = ('FEAROWISTRYINGTOLEARNMIRRORMOVE', 'TRYINGTOLEARNMIRRORMOVE', 'MIRRORMOVE', 'MOVE',
                   'BUTFEAROWCANTLEARNMORETHAN4MOVES', 'FEAROWCANTLEARNMORETHAN4MOVES',
                   'CANTLEARNMORETHAN4MOVES', 'THAN4MOVES')
    delete_pages = ('DELETEANOLDERMOVETOMAKEROOMFORMIRRORMOVE', 'MOVETOMAKEROOMFORMIRRORMOVE', 'FORMIRRORMOVE')
    abandon_pages = ('ABANDONLEARNINGMIRRORMOVE', 'STOPLEARNINGMIRRORMOVE', 'LEARNINGMIRRORMOVE', 'MIRRORMOVE')
    result_pages = (full_result, 'DIDNOTLEARNMIRRORMOVE', 'LEARNMIRRORMOVE', 'MIRRORMOVE')
    if (compact == full_result or (full_result in _SESSION['history']
                                  and stage == 'abandon_requested' and _prefix(compact, result_pages))):
        if (not _SESSION['seen_move'] or not _SESSION['abandon_yes_requested']
                or stage != 'abandon_requested'):
            return _fail('fearow_skip_completion_not_verified')
        if '!' not in lower and '▼' not in lower:
            return _wait('await_complete_mirror_skip_result')
        _SESSION['stage'] = 'complete'
        return _hint('a', 'skip_mirror_move_confirmed', learning_complete=True,
                     learning_result='skipped_unchanged', learning_moves_unchanged=True,
                     moves_verified=[64, 45, 43, 31])
    if not compact and not choices:
        return _wait('await_known_mirror_skip_transition')
    abandon_start = compact and any(word.startswith(compact) or word in compact
                                    for word in ('ABANDONLEARNING', 'STOPLEARNING'))
    if abandon_start:
        if not _SESSION['delete_no_requested']:
            return _fail('fearow_skip_abandon_before_delete_no')
        if stage not in {'after_delete_no', 'abandon_question', 'abandon_requested'}:
            return _fail('fearow_skip_question_order_unexpected')
        if stage != 'abandon_requested':
            _SESSION['stage'] = stage = 'abandon_question'
    if stage in {'abandon_question', 'abandon_requested'} and _prefix(compact, abandon_pages):
        if choices:
            action = _choice(rows, 'YES')
            if action is None:
                return _fail('fearow_skip_yes_no_cursor_unreadable')
            if action == 'a':
                _SESSION['abandon_yes_requested'] = True
                _SESSION['stage'] = 'abandon_requested'
            return _hint(action, 'abandon_mirror_move_learning', menu_label='YES')
        return _hint('a', 'advance_wrapped_mirror_abandon_question') if '▼' in lower else _wait('await_mirror_abandon_choices')
    if stage == 'abandon_requested' and _prefix(compact, result_pages):
        return _wait('await_verified_mirror_did_not_learn')
    if _prefix(compact, delete_pages):
        if stage not in {'intro', 'delete_question', 'after_delete_no'} or not _SESSION['seen_move']:
            return _fail('fearow_skip_delete_without_confirmed_move')
        if stage != 'after_delete_no':
            _SESSION['stage'] = stage = 'delete_question'
    if choices:
        if stage not in {'delete_question', 'after_delete_no'} or not _prefix(compact, delete_pages):
            return _fail('fearow_skip_question_not_verified')
        action = _choice(rows, 'NO')
        if action is None:
            return _fail('fearow_skip_yes_no_cursor_unreadable')
        if action == 'a':
            _SESSION['delete_no_requested'] = True
            _SESSION['stage'] = 'after_delete_no'
        return _hint(action, 'decline_mirror_move_replacement', menu_label='NO')
    if stage in {'delete_question', 'after_delete_no'} and _prefix(compact, delete_pages):
        return _hint('a', 'advance_wrapped_mirror_delete_question') if '▼' in lower else _wait('await_mirror_delete_choices')
    if stage == 'intro' and _prefix(compact, intro_pages):
        if '▼' in lower or '!' in lower or compact == 'FEAROWISTRYINGTOLEARN':
            return _hint('a', 'advance_verified_mirror_move_intro')
        return _wait('await_mirror_move_intro_text')
    return _fail('fearow_skip_page_unknown')


def context(text, progress):
    """接受可見20×18文字與唯讀progress；未知自然個案不接管。"""
    global _SESSION
    cells = text.get('cells', [])
    if len(cells) != 18 or any(len(row) != 20 for row in cells):
        return _fail('natural_learning_text_unreadable') if _SESSION is not None else None
    rows = [''.join(row).upper() for row in cells]
    lower = '\n'.join(rows[12:])
    compact = normalize(lower)
    party = progress.get('party', [])
    if _SESSION is None:
        starts = [i for i, mon in enumerate(party)
                  if (mon.get('species'), mon.get('level')) in _CASES
                  and normalize(species_key(mon['species']) + 'IS') in compact
                  and 'TRYINGTOLEARN' in compact]
        if not starts:
            return None
        if len(starts) != 1 or progress.get('party_read_valid') is not True:
            return _fail('natural_learning_learner_not_unique_or_verified')
        index = starts[0]
        learner = party[index]
        if sum(mon.get('species') == learner['species'] for mon in party) != 1:
            return _fail('natural_learning_learner_not_unique_or_verified')
        plan = candidate_plan(learner['species'], learner['level'], learner.get('moves', []))
        if not plan or plan['decision'] == 'review':
            return _fail('natural_learning_candidate_not_verified', learn_move_plan=plan)
        if not plan['ui_candidate_implemented']:
            return _fail('natural_learning_ui_requires_review', learn_move_plan=plan,
                         learning_move_visually_confirmed=False)
        if (learner['species'], learner['level']) == (35, 25):
            if plan['decision'] != 'skip' or plan.get('move') != 'MIRROR_MOVE':
                return _fail('fearow_skip_strategy_not_verified', learn_move_plan=plan)
            _SESSION = {'kind': 'fearow_mirror_skip', 'stage': 'intro', 'index': index,
                        'baseline': _fingerprint(party), 'plan': plan, 'seen_move': False,
                        'history': '', 'last_page': None, 'delete_no_requested': False,
                        'abandon_yes_requested': False, 'waits': 0, 'schema_version': 2}
            return _fearow_skip(rows, progress)
        if (plan['decision'] != 'replace' or plan.get('replace_index') != 0
                or plan.get('forget') != 'POISONPOWDER' or plan.get('move') != 'RAZOR_LEAF'):
            return _fail('natural_learning_replacement_plan_mismatch', learn_move_plan=plan)
        baseline = _fingerprint(party)
        expected = list(baseline)
        expected[index] = (9, (75, 15, 73, 22))
        _SESSION = {'stage': 'intro', 'index': index, 'baseline': baseline, 'expected': tuple(expected),
                    'before': (77, 15, 73, 22), 'plan': plan, 'seen_move': False,
                    'history': '', 'last_page': None, 'delete_yes_requested': False,
                    'seen_forgot': False, 'and_requested': False, 'abandon_yes_requested': False,
                    'waits': 0, 'schema_version': 1}
    if _SESSION.get('kind') == 'fearow_mirror_skip':
        return _fearow_skip(rows, progress)
    if _SESSION.get('error'):
        return _fail(_SESSION['error'])
    current = _fingerprint(party)
    if progress.get('party_read_valid') is not True:
        return _fail('natural_learning_party_not_verified')
    if (len(party) <= _SESSION['index'] or party[_SESSION['index']].get('species') != 9
            or party[_SESSION['index']].get('level') != 30):
        return _fail('natural_learning_learner_changed')
    if current not in (_SESSION['baseline'], _SESSION['expected']):
        return _fail('natural_learning_unexpected_move_change')
    if current == _SESSION['expected'] and not _SESSION['and_requested']:
        return _fail('natural_learning_move_changed_before_verified_selection')
    stage = _SESSION['stage']
    if stage == 'complete':
        if compact == 'IVYSAURLEARNEDRAZORLEAF':
            return _hint('a', 'dismiss_verified_razor_leaf_learned', learning_complete=True)
        _SESSION = None
        return None
    if compact != _SESSION['last_page']:
        _SESSION['history'] = (_SESSION['history'] + compact)[-2048:]
        _SESSION['last_page'] = compact
    if 'RAZORLEAF' in _SESSION['history']:
        _SESSION['seen_move'] = True
    choices = any(re.search(r'(?<![A-Z])(?:YES|NO)(?![A-Z])', row) for row in rows)
    if not compact and not choices and not any('▶' in row for row in rows):
        return _wait('await_known_natural_learning_transition')

    # ABANDON僅作尚未確認刪招時的安全中止；中止仍要求工程檢討，不當成成功學招。
    if (compact and stage in {'intro', 'delete_question', 'await_forget', 'forget_menu', 'abandon_question'}
            and any(word.startswith(compact) or word in compact
                    for word in ('ABANDONLEARNING', 'STOPLEARNING'))):
        if (not _SESSION['seen_move'] or stage not in {'intro', 'delete_question', 'await_forget',
                                                     'forget_menu', 'abandon_question'}
                or current != _SESSION['baseline']):
            return _fail('natural_learning_unexpected_abandon_question')
        _SESSION['stage'] = stage = 'abandon_question'
    if stage == 'abandon_question':
        if choices:
            action = _choice(rows, 'YES')
            if action is None:
                return _fail('natural_learning_yes_no_cursor_unreadable')
            if action == 'a':
                _SESSION['abandon_yes_requested'] = True
                _SESSION['stage'] = 'abandon_requested'
            return _hint(action, 'safely_abandon_learning', menu_label='YES')
        if not _prefix(compact, _ABANDON):
            return _fail('natural_learning_abandon_page_unknown')
        return _hint('a', 'advance_wrapped_abandon_question') if '▼' in lower else _wait('await_abandon_choices')
    if stage == 'abandon_requested':
        if current != _SESSION['baseline']:
            return _fail('natural_learning_abandon_changed_moves')
        if compact == 'IVYSAURDIDNOTLEARNRAZORLEAF':
            return _fail('natural_learning_abandoned_safely', learning_moves_unchanged=True,
                         learning_result='did_not_learn', learn_move_plan=_SESSION['plan'])
        if _prefix(compact, _DID_NOT) or not compact:
            return _wait('await_did_not_learn_confirmation')
        return _fail('natural_learning_abandon_result_unknown')

    if stage in {'forget_selected', 'forgot_message', 'and_message'}:
        if compact and 'AND'.startswith(compact) and compact != 'AND':
            if not _SESSION['seen_forgot'] or stage not in {'forgot_message', 'and_message'}:
                return _fail('natural_learning_and_without_verified_forgot')
            return _wait('await_complete_and_message')
        if compact == 'AND':
            if not _SESSION['seen_forgot'] or stage not in {'forgot_message', 'and_message'}:
                return _fail('natural_learning_and_without_verified_forgot')
            if '...' not in lower and '▼' not in lower:
                return _wait('await_complete_and_message')
            _SESSION['stage'] = 'and_message'
            _SESSION['and_requested'] = True
            return _hint('a', 'advance_verified_learning_and')
        if _prefix(compact, _LEARNED) and stage == 'and_message':
            if compact == 'IVYSAURLEARNEDRAZORLEAF' and ('!' in lower or '▼' in lower):
                if current != _SESSION['expected']:
                    return _fail('natural_learning_learned_without_expected_moves')
                _SESSION['stage'] = 'complete'
                return _hint('a', 'verified_razor_leaf_learned', learning_complete=True,
                             moves_verified=[75, 15, 73, 22], forgotten_move=77, protected_moves=[15, 73, 22])
            return _wait('await_verified_razor_leaf_learned')
        if _prefix(compact, _FORGOT) and stage in {'forget_selected', 'forgot_message'}:
            if compact == 'IVYSAURFORGOTPOISONPOWDER' and ('!' in lower or '▼' in lower):
                _SESSION['seen_forgot'] = True
                _SESSION['stage'] = 'forgot_message'
                return _hint('a', 'advance_verified_poisonpowder_forgot')
            return _wait('await_verified_poisonpowder_forgot')
        if _prefix(compact, _POOF) and stage == 'forget_selected':
            return _wait('await_forget_animation')
        if not compact:
            return _wait('await_known_learning_transition')
        # Laya可能選WAIT；仍在原四招選單時重複相同安全目標，不跳到動畫。
        if stage == 'forget_selected' and _prefix(compact, _FORGET):
            return _forget_action(rows)
        return _fail('natural_learning_post_selection_page_unknown')

    if (_prefix(compact, _FORGET) and (stage in {'await_forget', 'forget_menu'}
                                      or 'WHICH' in compact or 'BEFORGOTTEN' in compact)):
        if not _SESSION['delete_yes_requested'] or stage not in {'await_forget', 'forget_menu'}:
            return _fail('natural_learning_unexpected_forget_menu')
        _SESSION['stage'] = 'forget_menu'
        return _forget_action(rows)
    if 'FORGOT' in compact or 'POOF' in compact or 'LEARNED' in compact or '12AND' in compact:
        return _fail('natural_learning_forget_without_verified_selection')
    if _prefix(compact, _DELETE):
        if not _SESSION['seen_move'] or stage not in {'intro', 'delete_question', 'await_forget'}:
            return _fail('natural_learning_delete_without_confirmed_move')
        _SESSION['stage'] = stage = 'delete_question'
    if choices:
        if stage != 'delete_question' or not _SESSION['seen_move'] or not _prefix(compact, _DELETE):
            return _fail('natural_learning_question_not_verified')
        action = _choice(rows, 'YES')
        if action is None:
            return _fail('natural_learning_yes_no_cursor_unreadable')
        if action == 'a':
            _SESSION['delete_yes_requested'] = True
            _SESSION['stage'] = 'await_forget'
        return _hint(action, 'accept_verified_poisonpowder_replacement', menu_label='YES')
    if stage == 'delete_question':
        return _hint('a', 'advance_wrapped_delete_question') if '▼' in lower else _wait('await_delete_choices')
    if stage in {'await_forget', 'forget_menu'} and not compact:
        return _wait('await_verified_forget_menu')
    if stage == 'intro' and _prefix(compact, _INTRO):
        # 首屏已核對唯一學習者；僅已完整訊息或▼可前進，其餘逐字等待。
        if '▼' in lower or '!' in lower or compact == 'IVYSAURISTRYINGTOLEARN':
            return _hint('a', 'advance_verified_natural_learning_intro')
        return _wait('await_natural_learning_text')
    return _fail('natural_learning_page_unknown')
