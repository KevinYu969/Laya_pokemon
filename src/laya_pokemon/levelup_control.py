"""尼多力諾23級聚氣的保守略過流程；只產生 Laya 子目標，不操作遊戲。"""
from __future__ import annotations

import re

from .party_control import command
from .team_strategy import learn_move_plan, normalize


# 保留跨熱載入的問題階段；切勿在刪招確認分頁失去 NO 的意圖。
_SESSION = globals().get('_SESSION')
# pret/pokered a53671100ec22e5394ff26ec028d0812a238dae2:
# data/pokemon/evos_moves.asm NidorinoEvosMoves: db 23, FOCUS_ENERGY.
_SPECIES = 167
_LEVEL = 23
_MOVES = (43, 33, 30, 40)
_NEW_MOVE = 116
_PAGES = (
    'NIDORINOISTRYINGTOLEARNFOCUSENERGY',
    'BUTNIDORINOCANTLEARNMORETHAN4MOVES',
    'DELETEANOLDERMOVETOMAKEROOMFORFOCUSENERGY',
    'DELETEAMOVETOMAKEROOMFORFOCUSENERGY',
    'STOPLEARNINGFOCUSENERGY',
    'ABANDONLEARNINGFOCUSENERGY',
    'NIDORINODIDNOTLEARNFOCUSENERGY',
)
_SCHEMA_VERSION = 3
_MAX_QUESTION_WAIT_STEPS = 30


def _migrate_session():
    """僅一次解除已人工審查的 v1 逐字印問句暫停，其他失敗保持鎖定。"""
    if _SESSION is None or _SESSION.get('schema_version', 1) >= _SCHEMA_VERSION:
        return
    if (_SESSION.get('failed_reason') == 'learning_question_choices_not_visible'
            and _SESSION.get('phase') == 'delete_question'
            and _SESSION.get('confirmed_move') is True):
        _SESSION.pop('failed_reason')
        _SESSION['migration_v2_cleared_typing_pause'] = True
    if (_SESSION.get('schema_version')==2 and _SESSION.get('failed_reason')=='learning_page_not_verified'
            and _SESSION.get('phase')=='delete_question' and _SESSION.get('delete_no_requested') is True
            and _SESSION.get('confirmed_move') is True):
        _SESSION.pop('failed_reason')
        _SESSION['migration_v3_reviewed_abandon_wording']=True
    _SESSION['schema_version'] = _SCHEMA_VERSION
    _SESSION.setdefault('question_wait_steps', 0)


_migrate_session()


def _review(reason):
    if _SESSION is not None:
        _SESSION['failed_reason'] = reason
    return {'phase': 'strategy_review', 'objective': 'Wait.', 'available_actions': ['wait'],
            'review_reason': reason, 'learning_tactic': 'skip_focus_energy'}


def _fingerprint(party):
    return tuple((mon.get('species'), tuple(mon.get('moves', ()))) for mon in party)


def restore_after_review(record,party,source_sha256):
    """只恢復已核對同一存檔的聚氣刪招提問；不得回讀遊戲或略過結果驗證。"""
    global _SESSION
    learners=[m for m in party if m.get('species')==_SPECIES]
    if (record.get('kind')!='nidorino_focus_skip_review' or record.get('source_sha256')!=source_sha256
            or record.get('phase')!='delete_question' or record.get('confirmed_move') is not True
            or not record.get('evidence') or len(learners)!=1 or learners[0].get('level')!=_LEVEL
            or tuple(learners[0].get('moves',()))!=_MOVES):
        raise ValueError('學招恢復記錄與同一最新狀態不符')
    plan=learn_move_plan(_SPECIES,list(_MOVES),_NEW_MOVE,level=_LEVEL)
    if plan.get('decision')!='skip':raise ValueError('略過策略不符')
    _SESSION={'phase':'delete_question','confirmed_move':True,'history':'NIDORINOISTRYINGTOLEARNFOCUSENERGY',
              'last_page':None,'fingerprint':_fingerprint(party),'plan':plan,'delete_no_requested':False,
              'stop_yes_requested':False,'schema_version':_SCHEMA_VERSION,'question_wait_steps':0,
              'restored_from_review':True}


def _choice(rows, desired):
    labels = {label: [(match.start(), y) for y, row in enumerate(rows)
                      for match in re.finditer(r'(?<![A-Z])' + label + r'(?![A-Z])', row)]
              for label in ('YES', 'NO')}
    if any(len(matches) != 1 for matches in labels.values()):
        return None
    yes, no = labels['YES'][0], labels['NO'][0]
    if yes[0] != no[0] or not 0 < no[1] - yes[1] <= 3:
        return None
    cursors = [(x, y) for y in (yes[1], no[1]) for x, char in enumerate(rows[y])
               if char in {'▶', '▷'} and 1 <= yes[0] - x <= 2]
    if len(cursors) != 1:
        return None
    target = labels[desired][0]
    action = 'a' if cursors[0][1] == target[1] else 'down' if cursors[0][1] < target[1] else 'up'
    return action


