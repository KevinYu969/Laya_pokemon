"""僅教尼多力諾TM11泡沫光線的候選狀態機；不按鍵、不讀寫遊戲或存檔。

相容性及文字流程固定於pret/pokered公開版本。背包和忘招版面沿用已實測
CUT的座標，但TM11的完整教學尚未實機校準；未知畫面必須檢討。
"""
from copy import deepcopy
import re

from .field_moves import _item_labels, _KEY_ITEM_IDS
from .party_control import command
from .team_strategy import normalize, reference, species_key


SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE_SHA256 = {
    'data/pokemon/base_stats/nidorino.asm': '099f31db74e8f77c8ac12895eb8d0ac0d829f594d97f7d74c283a0c8ea678127',
    'data/moves/moves.asm': 'a2cf3e1ec6bf4b5caaeeec974967691c9eb47923d1e7432fb0267ba7d3a5931f',
    'constants/item_constants.asm': 'b5a1db015fbf0de637381eb39350f21f35a436a8088e2f6657f65c79f118f97f',
    'engine/items/item_effects.asm': '76b570b5216bbbcf6d9528c4704d931744a3740cce88afdc4f4f8f700449dda1',
    'engine/pokemon/learn_move.asm': 'f4e7973a87e6c0e74a2ce819eb6096121aca5ce7de7d4c040e8a5049cd31d8b6',
    'data/text/text_4.asm': 'eb9287b4d4e40679a916747d5ab7f6fb97ae7d6aabbfd7c2dc9ccabd2dcf5311',
    'data/text/text_6.asm': '780a4113660b6ed4c3fa54ddd2a984e1dc7d6bea7f423a00d5a476dfaf5f80ec',
}
SOURCES = [f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/{path}' for path in SOURCE_SHA256]
TM11, BUBBLEBEAM, NIDORINO, LEER = 211, 61, 167, 43
BEFORE_MOVES = [43, 33, 30, 40]
AFTER_MOVES = [61, 33, 30, 40]
MAX_TEXT_WAITS, MAX_BAG_REQUESTS, MAX_STAGNANT_REQUESTS, MAX_CONTEXTS = 30, 20, 3, 250
INTENT = {'kind': 'teach_bubblebeam', 'species': NIDORINO, 'item': TM11,
          'move': BUBBLEBEAM, 'replace_move': LEER}

_BOOT = ('BOOTEDUPATM',)
_CONTAINED = ('ITCONTAINEDBUBBLEBEAM',)
_TEACH = ('TEACHBUBBLEBEAMTOAPOKEMON', 'TOAPOKEMON')
_INTRO = ('NIDORINOISTRYINGTOLEARNBUBBLEBEAM', 'TRYINGTOLEARNBUBBLEBEAM', 'BUBBLEBEAM')
_CAPACITY = ('BUTNIDORINOCANTLEARNMORETHAN4MOVES', 'NIDORINOCANTLEARNMORETHAN4MOVES',
             'CANTLEARNMORETHAN4MOVES', 'THAN4MOVES')
_DELETE = ('DELETEANOLDERMOVETOMAKEROOMFORBUBBLEBEAM',
           'MOVETOMAKEROOMFORBUBBLEBEAM', 'FORBUBBLEBEAM')
_FORGET = ('WHICHMOVESHOULDBEFORGOTTEN', 'BEFORGOTTEN')
_FORGOT = ('12ANDPOOF', '12AND', 'POOF', 'NIDORINOFORGOTLEERAND',
           'NIDORINOFORGOTLEER', 'LEERAND', 'LEER', 'AND')
_LEARNED = ('NIDORINOLEARNEDBUBBLEBEAM', 'LEARNEDBUBBLEBEAM', 'BUBBLEBEAM')


def _rows(text):
    cells = text.get('cells') if isinstance(text, dict) else None
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(row, (list, tuple)) or len(row) != 20
                   or any(not isinstance(c, str) or (len(c) != 1 and not (y>=12 and c=="'t"))
                          for c in row) for y,row in enumerate(cells))):
        return None
    # 紅版can't的't是單一字格；只將已核對的下方對話縮寫正規化為T，
    # 保持每列20格及所有選單座標，未知多字格仍拒絕。
    return [''.join('t' if c=="'t" else c for c in row).upper() for row in cells]


