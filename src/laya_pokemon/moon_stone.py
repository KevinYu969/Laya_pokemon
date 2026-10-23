"""月之石將唯一尼多力諾167進化尼多王7的純控制候選；不操作模擬器。

只回Laya按鍵子目標；進化的done文字與動畫全部wait。無教招、命名、
RAM／存檔存取或runner接入。來源及HP重算限制見指定研究MD。
"""
from copy import deepcopy
import math
import re

from .field_moves import _item_labels, _KEY_ITEM_IDS
from .party_control import command
from .team_strategy import normalize, species_key


SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE_ROOT = f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/'
SOURCES = [SOURCE_ROOT + path for path in (
    'engine/items/item_effects.asm#L759', 'engine/pokemon/evos_moves.asm#L116',
    'engine/movie/evolution.asm#L142', 'engine/menus/party_menu.asm#L114',
    'engine/menus/start_sub_menus.asm#L408', 'home/pokemon.asm#L240',
    'data/text/text_3.asm#L35', 'data/pokemon/evos_moves.asm#L1895')]
MOON_STONE, NIDORINO, NIDOKING = 10, 167, 7
INTENT = {'kind': 'evolve_nidorino', 'item': MOON_STONE, 'species': NIDORINO,
          'evolves_to': NIDOKING}
_MOON_ABILITIES = {4, 100, 167, 168}
_NEW_MOVE_LEVELS = {8, 14, 23}
_PROMPT = 'USEITEMONWHICHPOKEMON'
_INTRO = 'WHATNIDORINOISEVOLVING'
_EVOLVED = 'NIDORINOEVOLVEDINTONIDOKING'


def _rows(text):
    cells = text.get('cells') if isinstance(text, dict) else None
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(row, (list, tuple)) or len(row) != 20
                   or any(not isinstance(c, str) or (len(c) != 1 and not (y >= 12 and c == "'t"))
                          for c in row) for y, row in enumerate(cells))):
        return None
    return [''.join('t' if c == "'t" else c for c in row).upper() for row in cells]


def _inventory(items):
    if (not isinstance(items, list) or len(items) > 20
            or any(not isinstance(x, dict) or set(x) != {'item', 'quantity'}
                   or type(x['item']) is not int or not 1 <= x['item'] <= 255
                   or type(x['quantity']) is not int or not 1 <= x['quantity'] <= 99 for x in items)):
        return None
    pairs = [(x['item'], x['quantity']) for x in items]
    return pairs if len({item for item, _ in pairs}) == len(pairs) else None


def _markers(rows, marker):
    return [(x, y) for y, row in enumerate(rows) for x, char in enumerate(row) if char == marker]


def _hint(action, tactic, **extra):
    meta = {'moon_stone_controller': 'candidate_nidorino_to_nidoking',
            'moon_stone_tactic': tactic, 'source_commit': SOURCE_COMMIT, 'sources': SOURCES, **extra}
    if action == 'wait':
        return {'phase': 'moon_stone_menu', 'objective': 'Wait.', 'available_actions': ['wait'],
                'controller_menu_verified': True, **meta}
    return command(action, 'moon_stone_menu', meta)