def skip_context(text, party):
    """只接受已確認的自然學招個案；未知／歧義交給人工工程檢討。"""
    global _SESSION
    cells = text.get('cells', [])
    if len(cells) != 18 or any(len(row) != 20 for row in cells):
        return _review('learning_text_unreadable') if _SESSION is not None else None
    rows = [''.join(row).upper() for row in cells]
    lower = '\n'.join(rows[12:])
    compact = normalize(lower)
    starts = 'NIDORINOIS' in compact and 'TRYINGTOLEARN' in compact
    if _SESSION is None:
        if not starts:
            return None
        learners = [mon for mon in party if mon.get('species') == _SPECIES]
        if (len(learners) != 1 or learners[0].get('level') != _LEVEL
                or tuple(learners[0].get('moves', ())) != _MOVES):
            return _review('learning_case_not_verified')
        plan = learn_move_plan(_SPECIES, list(_MOVES), _NEW_MOVE, level=_LEVEL)
        if plan.get('decision') != 'skip':
            return _review('learning_skip_not_approved_by_strategy')
        _SESSION = {'phase': 'intro', 'confirmed_move': False, 'history': '', 'last_page': None,
                    'fingerprint': _fingerprint(party), 'plan': plan,
                    'delete_no_requested': False, 'stop_yes_requested': False,
                    'schema_version': _SCHEMA_VERSION, 'question_wait_steps': 0}
    if _SESSION.get('failed_reason'):
        return _review(_SESSION['failed_reason'])
    learners = [mon for mon in party if mon.get('species') == _SPECIES]
    if (_fingerprint(party) != _SESSION['fingerprint'] or len(learners) != 1
            or learners[0].get('level') != _LEVEL):
        return _review('learning_party_changed_unexpectedly')
    if any(marker in compact for marker in ('FORGOT', 'POOF', 'WHICH', '12AND')):
        return _review('unexpected_forget_menu_during_skip')
    if not compact or not any(compact in page for page in _PAGES):
        return _review('learning_page_not_verified')
    if compact != _SESSION['last_page']:
        _SESSION['history'] = (_SESSION['history'] + compact)[-2048:]
        _SESSION['last_page'] = compact
    if 'FOCUSENERGY' in compact or 'FOCUSENERGY' in _SESSION['history']:
        _SESSION['confirmed_move'] = True
    if 'DELETE' in compact or (_SESSION['phase'] == 'intro' and 'DELETE'.startswith(compact)):
        if _SESSION['phase'] == 'stop_question':
            return _review('learning_question_order_unexpected')
        _SESSION['phase'] = 'delete_question'
    if ('STOP' in compact or 'ABANDON' in compact
            or (_SESSION['delete_no_requested'] and any(word.startswith(compact) for word in ('STOP','ABANDON')))):
        if not _SESSION['delete_no_requested']:
            return _review('learning_stop_before_delete_no')
        _SESSION['phase'] = 'stop_question'
    extra = {'learning_tactic': 'skip_focus_energy', 'learn_move_plan': _SESSION['plan'],
             'learning_question': _SESSION['phase']}
    if 'DIDNOTLEARN' in compact:
        if (not _SESSION['confirmed_move'] or not _SESSION['stop_yes_requested']
                or _SESSION['phase'] != 'stop_question' or 'NIDORINO' not in compact):
            return _review('learning_completion_not_verified')
        _SESSION = None
        return command('a', 'learning_menu', {**extra, 'learning_tactic': 'skip_confirmed',
                                              'learning_moves_unchanged': True})
    has_choices = any(re.search(r'(?<![A-Z])(?:YES|NO)(?![A-Z])', row) for row in rows)
    if has_choices:
        if not _SESSION['confirmed_move']:
            return _review('learning_move_not_visually_confirmed')
        if _SESSION['phase'] not in {'delete_question', 'stop_question'}:
            return _review('learning_question_not_confirmed')
        desired = 'NO' if _SESSION['phase'] == 'delete_question' else 'YES'
        action = _choice(rows, desired)
        if action is None:
            return _review('learning_choices_or_cursor_unreadable')
        _SESSION['question_wait_steps'] = 0
        if action == 'a':
            _SESSION['delete_no_requested' if desired == 'NO' else 'stop_yes_requested'] = True
        return command(action, 'learning_menu', {**extra, 'menu_label': desired})
    if _SESSION['phase'] in {'delete_question', 'stop_question'}:
        if not _SESSION['confirmed_move']:
            return _review('learning_move_not_visually_confirmed')
        if '▼' not in lower:
            _SESSION['question_wait_steps'] = _SESSION.get('question_wait_steps', 0) + 1
            if _SESSION['question_wait_steps'] > _MAX_QUESTION_WAIT_STEPS:
                return _review('learning_question_typing_timeout')
            return {'phase': 'learning_menu', 'objective': 'Wait.', 'available_actions': ['wait'],
                    **extra, 'learning_tactic': 'wait_for_learning_question_text',
                    'learning_question_wait_steps': _SESSION['question_wait_steps']}
        _SESSION['question_wait_steps'] = 0
        return command('a', 'learning_menu', {**extra, 'learning_tactic': 'advance_wrapped_learning_question'})
    return command('a', 'learning_menu', {**extra, 'learning_tactic': 'advance_focus_energy_intro'})