def _inventory(items):
    if (not isinstance(items, list) or not 1 <= len(items) <= 20
            or any(not isinstance(x, dict) or set(x) != {'item', 'quantity'}
                   or type(x['item']) is not int or not 1 <= x['item'] <= 255
                   or type(x['quantity']) is not int or not 1 <= x['quantity'] <= 99 for x in items)):
        return None
    pairs = [(x['item'], x['quantity']) for x in items]
    return pairs if len(set(x[0] for x in pairs)) == len(pairs) else None


def _hint(action, tactic, **extra):
    meta = {'tm_teaching_controller': 'candidate_nidorino_tm11', 'tm_teaching_tactic': tactic,
            'sources': SOURCES, **extra}
    if action == 'wait':
        return {'phase': 'tm_teaching_menu', 'objective': 'Wait.', 'available_actions': ['wait'],
                'controller_menu_verified': True, **meta}
    return command(action, 'tm_teaching_menu', meta)


class BubbleBeamController:
    """每次交易建立一個實例；明確意圖必須完全符合常數INTENT。

    context只接受完整20×18可見cells、唯讀progress、已校驗非戰鬥／野外聲明。
    初始四招嚴格為[43,33,30,40]，既有泡沫光線沒有本次交易基線時不冒稱完成。
    唯一允許變更為首招43→61、該格PP→20與TM11數量減一；其餘隊伍資料不變。
    """

    def __init__(self, intent):
        if intent != INTENT or any(type(intent[k]) is not int for k in ('species', 'item', 'move', 'replace_move')):
            raise ValueError('僅允許明確NIDORINO167／TM11 item211／BUBBLEBEAM61／替換LEER43')
        self.intent = deepcopy(intent)
        self.stage, self.error = 'initial', None
        self.baseline = self.inventory_before = self.inventory_after = None
        self.target_index = None
        self.seen_contained = self.learner_selected = self.seen_learner = False
        self.teach_verified = self.delete_verified = self.seen_learned = False
        self.delete_confirmed = False
        self.wait_stage, self.wait_count = None, 0
        self.bag_requests, self.bag_stagnant = 0, 0
        self.bag_last_index = self.bag_last_action = None
        self.calls = 0

    def _fail(self, reason):
        self.error = reason
        return {'phase': 'campaign_review', 'objective': 'Wait.', 'available_actions': ['wait'],
                'review_reason': reason, 'tm_teaching_controller': 'candidate_nidorino_tm11',
                'sources': SOURCES}

    def _wait(self, tactic):
        if self.wait_stage != self.stage:
            self.wait_stage, self.wait_count = self.stage, 0
        if self.wait_count >= MAX_TEXT_WAITS:
            return self._fail('bubblebeam_known_text_wait_exhausted')
        self.wait_count += 1
        return _hint('wait', tactic, safe_wait_count=self.wait_count, safe_wait_limit=MAX_TEXT_WAITS)

    def _text_a(self, rows, tactic):
        """完整已知對話只能在沒有真正選單游標時確認；背景▷可以保留。"""
        if any('▶' in row for row in rows):
            return self._fail('bubblebeam_dialogue_has_active_cursor')
        return _hint('a', tactic)

    def context(self, text, progress, *, overworld_ready=False, battle_active=False):
        """回傳一個Laya可分類的按鍵子目標；所有矛盾優先於文字等待。"""
        if self.error:
            return self._fail(self.error)
        self.calls += 1
        if self.calls > MAX_CONTEXTS:
            return self._fail('bubblebeam_transaction_context_limit')
        if battle_active is not False:
            return self._fail('bubblebeam_requires_verified_nonbattle')
        rows = _rows(text)
        if rows is None:
            return self._fail('bubblebeam_visible_cells_invalid')
        error = self._check_progress(progress)
        if error:
            return self._fail(error)
        result = self._context(rows, progress, overworld_ready)
        if result.get('phase') == 'campaign_review':
            self.error = result['review_reason']
        elif result.get('available_actions') != ['wait']:
            self.wait_stage, self.wait_count = None, 0
        return result

    def _check_progress(self, progress):
        """先檢查真正隊伍／道具指紋；未知或錯誤變更不得被partial等待遮蔽。"""
        if not isinstance(progress, dict) or progress.get('party_read_valid') is not True:
            return 'bubblebeam_party_not_verified'
        party = progress.get('party')
        if (not isinstance(party, list) or not 1 <= len(party) <= 6
                or any(not isinstance(m, dict) or species_key(m.get('species')) is None
                       or not isinstance(m.get('moves'), list) or len(m['moves']) != 4
                       or any(type(v) is not int or not 0 <= v <= 165 for v in m['moves'])
                       or not isinstance(m.get('pp'), list) or len(m['pp']) != 4
                       or any(type(v) is not int or not 0 <= v <= 255 for v in m['pp']) for m in party)):
            return 'bubblebeam_party_fingerprint_unreadable'
        targets = [i for i, m in enumerate(party) if m['species'] == NIDORINO]
        if len(targets) != 1 or len({m['species'] for m in party}) != len(party):
            return 'bubblebeam_unique_target_not_verified'
        inv = _inventory(progress.get('inventory'))
        # 學掉唯一一項道具時允許空背包作為精確的預期結果。
        if progress.get('inventory') == [] and self.inventory_after == []:
            inv = []
        if inv is None:
            return 'bubblebeam_inventory_not_verified'
        if self.baseline is None:
            ref = reference()
            move = ref.get('moves', {}).get('BUBBLEBEAM', {})
            if (ref.get('source_commit') != SOURCE_COMMIT or 'BUBBLEBEAM' not in ref['species']['NIDORINO']['tmhm']
                    or (move.get('id'), move.get('power'), move.get('type'), move.get('pp')) != (61, 65, 'WATER', 20)):
                return 'bubblebeam_fixed_source_contract_missing'
            if party[targets[0]]['moves'] != BEFORE_MOVES:
                return 'bubblebeam_initial_four_moves_not_supported'
            if not any(item == TM11 for item, _ in inv):
                return 'bubblebeam_tm11_missing'
            self.target_index, self.baseline = targets[0], deepcopy(party)
            self.inventory_before = inv
            self.inventory_after = [(item, qty - (item == TM11)) for item, qty in inv
                                    if item != TM11 or qty > 1]
        if len(party) != len(self.baseline) or targets[0] != self.target_index:
            return 'bubblebeam_party_changed_unexpectedly'
        for i, (mon, before) in enumerate(zip(party, self.baseline)):
            if i != self.target_index:
                if mon != before:
                    return 'bubblebeam_other_party_changed_unexpectedly'
                continue
            if {k: v for k, v in mon.items() if k not in {'moves', 'pp'}} != {k: v for k, v in before.items() if k not in {'moves', 'pp'}}:
                return 'bubblebeam_target_nonmove_data_changed'
            if mon['moves'] not in (BEFORE_MOVES, AFTER_MOVES):
                return 'bubblebeam_unexpected_move_replacement'
            expected_pp = [20, *before['pp'][1:]] if mon['moves'] == AFTER_MOVES else before['pp']
            if mon['pp'] != expected_pp:
                return 'bubblebeam_pp_change_not_verified'
            if mon['moves'] == AFTER_MOVES and self.stage not in {'forget_selected', 'learned', 'closing', 'complete'}:
                return 'bubblebeam_move_changed_before_verified_forget'
            if self.stage in {'learned', 'closing', 'complete'} and mon['moves'] != AFTER_MOVES:
                return 'bubblebeam_learned_without_expected_moves'
        if inv not in (self.inventory_before, self.inventory_after):
            return 'bubblebeam_inventory_change_not_only_one_tm11'
        if inv == self.inventory_after and (party[self.target_index]['moves'] != AFTER_MOVES
                                           or self.stage not in {'forget_selected', 'learned', 'closing', 'complete'}):
            return 'bubblebeam_tm11_consumed_before_verified_learning'
        return None

    @staticmethod
    def _start_menu(rows):
        return all(any(row.strip(' ▶▷') == label for row in rows) for label in ('POKÉDEX', 'POKÉMON', 'ITEM'))

    def _select(self, rows, label, tactic):
        """只看實心游標；背景空心▷不代表目前選項。"""
        labels = [(len(row) - len(row.lstrip(' ▶▷')), y) for y, row in enumerate(rows)
                  if row.strip(' ▶▷') == label]
        cursors = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == '▶']
        if len(labels) != 1 or len(cursors) != 1 or cursors[0][0] != labels[0][0] - 1:
            return self._fail('bubblebeam_menu_cursor_not_verified')
        y, ty = cursors[0][1], labels[0][1]
        return _hint('a' if y == ty else 'up' if y > ty else 'down', tactic, menu_label=label)

    def _bag(self, rows, inventory, *, closing=False):
        """實際CUT背包版面：x6列名、x5游標、y4/6/8可選、y10預覽。"""
        inv = _inventory(inventory)
        if inv is None:
            return self._fail('bubblebeam_bag_inventory_invalid')
        cursors = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c in {'▶', '▷'}]
        if len(cursors) != 1 or cursors[0][0] != 5 or cursors[0][1] not in (4, 6, 8):
            return self._fail('bubblebeam_bag_cursor_not_verified')
        labels, visible, cancel = _item_labels(), [], None
        for y in (4, 6, 8, 10):
            label = normalize(rows[y][6:19])
            if label == 'CANCEL':
                cancel = y
                break
            matches = [(item, qty) for item, qty in inv if labels.get(item) == label and label]
            if len(matches) != 1:
                return self._fail('bubblebeam_bag_label_not_verified')
            item, qty = matches[0]
            printed = rows[y + 1][14:18].strip()
            if item in _KEY_ITEM_IDS:
                valid_qty = not printed
            else:
                match = re.fullmatch(r'×\s*(\d{1,2})', printed)
                valid_qty = bool(match and int(match.group(1)) == qty)
            if not valid_qty:
                return self._fail('bubblebeam_bag_quantity_not_verified')
            visible.append(item)
        offsets = [i for i in range(len(inv) - len(visible) + 1)
                   if [item for item, _ in inv[i:i + len(visible)]] == visible
                   and (cancel is None or i + len(visible) == len(inv))]
        if len(visible) < 2 or len(offsets) != 1:
            return self._fail('bubblebeam_bag_order_not_verified')
        current = offsets[0] + (cursors[0][1] - 4) // 2
        if current >= offsets[0] + len(visible):
            return self._fail('bubblebeam_bag_cursor_not_on_item')
        evidence = {'bag_visible_item_ids': visible, 'bag_visible_offset': offsets[0],
                    'bag_cursor_inventory_index': current}
        if closing:
            return _hint('b', 'close_verified_bag_after_bubblebeam', **evidence)
        target = next(i for i, (item, _) in enumerate(inv) if item == TM11)
        evidence['bag_tm11_inventory_index'] = target
        if target == current and TM11 in visible:
            self.stage = 'tm_selected'
            return _hint('a', 'select_verified_tm11', menu_label='TM11', **evidence)
        # TM11可能在先前CUT留下的背包頁上方；唯讀完整順序已證明其方向。
        action = 'up' if current > target else 'down'
        if self.bag_last_index is not None and (
                self.bag_last_action == 'down' and current < self.bag_last_index
                or self.bag_last_action == 'up' and current > self.bag_last_index):
            return self._fail('bubblebeam_bag_cursor_moved_opposite_to_verified_request')
        self.bag_stagnant = self.bag_stagnant + 1 if current == self.bag_last_index else 0
        if self.bag_stagnant >= MAX_STAGNANT_REQUESTS or self.bag_requests >= MAX_BAG_REQUESTS:
            return self._fail('bubblebeam_bag_scroll_limit')
        self.bag_last_index, self.bag_last_action = current, action
        self.bag_requests += 1
        self.stage = 'bag'
        return _hint(action, 'scroll_verified_bag_toward_tm11', bag_movement_requests=self.bag_requests, **evidence)

    def _party(self, rows, party):
        for i, mon in enumerate(party):
            y = i * 2
            if (normalize(rows[y][3:13]) != normalize(species_key(mon['species']))
                    or rows[y][13:16].strip() != str(mon['level'])):
                return self._fail('bubblebeam_tm_party_name_or_layout_not_verified')
            expected = 'ABLE' if 'BUBBLEBEAM' in reference()['species'][species_key(mon['species'])]['tmhm'] else 'NOT ABLE'
            if rows[y + 1][12:].strip() != expected:
                return self._fail('bubblebeam_tm_party_ability_not_verified')
        cursors = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == '▶']
        if len(cursors) != 1 or cursors[0][0] != 0 or cursors[0][1] not in range(1, len(party) * 2, 2):
            return self._fail('bubblebeam_tm_party_cursor_not_verified')
        current = (cursors[0][1] - 1) // 2
        self.stage = 'choose_learner'
        if current == self.target_index:
            self.learner_selected = True
        return _hint('a' if current == self.target_index else 'down' if current < self.target_index else 'up',
                     'choose_verified_nidorino', party_target_index=self.target_index)

    def _forget(self, rows):
        if not self.delete_confirmed or not self.seen_learner:
            return self._fail('bubblebeam_forget_without_verified_delete_yes')
        if [normalize(rows[8 + i][6:]) for i in range(4)] != ['LEER', 'TACKLE', 'HORNATTACK', 'POISONSTING']:
            return self._fail('bubblebeam_forget_four_move_layout_mismatch')
        cursors = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == '▶']
        if len(cursors) != 1 or cursors[0][0] != 5 or cursors[0][1] not in range(8, 12):
            return self._fail('bubblebeam_forget_cursor_not_verified')
        action = 'a' if cursors[0][1] == 8 else 'up'
        if action == 'a':
            self.stage = 'forget_selected'
        return _hint(action, 'forget_only_verified_leer', forgotten_move=LEER,
                     protected_moves=[33, 30, 40])

    def _partial(self, rows, lower):
        """僅固定下方逐字前綴可等待；實心游標、▼與錯誤指紋不得被遮蔽。"""
        if any(c in ''.join(rows) for c in ('▶', '▼')) or any(row.strip(' ▷') in {'YES', 'NO'} for row in rows):
            return None
        pages = {
            'tm_dialogue': _BOOT + _CONTAINED + _TEACH,
            'teach_question': _TEACH,
            'choose_learner': _INTRO,
            'learning_intro': _INTRO + _CAPACITY + _DELETE,
            'delete_question': _DELETE + _FORGET,
            'forget_menu': _FORGET,
            'forget_selected': _FORGOT + _LEARNED,
            'learned': _LEARNED,
        }.get(self.stage, ())
        if not lower:
            if self.stage in {'tm_dialogue', 'teach_question', 'choose_learner', 'learning_intro',
                              'delete_question', 'forget_menu', 'forget_selected', 'learned', 'closing'} and not normalize(''.join(rows)):
                return self._wait('await_known_tm11_transition_blank')
            return None
        matches = [p for p in pages if p.startswith(lower)]
        if not matches:
            return None
        # 完整Poof、FORGOT、And、learned必須交給下方明確確認分支，不永遠wait。
        if lower in matches and any(mark in ' '.join(rows[12:]) for mark in ('!', '...', '?')):
            if lower not in _TEACH + _DELETE + _FORGET:
                return None
        if any(p in _DELETE for p in matches) and self.seen_learner:
            self.stage = 'delete_question'
        elif any(p in _TEACH for p in matches) and self.seen_contained:
            self.stage = 'teach_question'
        return self._wait('await_verified_bubblebeam_text_prefix')

    def _context(self, rows, progress, overworld_ready):
        lower_raw, compact = ' '.join(rows[12:]), normalize(' '.join(rows))
        lower = normalize(lower_raw)
        moves = progress['party'][self.target_index]['moves']
        inv = _inventory(progress['inventory']) or []
        if self.stage == 'initial':
            if not overworld_ready or lower or any(c in ''.join(rows) for c in ('▶', '▼')) or self._start_menu(rows):
                return self._fail('bubblebeam_initial_overworld_not_verified')
            self.stage = 'start_menu'
            return _hint('start', 'open_items_for_tm11')
        # 明確拒絕頁與錯誤FORGOT優先於所有部分文字／動畫等待。
        if any(x in compact for x in ('DIDNOTLEARN', 'ABANDONLEARNING', 'STOPLEARNING',
                                      'NOTCOMPATIBLE', 'ALREADYKNOWS', 'HMCANT', 'CANTBEDELETED')):
            return self._fail('bubblebeam_learning_rejected_or_abandoned')
        if re.search(r'\bFORGOT\b', lower_raw):
            if self.stage != 'forget_selected':
                return self._fail('bubblebeam_unexpected_forget_message')
            if not any(p.startswith(lower) for p in _FORGOT):
                return self._fail('bubblebeam_forgot_wrong_move_or_learner')
        if 'ITCONTAINED' in lower and not any(p.startswith(lower) for p in _CONTAINED):
            return self._fail('bubblebeam_contained_wrong_move')
        if 'CANTLEARN' in compact and not any(p.startswith(lower) for p in _CAPACITY):
            return self._fail('bubblebeam_cannot_learn_message')
        if moves == AFTER_MOVES and inv == self.inventory_after and overworld_ready and not self.seen_learned:
            return self._fail('bubblebeam_expected_move_without_learned_receipt')
        if self.seen_learned and moves == AFTER_MOVES and inv == self.inventory_after and overworld_ready:
            if lower or any(c in ''.join(rows) for c in ('▶', '▼')) or self._start_menu(rows):
                return self._fail('bubblebeam_overworld_completion_conflicts_with_menu')
            self.stage = 'complete'
            return {'phase': 'tm_teaching_complete', 'objective': 'Wait.', 'available_actions': ['wait'],
                    'tm_teaching_complete': True, 'tm_teaching_kind': 'teach_bubblebeam',
                    'moves_verified': list(moves), 'tm_consumed': TM11, 'tm_quantity_used': 1,
                    'forgotten_move': LEER, 'protected_moves': [33, 30, 40], 'sources': SOURCES}
        # 完整忘招選單優先於逐字提示；不把尚未畫完的Which m與殘留HUD當成錯誤四招。
        move_cursor = any(rows[y][5] == '▶' for y in range(8, 12))
        all_move_labels = [normalize(rows[8 + i][6:]) for i in range(4)] == ['LEER', 'TACKLE', 'HORNATTACK', 'POISONSTING']
        if self.stage in {'forget_menu', 'forget_selected'} and (move_cursor or all_move_labels):
            return self._forget(rows)
        partial = self._partial(rows, lower)
        if partial:
            return partial
        if lower in _FORGOT and self.stage == 'forget_selected':
            return self._text_a(rows, 'advance_verified_leer_forget_page')
        if lower in _LEARNED and 'NIDORINOLEARNEDBUBBLEBEAM' == lower:
            if self.stage not in {'forget_selected', 'learned'} or moves != AFTER_MOVES:
                return self._fail('bubblebeam_learned_message_without_expected_transaction')
            if (any('▶' in row for row in rows)
                    or not re.search(r'BUBBLEBEAM!\s*[▼ ]*$', lower_raw)):
                return self._fail('bubblebeam_learned_receipt_incomplete_or_cursor_conflict')
            self.seen_learned, self.stage = True, 'learned'
            return _hint('a', 'dismiss_verified_bubblebeam_learned')
        if self.stage in {'learned', 'closing'}:
            if inv != self.inventory_after:
                return self._fail('bubblebeam_tm11_not_consumed_after_learning')
            self.stage = 'closing'
            if self._start_menu(rows):
                return _hint('b', 'close_verified_start_menu_after_bubblebeam')
            if any(rows[y][5] == '▶' for y in (4, 6, 8)):
                return self._bag(rows, progress['inventory'], closing=True)
            return self._fail('bubblebeam_post_learning_screen_unrecognized')
        if self.stage in {'delete_question', 'forget_menu'} and lower in _FORGET:
            self.stage = 'forget_menu'
            return self._forget(rows)
        if self.stage in {'learning_intro', 'delete_question'} and (lower in _DELETE or lower == 'DELETEANOLDERMOVETOMAKEROOM'):
            if not self.seen_learner:
                return self._fail('bubblebeam_delete_without_verified_learner')
            self.stage = 'delete_question'
            self.delete_verified = lower in _DELETE or lower == 'DELETEANOLDERMOVETOMAKEROOM'
            return self._question(rows, 'delete', lower)
        if self.stage in {'tm_dialogue', 'teach_question'} and lower in _TEACH:
            if not self.seen_contained:
                return self._fail('bubblebeam_teach_question_without_verified_move')
            self.stage, self.teach_verified = 'teach_question', True
            return self._question(rows, 'teach', lower)
        if any(re.search(r'(?<![A-Z])YES(?![A-Z])',row) for row in rows) and any(re.search(r'(?<![A-Z])NO(?![A-Z])',row) for row in rows):
            if self.stage == 'teach_question' and self.teach_verified:
                return self._question(rows, 'teach', lower)
            if self.stage == 'delete_question' and self.delete_verified:
                return self._question(rows, 'delete', lower)
            return self._fail('bubblebeam_unknown_yes_no_question')
        if self.stage in {'teach_question', 'choose_learner'} and self.teach_verified and 'USETMONWHICHPOKEMON' == lower:
            return self._party(rows, progress['party'])
        if self.stage in {'choose_learner', 'learning_intro'} and self.learner_selected:
            # 首頁及續頁必須吻合固定尼多力諾／泡沫光線文字，不能泛A。
            known_intro = any(p.startswith(lower) for p in _INTRO) and (lower.startswith('NIDORINOISTRYINGTOLEARN') or self.seen_learner)
            capacity = any(p.startswith(lower) for p in _CAPACITY)
            if known_intro or capacity and self.seen_learner:
                if lower.startswith('NIDORINOISTRYINGTOLEARN'):
                    self.seen_learner = True
                self.stage = 'learning_intro'
                if '▼' in lower_raw or lower in _INTRO + _CAPACITY and any(p in lower_raw for p in ('!', '.')):
                    return self._text_a(rows, 'advance_verified_nidorino_learning_page')
        if self.stage == 'tm_dialogue' and lower in _BOOT:
            return self._text_a(rows, 'advance_verified_booted_tm')
        if self.stage == 'tm_dialogue' and lower in _CONTAINED:
            result = self._text_a(rows, 'advance_verified_bubblebeam_contained')
            if result.get('phase') != 'campaign_review':
                self.seen_contained = True
            return result
        if self._start_menu(rows) and self.stage in {'start_menu', 'bag'}:
            result = self._select(rows, 'ITEM', 'open_tm11_bag')
            if result.get('available_actions') == ['a', 'wait']:
                self.stage = 'bag'
            return result
        # 紅版道具子選單為兩列USE/TOSS，沒有CANCEL；真實TM11已核對
        # x15/y11與y13、active cursor x14。EXIT殘字屬背包背景。
        use_labels = {'USE':11, 'TOSS':13}
        if self.stage == 'tm_selected' and all(rows[y][15:].strip() == label
                and sum(bool(re.search(r'(?<![A-Z])'+label+r'(?![A-Z])',row)) for row in rows)==1
                for label,y in use_labels.items()):
            cursors=[(x,y) for y,row in enumerate(rows) for x,c in enumerate(row) if c=='▶']
            if len(cursors)!=1 or cursors[0] not in {(14,11),(14,13)}:
                return self._fail('bubblebeam_item_submenu_cursor_unverified')
            result = self._select(rows, 'USE', 'use_verified_tm11')
            if result.get('available_actions') == ['a', 'wait']:
                self.stage = 'tm_dialogue'
            return result
        if self.stage in {'bag', 'tm_selected'} and any(rows[y][5] == '▶' for y in (4, 6, 8)):
            return self._bag(rows, progress['inventory'])
        return self._fail('bubblebeam_screen_unrecognized')

    def _question(self, rows, kind, lower):
        known = _TEACH if kind == 'teach' else _DELETE + ('DELETEANOLDERMOVETOMAKEROOM',)
        if lower and lower not in known:
            return self._fail('bubblebeam_question_content_not_verified')
        if any(re.search(r'(?<![A-Z])YES(?![A-Z])',row) for row in rows) and any(re.search(r'(?<![A-Z])NO(?![A-Z])',row) for row in rows):
            positions = {label: [(m.start(), y) for y, row in enumerate(rows)
                                 for m in re.finditer(r'(?<![A-Z])' + label + r'(?![A-Z])', row)]
                         for label in ('YES', 'NO')}
            # 四人以上TM隊伍頁的NOT ABLE會被YES/NO框截成背景NO。
            # 僅Delete流程、已選正確學員及其原隊伍相容性可證明的固定
            # x12／奇數列殘字可排除；任何其他重複NO仍是矛盾。
            if kind=='delete' and self.learner_selected and self.seen_learner:
                background={(12,i*2+1) for i,mon in enumerate(self.baseline)
                            if i*2+1 in {7,9,11}
                            and 'BUBBLEBEAM' not in reference()['species'][species_key(mon['species'])]['tmhm']
                            and rows[i*2+1][12:14]=='NO' and not rows[i*2+1][14:].strip()}
                positions['NO']=[pos for pos in positions['NO'] if pos not in background]
            cursors = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == '▶']
            if positions != {'YES': [(16, 8)], 'NO': [(16, 10)]} or len(cursors) != 1 or cursors[0] not in {(15, 8), (15, 10)}:
                return self._fail('bubblebeam_yes_no_layout_not_verified')
            result = _hint('a' if cursors[0][1] == 8 else 'up',
                           'accept_teach_bubblebeam' if kind == 'teach' else 'accept_replace_leer', menu_label='YES')
            if result.get('available_actions') == ['a', 'wait']:
                self.stage = 'choose_learner' if kind == 'teach' else 'forget_menu'
                if kind == 'delete':
                    self.delete_confirmed = True
            return result
        if any('▶' in row or row.strip(' ▷') in {'YES', 'NO'} for row in rows):
            return self._fail('bubblebeam_yes_no_layout_not_verified')
        if '▼' in ''.join(rows) and ((kind == 'teach' and self.teach_verified) or (kind == 'delete' and self.delete_verified)):
            return self._text_a(rows, 'advance_verified_wrapped_' + kind + '_question')
        return self._wait('await_verified_' + kind + '_choices')