class MoonStoneController:
    """單次交易；now必須由呼叫端提供單調秒數，每次按鍵後重新觀測。

    目前只支援未改暱稱的NIDORINO；不接任意進化、改招或補學Thrash。
    未讀得完整intro與成功姓名文字，不因species7／道具消失就冒稱完成。
    """

    def __init__(self, intent, *, max_calls=240, max_waits=120, max_seconds=60.0):
        if (intent != INTENT or not isinstance(intent, dict)
                or any(type(intent.get(k)) is not int for k in ('item', 'species', 'evolves_to'))):
            raise ValueError('只允許明確item10／NIDORINO167→NIDOKING7')
        if (any(type(x) is not int or not 1 <= x <= 1000 for x in (max_calls, max_waits))
                or type(max_seconds) not in (int, float) or not math.isfinite(max_seconds)
                or not 0 < max_seconds <= 60):
            raise ValueError('操作／等待上限須為1..1000，時間為0..60秒')
        self.intent = deepcopy(intent)
        self.max_calls, self.max_waits, self.max_seconds = max_calls, max_waits, max_seconds
        self.calls = self.waits = self.bag_requests = self.bag_stagnant = 0
        self.stage, self.error = 'initial', None
        self.started_at = self.last_time = None
        self.baseline = self.inventory_before = self.inventory_after = None
        self.target_index = self.bag_cursor = self.bag_last_index = self.bag_last_action = None
        self.selected = self.seen_intro = self.seen_evolved = False

    def _fail(self, reason):
        self.error = reason
        return {'phase': 'campaign_review', 'objective': 'Wait.', 'available_actions': ['wait'],
                'review_reason': reason, 'moon_stone_controller': 'candidate_nidorino_to_nidoking',
                'source_commit': SOURCE_COMMIT, 'sources': SOURCES}

    def _wait(self, tactic):
        self.waits += 1
        if self.waits > self.max_waits:
            return self._fail('moon_stone_wait_budget_exhausted')
        return _hint('wait', tactic, safe_wait_count=self.waits, safe_wait_limit=self.max_waits)

    def context(self, text, progress, *, now, overworld_ready=False, battle_active=False):
        if self.error:
            return self._fail(self.error)
        self.calls += 1
        if (type(now) not in (int, float) or not math.isfinite(now) or now < 0
                or self.last_time is not None and now < self.last_time):
            return self._fail('moon_stone_clock_invalid')
        if self.started_at is None:
            self.started_at = now
        if self.calls > self.max_calls or now - self.started_at > self.max_seconds:
            return self._fail('moon_stone_transaction_budget_exhausted')
        self.last_time = now
        if battle_active is not False or type(overworld_ready) is not bool:
            return self._fail('moon_stone_requires_verified_nonbattle')
        rows = _rows(text)
        if rows is None:
            return self._fail('moon_stone_full_cells_required')
        error = self._check_progress(progress)
        if error:
            return self._fail(error)
        return self._context(rows, progress, overworld_ready)

    def _check_progress(self, progress):
        if not isinstance(progress, dict) or progress.get('party_read_valid') is not True:
            return 'moon_stone_party_not_verified'
        party = progress.get('party')
        if (not isinstance(party, list) or not 1 <= len(party) <= 6
                or type(progress.get('party_count')) is not int or progress['party_count'] != len(party)):
            return 'moon_stone_party_count_invalid'
        for mon in party:
            if (not isinstance(mon, dict) or type(mon.get('species')) is not int
                    or species_key(mon['species']) is None
                    or not isinstance(mon.get('species_name'), str)
                    or normalize(mon['species_name']) != normalize(species_key(mon['species']))
                    or any(type(mon.get(k)) is not int for k in ('level', 'exp', 'hp', 'max_hp', 'status'))
                    or not 1 <= mon['level'] <= 100 or not 0 <= mon['exp'] <= 0xFFFFFF
                    or not 1 <= mon['max_hp'] <= 999 or not 0 <= mon['hp'] <= mon['max_hp']
                    or not 0 <= mon['status'] <= 255
                    or any(not isinstance(mon.get(k), list) or len(mon[k]) != 4
                           or any(type(x) is not int or not 0 <= x <= limit for x in mon[k])
                           for k, limit in (('moves', 165), ('pp', 255)))):
                return 'moon_stone_party_fingerprint_invalid'
        inv = _inventory(progress.get('inventory'))
        if inv is None:
            return 'moon_stone_inventory_invalid'
        if self.baseline is None:
            targets = [i for i, mon in enumerate(party) if mon['species'] == NIDORINO]
            if len(targets) != 1 or any(mon['species'] == NIDOKING for mon in party):
                return 'moon_stone_unique_initial_nidorino_required'
            if not any(item == MOON_STONE for item, _ in inv):
                return 'moon_stone_item10_missing'
            if party[targets[0]]['level'] in _NEW_MOVE_LEVELS:
                return 'moon_stone_current_level_would_enter_move_learning'
            self.target_index, self.baseline = targets[0], deepcopy(party)
            self.inventory_before = inv
            self.inventory_after = [(item, qty - (item == MOON_STONE)) for item, qty in inv
                                    if item != MOON_STONE or qty > 1]
        if len(party) != len(self.baseline):
            return 'moon_stone_party_size_changed'
        for i, (mon, old) in enumerate(zip(party, self.baseline)):
            if i != self.target_index:
                if mon != old:
                    return 'moon_stone_other_member_changed'
            elif mon != old:
                if not self.selected or mon['species'] != NIDOKING:
                    return 'moon_stone_target_changed_before_selection_or_wrong_species'
                protected = set(old) | set(mon)
                protected -= {'species', 'species_name', 'hp', 'max_hp'}
                if any(k not in old or k not in mon or old[k] != mon[k] for k in protected):
                    return 'moon_stone_target_protected_data_changed'
                delta = mon['max_hp'] - old['max_hp']
                if delta < 0 or mon['hp'] != old['hp'] + delta:
                    return 'moon_stone_target_hp_delta_invalid'
                if not self.seen_evolved:
                    return 'moon_stone_new_species_without_visible_success'
        if inv not in (self.inventory_before, self.inventory_after):
            return 'moon_stone_inventory_change_not_exactly_one_item10'
        if inv == self.inventory_after and (not self.selected or party[self.target_index]['species'] != NIDOKING):
            return 'moon_stone_consumed_before_target_evolution'
        if self.stage in {'closing', 'complete'} and (
                party[self.target_index]['species'] != NIDOKING or inv != self.inventory_after):
            return 'moon_stone_completed_fingerprint_reverted'
        return None

    @staticmethod
    def _start_menu(rows):
        return all(rows[y][12:19].strip() == label
                   for y, label in ((2, 'POKÉDEX'), (4, 'POKÉMON'), (6, 'ITEM')))

    def _start_choice(self, rows, *, closing=False):
        for y, label in ((2, 'POKÉDEX'), (4, 'POKÉMON'), (6, 'ITEM')):
            positions = [(m.start(), yy) for yy, row in enumerate(rows)
                         for m in re.finditer(r'(?<![A-ZÉ])' + label + r'(?![A-ZÉ])', row)]
            if positions != [(12, y)]:
                return self._fail('moon_stone_start_label_not_unique')
        active, inactive = _markers(rows, '▶'), _markers(rows, '▷')
        allowed = {(11, y) for y in (2, 4, 6, 8, 10, 12, 14)}
        if closing and not active and inactive == [(11, 6)] and not _markers(rows, '▼'):
            return self._wait('await_start_redraw_with_inactive_item_cursor')
        if inactive or len(active) != 1 or active[0] not in allowed:
            return self._fail('moon_stone_start_cursor_invalid')
        if closing:
            return _hint('b', 'close_verified_start_menu')
        y = active[0][1]
        if y == 6:
            self.stage = 'bag'
        return _hint('a' if y == 6 else 'up' if y > 6 else 'down',
                     'select_verified_start_item', menu_label='ITEM')

    def _bag(self, rows, inventory, *, closing=False, pending=False):
        inv = _inventory(inventory)
        markers = _markers(rows, '▶') + _markers(rows, '▷')
        if inv is None or len(markers) != 1 or markers[0][0] != 5 or markers[0][1] not in (4, 6, 8):
            return self._fail('moon_stone_bag_cursor_invalid')
        labels, visible, cancel = _item_labels(), [], None
        for y in (4, 6, 8, 10):
            label = normalize(rows[y][6:19])
            if label == 'CANCEL':
                cancel = y
                break
            matches = [(item, qty) for item, qty in inv if labels.get(item) == label and label]
            if len(matches) != 1:
                return self._fail('moon_stone_bag_label_invalid')
            item, qty = matches[0]
            printed = rows[y + 1][14:18].strip()
            match = re.fullmatch(r'×\s*(\d{1,2})', printed)
            if (item in _KEY_ITEM_IDS and printed
                    or item not in _KEY_ITEM_IDS and not (match and int(match.group(1)) == qty)):
                return self._fail('moon_stone_bag_quantity_invalid')
            visible.append(item)
        offsets = [i for i in range(len(inv) - len(visible) + 1)
                   if [item for item, _ in inv[i:i + len(visible)]] == visible
                   and (cancel is None or i + len(visible) == len(inv))]
        if len(offsets) != 1 or not visible and not (closing and not inv and cancel == 4):
            return self._fail('moon_stone_bag_order_invalid')
        current = offsets[0] + (markers[0][1] - 4) // 2
        if current >= len(inv) and not (closing and cancel == markers[0][1]):
            return self._fail('moon_stone_bag_cursor_not_on_item')
        evidence = {'bag_visible_item_ids': visible, 'bag_visible_offset': offsets[0],
                    'bag_cursor_inventory_index': current}
        if not _markers(rows, '▶') or pending:
            return self._wait('await_active_bag_or_selected_item_transition')
        if closing:
            return _hint('b', 'close_verified_bag_after_evolution', **evidence)
        target = next(i for i, (item, _) in enumerate(inv) if item == MOON_STONE)
        if current == target and MOON_STONE in visible:
            self.stage, self.bag_cursor = 'stone_selected', markers[0]
            return _hint('a', 'select_only_verified_moon_stone', menu_label='MOON STONE', **evidence)
        action = 'up' if current > target else 'down'
        if self.bag_last_index is not None and (
                self.bag_last_action == 'down' and current < self.bag_last_index
                or self.bag_last_action == 'up' and current > self.bag_last_index):
            return self._fail('moon_stone_bag_moved_opposite_to_request')
        self.bag_stagnant = self.bag_stagnant + 1 if current == self.bag_last_index else 0
        if self.bag_stagnant >= 3 or self.bag_requests >= 20:
            return self._fail('moon_stone_bag_scroll_budget_exhausted')
        self.bag_last_index, self.bag_last_action = current, action
        self.bag_requests += 1
        return _hint(action, 'scroll_verified_bag_to_moon_stone', **evidence)

    def _use(self, rows, *, pending=False):
        positions = {label: [(m.start(), y) for y, row in enumerate(rows)
                             for m in re.finditer(r'(?<![A-Z])' + label + r'(?![A-Z])', row)]
                     for label in ('USE', 'TOSS')}
        if (positions != {'USE': [(15, 11)], 'TOSS': [(15, 13)]}
                or rows[11][15:].strip() != 'USE' or rows[13][15:].strip() != 'TOSS'):
            return self._fail('moon_stone_use_toss_labels_invalid')
        active, inactive = _markers(rows, '▶'), _markers(rows, '▷')
        if (len(active) != 1 or active[0] not in {(14, 11), (14, 13)}
                or inactive not in ([], [self.bag_cursor])):
            return self._fail('moon_stone_use_toss_cursor_invalid')
        if pending:
            if active[0] != (14, 11):
                return self._fail('moon_stone_use_cursor_changed_after_request')
            return self._wait('await_party_after_single_use_request')
        if active[0][1] == 11:
            self.stage = 'choose_mon'
        return _hint('a' if active[0][1] == 11 else 'up', 'use_verified_moon_stone', menu_label='USE')

    def _party(self, rows, party, *, pending=False):
        for i, mon in enumerate(party):
            y = 2 * i
            if (normalize(rows[y][3:13]) != normalize(species_key(mon['species']))
                    or rows[y][13:16].strip() != str(mon['level'])):
                return self._fail('moon_stone_party_name_level_layout_invalid')
            ability = 'ABLE' if mon['species'] in _MOON_ABILITIES else 'NOT ABLE'
            if rows[y + 1][12:].strip() != ability:
                return self._fail('moon_stone_party_stone_ability_invalid')
        if any(rows[y][3:16].strip() for y in range(2 * len(party), 12, 2)):
            return self._fail('moon_stone_party_extra_visible_member')
        active, inactive = _markers(rows, '▶'), _markers(rows, '▷')
        valid = {(0, 2 * i + 1) for i in range(len(party))}
        expected = (0, 2 * self.target_index + 1)
        if pending and (active and active != [expected] or inactive and inactive != [expected]):
            return self._fail('moon_stone_party_cursor_changed_after_target_request')
        if not active and (inactive == [] or len(inactive) == 1 and inactive[0] in valid):
            return self._wait('await_active_party_cursor_without_confirming_inactive_arrow')
        if inactive or len(active) != 1 or active[0] not in valid:
            return self._fail('moon_stone_party_cursor_invalid')
        if pending:
            return self._wait('await_evolution_after_single_target_request')
        current = (active[0][1] - 1) // 2
        if current == self.target_index:
            self.selected, self.stage = True, 'evolving'
        return _hint('a' if current == self.target_index else 'up' if current > self.target_index else 'down',
                     'choose_only_verified_nidorino', party_target_index=self.target_index)

    def _evolution(self, rows, progress, ready):
        raw = ' '.join(rows[12:18]).strip()
        lower = normalize(raw)
        evolved = progress['party'][self.target_index]['species'] == NIDOKING
        consumed = _inventory(progress['inventory']) == self.inventory_after
        # 成功文字已見且精確結果成立後，先辨識正常回背包／START的active游標。
        if self.seen_evolved and evolved and consumed and lower not in {_INTRO, _EVOLVED}:
            self.stage = 'closing'
            return self._closing(rows, progress, ready)
        # source的done文字不需要A，允許的舊游標只有已選隊員的空心背景。
        if (_markers(rows, '▶') or _markers(rows, '▷') not in ([], [(0, 2 * self.target_index + 1)])
                or _markers(rows, '▼')):
            return self._fail('moon_stone_evolution_unverified_menu_marker')
        intro_pattern = r'WHAT\?\s+NIDORINO\s+IS\s+EVOLVING'
        evolved_pattern = r'NIDORINO\s+EVOLVED\s+INTO\s+NIDOKING'
        if lower == _INTRO and re.fullmatch(intro_pattern + '!', raw):
            if self.seen_evolved:
                return self._fail('moon_stone_intro_after_success')
            self.seen_intro = True
            return self._wait('observe_complete_named_intro_without_pressing_a')
        if lower == _EVOLVED and re.fullmatch(evolved_pattern + '!', raw):
            if not self.seen_intro:
                return self._fail('moon_stone_success_without_visible_intro')
            self.seen_evolved = True
            return self._wait('observe_complete_named_evolution_without_pressing_a')
        if (lower == _INTRO and not re.fullmatch(intro_pattern, raw)
                or lower == _EVOLVED and not re.fullmatch(evolved_pattern, raw)):
            return self._fail('moon_stone_named_evolution_punctuation_invalid')
        if evolved and not self.seen_evolved:
            return self._fail('moon_stone_new_species_without_visible_success')
        if ready:
            return self._fail('moon_stone_overworld_before_complete_transaction')
        if not lower or (not self.seen_evolved and (_INTRO.startswith(lower) or _EVOLVED.startswith(lower))):
            return self._wait('await_only_known_evolution_text_or_animation')
        return self._fail('moon_stone_evolution_screen_unrecognized')

    def _closing(self, rows, progress, ready):
        lower = normalize(''.join(rows[12:18]))
        if ready:
            if lower or any(_markers(rows, char) for char in ('▶', '▷', '▼')) or self._start_menu(rows):
                return self._fail('moon_stone_overworld_conflicts_with_visible_menu')
            self.stage = 'complete'
            return {**_hint('wait', 'named_evolution_and_exact_consumption_verified'),
                    'phase': 'moon_stone_complete', 'moon_stone_complete': True,
                    'evolved_from': NIDORINO, 'evolved_to': NIDOKING,
                    'stone_consumed': MOON_STONE, 'stone_quantity_used': 1,
                    'party_target_index': self.target_index, 'moves_unchanged': True,
                    'level_exp_pp_unchanged': True}
        if self._start_menu(rows):
            return self._start_choice(rows, closing=True)
        if (rows[2][12:19].strip() == 'POKÉDEX'
                and rows[4][12:19].strip() == 'POKÉMON'
                and not any(_markers(rows, c) for c in ('▶', '▷', '▼'))):
            # 實戰進化返回時START逐列重繪；只等待，不能提早B或宣告完成。
            return self._wait('await_partial_start_redraw_after_evolution')
        if rows[4][5] in {'▶', '▷'} or rows[6][5] in {'▶', '▷'} or rows[8][5] in {'▶', '▷'}:
            return self._bag(rows, progress['inventory'], closing=True)
        if not normalize(''.join(rows)):
            return self._wait('await_verified_bag_after_evolution')
        return self._fail('moon_stone_return_screen_unrecognized')

    def _context(self, rows, progress, ready):
        lower = normalize(''.join(rows[12:18]))
        if self.stage == 'initial':
            if (not ready or lower or any(_markers(rows, char) for char in ('▶', '▷', '▼'))
                    or self._start_menu(rows)):
                return self._fail('moon_stone_initial_overworld_required')
            self.stage = 'start_menu'
            return _hint('start', 'open_start_for_explicit_moon_stone_intent')
        if self.stage in {'complete', 'closing'}:
            return self._closing(rows, progress, ready)
        if self.stage == 'evolving':
            if lower == _PROMPT:
                return self._party(rows, progress['party'], pending=True)
            return self._evolution(rows, progress, ready)
        if self.stage == 'start_menu' and self._start_menu(rows):
            return self._start_choice(rows)
        if self.stage == 'bag' and self._start_menu(rows):
            return self._wait('await_bag_after_single_item_request')
        if self.stage in {'stone_selected', 'choose_mon'} and ('USE' in rows[11] or 'TOSS' in rows[13]):
            return self._use(rows, pending=self.stage == 'choose_mon')
        if self.stage == 'choose_mon':
            if lower == _PROMPT:
                return self._party(rows, progress['party'])
            if lower and _PROMPT.startswith(lower) and not _markers(rows, '▶'):
                return self._wait('await_complete_item_party_prompt')
        if self.stage in {'bag', 'stone_selected'} and any(rows[y][5] in {'▶', '▷'} for y in (4, 6, 8)):
            return self._bag(rows, progress['inventory'], pending=self.stage == 'stone_selected')
        if not normalize(''.join(rows)) and not ready:
            return self._wait('await_known_menu_transition_blank')
        return self._fail('moon_stone_screen_unrecognized')
