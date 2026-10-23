"""Route12 指定位置正常吹笛的純候選；不操作模擬器、不負責捕捉。

呼叫端須提供同一次觀測的 decoder、progress、位置及既有 battle_state。
frame 只防重送／倒退，不能代替執行緒同步；沒有 getter、RAM 或檔案操作。
來源與未校準限制見 outputs/research/snorlax-flute-controller-20261024.md。
"""
from copy import deepcopy
import math
import re

from .field_moves import _item_labels, _KEY_ITEM_IDS
from .observation import PROFILE as TEXT_PROFILE
from .party_control import command
from .team_strategy import normalize, species_key


SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE_ROOT = f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/'
SOURCES = [SOURCE_ROOT + path for path in (
    'scripts/Route12.asm#L24', 'engine/items/item_effects.asm#L1671',
    'engine/items/item_effects.asm#L1774', 'engine/menus/start_sub_menus.asm#L330',
    'data/items/use_overworld.asm#L1', 'data/text_boxes.asm#L28',
    'text/Route12.asm#L7', 'data/text/text_6.asm#L107')]
FLUTE, SNORLAX = 73, 132
INTENT = {'kind': 'wake_route12_snorlax', 'map_id': 23, 'player_x': 10,
          'player_y': 61, 'facing': 'down', 'snorlax_x': 10, 'snorlax_y': 62,
          'item': FLUTE, 'species': SNORLAX, 'level': 30}
_UPSTREAM_PROFILE = 'gen1-wrapper-ram-progress-v1-unvalidated'
_START = ((2, 'POKÉDEX'), (4, 'POKÉMON'), (6, 'ITEM'), (8, 'KEVIN'),
          (10, 'SAVE'), (12, 'OPTION'), (14, 'EXIT'))
_PLAYED = 'KEVINPLAYEDTHEPOKEFLUTE.'
_WOKE = 'SNORLAXWOKEUP!'
_RAGE = 'ITATTACKEDINAGRUMPYRAGE!'


def _rows(text):
    cells = text.get('cells') if isinstance(text, dict) else None
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(row, (list, tuple)) or len(row) != 20
                   or any(not isinstance(c, str) or len(c) != 1 for c in row) for row in cells)):
        return None
    return tuple(''.join(row).upper() for row in cells)


def _markers(rows, char):
    return [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == char]


def _positions(rows, label):
    return [(m.start(), y) for y, row in enumerate(rows)
            for m in re.finditer(r'(?<![A-ZÉ0-9])' + re.escape(label) + r'(?![A-ZÉ0-9])', row)]


def _inventory(value):
    if (not isinstance(value, list) or len(value) > 20
            or any(not isinstance(x, dict) or set(x) != {'item', 'quantity'}
                   or type(x['item']) is not int or not 1 <= x['item'] <= 250
                   or type(x['quantity']) is not int or not 1 <= x['quantity'] <= 99 for x in value)):
        return None
    pairs = [(x['item'], x['quantity']) for x in value]
    return pairs if len({i for i, _ in pairs}) == len(pairs) else None


def _party(progress):
    if (not isinstance(progress, dict) or progress.get('profile') != _UPSTREAM_PROFILE
            or progress.get('initialization_candidate') is not True
            or progress.get('party_read_valid') is not True):
        return None
    party, count = progress.get('party'), progress.get('party_count')
    if not isinstance(party, list) or type(count) is not int or not 1 <= count <= 6 or len(party) != count:
        return None
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
                       or any(type(v) is not int or not 0 <= v <= cap for v in mon[k])
                       for k, cap in (('moves', 165), ('pp', 255)))):
            return None
    return party


def _proof(text, frame):
    return (isinstance(text, dict) and text.get('profile') == TEXT_PROFILE
            and text.get('read_valid') is True and text.get('alignment_verified') is True
            and type(text.get('window_visible')) is bool and text.get('read_error') is None
            and ('observation_frame' not in text or type(text['observation_frame']) is int
                 and text['observation_frame'] == frame))


def _compact(raw):
    return re.sub(r'\s+', '', raw.replace('É', 'E'))


class PokeFluteController:
    """單次明確意圖：只喚醒並交棒，不宣稱捕獲或選擇戰鬥策略。

    ``location`` 必須含 map_id/x/y/facing；facing 是既有唯讀方向的 down。
    ``frame`` 由 caller 同次觀測提供。若其他輸入另有 observation_frame，
    也必須吻合；本類不替舊資料加 frame。now 是 caller 的單調秒數。
    handoff 需要已送一次合法 USE／吹笛提示確認、既有 wild SNORLAX
    旗標及可見 Lv30 HUD。裸來源預期 Lv30 不會被冒充為已讀到的等級。
    """

    def __init__(self, intent, *, max_calls=240, max_seconds=60, max_waits=120):
        if (not isinstance(intent, dict) or intent != INTENT
                or any(type(intent[k]) is not int for k in INTENT if type(INTENT[k]) is int)):
            raise ValueError('只允許 Route12 23(10,61)down，正常Flute73喚醒(10,62)SNORLAX132 Lv30')
        if (type(max_calls) is not int or not 1 <= max_calls <= 240
                or type(max_waits) is not int or not 1 <= max_waits <= 240
                or type(max_seconds) not in (int, float) or not math.isfinite(max_seconds)
                or not 0 < max_seconds <= 60):
            raise ValueError('上限為240次呼叫、240次等待及60秒；可縮短不可擴大')
        self.intent, self._contract = deepcopy(intent), deepcopy(INTENT)
        self.max_calls, self.max_waits, self.max_seconds = max_calls, max_waits, max_seconds
        self.calls = self.waits = self.scrolls = 0
        self.stage, self.error = 'initial', None
        self.started_at = self.last_time = self.last_frame = self.last_packet = None
        self.party_before = self.inventory_before = None
        self.pending_rows = self.selected_bag = self.bag_cursor = None
        self.initial_world_rows = None
        self.pending_start_row = None
        self.last_bag_index = None
        self.used = self.played_confirmed = self.woke_confirmed = False
        self.seen_woke = self.seen_rage = self.handed_off = False
        self.intro_confirmed = False

    def _hint(self, action, tactic, **extra):
        meta = {'poke_flute_controller': 'route12_candidate', 'poke_flute_tactic': tactic,
                'source_commit': SOURCE_COMMIT, 'sources': SOURCES, 'captured': False,
                'poke_flute_stage': self.stage, **extra}
        if action == 'wait':
            return {'phase': 'poke_flute_menu', 'objective': 'Wait.', 'available_actions': ['wait'],
                    'controller_menu_verified': True, **meta}
        return command(action, 'poke_flute_menu', meta)

    def _fail(self, reason):
        self.error = reason
        return {**self._hint('wait', 'stop_for_review'), 'phase': 'campaign_review',
                'controller_menu_verified': False, 'review_reason': reason}

    def _wait(self, reason):
        self.waits += 1
        if self.waits > self.max_waits:
            return self._fail('poke_flute_wait_budget_exhausted')
        return self._hint('wait', reason, safe_wait_count=self.waits)

    def _send(self, action, rows, tactic, **extra):
        self.pending_rows = rows
        return self._hint(action, tactic, **extra)

    def _handoff(self):
        self.handed_off, self.stage = True, 'handoff'
        return {**self._hint('wait', 'handoff_verified_wild_snorlax'),
                'phase': 'poke_flute_handoff', 'poke_flute_handoff': True,
                'handoff_kind': 'wild_battle_candidate_requires_separate_review',
                'wild_species': SNORLAX, 'visible_wild_level': 30,
                'flute_quantity_used': 0, 'party_and_inventory_unchanged': True,
                'handoff_observation_frame': self.last_frame,
                'fingerprint_evidence_scope': 'verified at latched handoff frame; later packets are not read',
                'capture_complete': False}

    def context(self, text, progress, *, location, battle_state, frame, now,
                overworld_ready=False, intent=None):
        """只回一個 Laya 子目標；錯誤及交棒均鎖存，後續永遠不再回按鍵。"""
        if self.handed_off:
            return self._handoff()
        if self.error:
            return self._fail(self.error)
        self.calls += 1
        if self.intent != self._contract or intent is not None and intent != self._contract:
            return self._fail('poke_flute_intent_changed')
        if (type(frame) is not int or frame < 0 or type(now) not in (int, float)
                or not math.isfinite(now) or now < 0
                or self.last_frame is not None and frame < self.last_frame
                or self.last_time is not None and now < self.last_time):
            return self._fail('poke_flute_clock_or_frame_invalid')
        if self.started_at is None:
            self.started_at = now
        if self.calls > self.max_calls or now - self.started_at > self.max_seconds:
            return self._fail('poke_flute_transaction_budget_exhausted')
        self.last_time = now
        if type(overworld_ready) is not bool or not _proof(text, frame):
            return self._fail('poke_flute_decoder_proof_required')
        rows = _rows(text)
        if rows is None:
            return self._fail('poke_flute_full_cells_required')
        if (not isinstance(location, dict) or any(type(location.get(k)) is not int for k in ('map_id', 'x', 'y'))
                or (location['map_id'], location['x'], location['y'], location.get('facing')) != (23, 10, 61, 'down')
                or 'facing_raw' in location and (type(location['facing_raw']) is not int or location['facing_raw'] != 0)):
            return self._fail('poke_flute_fixed_stance_required')
        for packet in (progress, location, battle_state):
            if (not isinstance(packet, dict) or 'observation_frame' in packet
                    and (type(packet['observation_frame']) is not int or packet['observation_frame'] != frame)):
                return self._fail('poke_flute_observation_frame_conflict')
        inventory = _inventory(progress.get('inventory'))
        if inventory is None or inventory.count((FLUTE, 1)) != 1:
            return self._fail('poke_flute_unique_quantity_one_required')
        if self.inventory_before is not None and inventory != self.inventory_before:
            return self._fail('poke_flute_inventory_changed')
        text_proof = tuple(text.get(key) for key in ('profile', 'read_valid', 'alignment_verified', 'window_visible', 'read_error'))
        packet = (rows, text_proof, deepcopy(progress), deepcopy(location), deepcopy(battle_state), overworld_ready)
        if self.last_frame == frame:
            if packet != self.last_packet:
                return self._fail('poke_flute_same_frame_changed_packet')
            return self._wait('same_frame_no_resend')
        self.last_frame, self.last_packet = frame, packet
        battle = self._battle(battle_state, rows)
        if battle == 'invalid':
            return self._fail('poke_flute_battle_state_unknown_or_wrong_opponent')
        if battle != 'none' and not (self.used and self.played_confirmed):
            return self._fail('poke_flute_battle_before_verified_use')
        party = _party(progress)
        if party is None:
            if battle in {'candidate', 'pending_level','intro_prompt'}:
                return self._wait('await_readable_party_during_verified_battle_transition')
            return self._fail('poke_flute_readable_party_required')
        if not any(mon['hp'] > 0 for mon in party):
            return self._fail('poke_flute_no_healthy_party')
        if self.party_before is not None and party != self.party_before:
            return self._fail('poke_flute_party_changed')
        if progress.get('player_name_raw') != 'KEVIN':
            return self._fail('poke_flute_player_name_not_verified')
        events = progress.get('story_event_bits', {})
        if not isinstance(events, dict) or 'beat_route12_snorlax' in events and events['beat_route12_snorlax'] is not False:
            return self._fail('poke_flute_snorlax_already_resolved_or_unknown')
        if self.party_before is None:
            self.party_before, self.inventory_before = deepcopy(party), list(inventory)
        if battle=='intro_prompt':
            if getattr(self,'intro_confirmed',False):
                return self._wait('await_hud_after_single_complete_wild_intro')
            self.intro_confirmed=True
            return self._send('a',rows,'advance_complete_wild_snorlax_intro_to_reveal_hud')
        if battle == 'candidate':
            return self._handoff()
        if battle == 'pending_level':
            return self._wait('await_visible_level30_without_intervening_in_battle')
        if overworld_ready and (text['window_visible'] or _markers(rows, '▶') or _markers(rows, '▷')
                                or _markers(rows, '▼') or ''.join(rows[12:18]).strip()):
            return self._fail('poke_flute_overworld_conflicts_with_visible_ui')
        if self.pending_rows == rows:
            return self._wait('await_changed_observation_after_single_request')
        self.pending_rows = None
        if self.stage == 'initial':
            if (not overworld_ready or text['window_visible'] or any(c in ''.join(rows) for c in '▶▷▼')
                    or ''.join(rows[12:18]).strip()
                    or any(_positions(rows, label) for _, label in _START)):
                return self._fail('poke_flute_initial_verified_overworld_required')
            # 未校準的野外字碼不能成為之後的「可信背景」；尤其不可將
            # YES／Delete等上方文字先存成baseline，再讓袋／USE沿用。
            if re.search(r'[A-ZÉ0-9]', ''.join(rows)):
                return self._fail('poke_flute_initial_readable_text_not_verified')
            self.stage = 'start_opening'
            self.initial_world_rows = rows
            return self._send('start', rows, 'open_start_once')
        if self.stage in {'start_opening', 'bag_opening'}:
            if self._start_present(rows):
                return self._start(rows, pending=self.stage == 'bag_opening')
            if self.stage == 'start_opening':
                return self._blank_or_fail(rows, 'await_start_after_single_start')
            return self._bag(rows, inventory)
        if self.stage == 'bag':
            return self._bag(rows, inventory)
        if self.stage == 'flute_selected':
            if _positions(rows, 'USE') or _positions(rows, 'TOSS'):
                return self._use(rows)
            return self._bag(rows, inventory, pending=True)
        if self.stage == 'flute_used':
            if _positions(rows, 'USE') or _positions(rows, 'TOSS'):
                return self._use(rows, pending=True)
            return self._dialogue(rows)
        return self._fail('poke_flute_stage_unknown')

    def _battle(self, state, rows):
        if state.get('raw') == 0 and type(state.get('raw')) is int and state.get('active') is False and state.get('kind') == 'none':
            return 'none'
        if (type(state.get('raw')) is not int or state['raw'] != 1 or state.get('active') is not True
                or state.get('kind') != 'wild'):
            return 'invalid'
        for field in ('opponent_species', 'wild_opponent_species'):
            value = state.get(field)
            if not (type(value) is int and value == SNORLAX or type(value) is str and value == 'SNORLAX'):
                return 'invalid'
        for field in ('enemy_level', 'opponent_level', 'level'):
            if field in state and (type(state[field]) is not int or state[field] != 30):
                return 'invalid'
        if any(_positions(rows, word) for word in ('YES', 'NO', 'USE', 'TOSS', 'STATS', 'SWITCH', 'CANCEL')):
            return 'invalid'
        if (_markers(rows, '▷') or _markers(rows, '▼') not in ([], [(18, 16)])
                or _markers(rows, '▶') not in ([], [(9, 14)], [(9, 16)], [(15, 14)], [(15, 16)])):
            return 'invalid'
        if normalize(rows[0]) != 'SNORLAX':
            expected=[[' ']*20 for _ in range(18)]
            for x,y,label in ((1,14,'WILD SNORLAX'),(1,16,'APPEARED!'),(18,16,'▼')):
                expected[y][x:x+len(label)]=list(label)
            # 原生Wild appeared先等待A，之後才畫敵方HUD；完整固定提示
            # 可單次確認以顯示等級，但在可見Lv30前絕不標交棒完成。
            if rows==tuple(''.join(r) for r in expected):return 'intro_prompt'
            return 'pending_level' if not rows[0].strip() and not _markers(rows, '▶') else 'invalid'
        level = normalize(rows[1])
        if not level:
            return 'pending_level'
        if level not in {'30', 'L30', 'LV30'}:
            return 'invalid'
        if len(_positions(rows[:4], 'SNORLAX')) != 1:
            return 'invalid'
        lower = _compact(' '.join(row.replace('▼', ' ') for row in rows[12:18]))
        intro = 'WILDSNORLAXAPPEARED!'
        go_pages = {'GO!' + mon['species_name'] + '!' for mon in self.party_before or []}
        if lower == intro or lower in go_pages:
            return 'candidate'
        if not lower or (intro.startswith(lower) or any(page.startswith(lower) for page in go_pages)) and not _markers(rows, '▼'):
            return 'pending_level'
        if ({word: _positions(rows[12:], word) for word in ('FIGHT', 'ITEM', 'RUN')}
                != {'FIGHT': [(10, 2)], 'ITEM': [(10, 4)], 'RUN': [(16, 4)]}):
            return 'invalid'
        if _markers(rows, '▼') or rows[14][16:20].strip() not in {'', 'PKMN'}:
            return 'invalid'
        expected = [[' '] * 20 for _ in range(6)]
        for x, y, label in ((10, 2, 'FIGHT'), (10, 4, 'ITEM'), (16, 4, 'RUN')):
            expected[y][x:x + len(label)] = list(label)
        expected[2][16:20] = list(rows[14][16:20])
        for x, y in _markers(rows, '▶'):
            if y < 12:
                return 'invalid'
            expected[y - 12][x] = '▶'
        return 'candidate' if rows[12:] == tuple(''.join(row) for row in expected) else 'invalid'

    @staticmethod
    def _start_present(rows):
        # 背包後方仍可能露出EXIT，不能只憑這個字把背包誤作START。
        return any(rows[y][12:19].strip() and label.startswith(rows[y][12:19].strip())
                   for y, label in _START[:3])

    def _start(self, rows, *, pending):
        active, inactive = _markers(rows, '▶'), _markers(rows, '▷')
        if _markers(rows, '▼'):
            return self._fail('poke_flute_start_prompt_conflict')
        complete = True
        expected = {y: label for y, label in _START}
        for y, label in _START:
            slot = rows[y][12:19].strip()
            if not label.startswith(slot) or _positions(rows, label) not in ([], [(12, y)]):
                return self._fail('poke_flute_start_layout_invalid')
            complete = complete and slot == label
        for y in range(1, 16):
            for x in range(11, 20):
                c = rows[y][x]
                target = expected.get(y, '')
                allowed = target[x - 12] if y in expected and 12 <= x < 12 + len(target) else ' '
                if c != ' ' and c != allowed and not (x == 11 and y in expected and c in '▶▷'):
                    return self._fail('poke_flute_start_unknown_content')
        for y, row in enumerate(rows):
            for x, c in enumerate(row):
                if 10 <= x <= 19 and 0 <= y <= 16:
                    if not (11 <= x <= 19 and 1 <= y <= 15) and c != ' ':
                        return self._fail('poke_flute_start_unknown_content')
                    continue
                if c != self.initial_world_rows[y][x]:
                    return self._fail('poke_flute_start_background_dialogue_conflict')
        if not complete:
            if active or inactive:
                return self._fail('poke_flute_start_partial_cursor_conflict')
            return self._wait('await_known_partial_start')
        if pending:
            if active not in ([], [(11, 6)]) or inactive not in ([], [(11, 6)]) or active and inactive:
                return self._fail('poke_flute_start_cursor_changed_after_item_request')
            return self._wait('await_bag_without_reselecting_item')
        if inactive or len(active) != 1 or active[0] not in {(11, y) for y in expected}:
            return self._fail('poke_flute_start_cursor_invalid')
        y = active[0][1]
        if self.pending_start_row is not None:
            previous = self.pending_start_row
            if y == previous:
                return self._wait('await_start_cursor_move_without_resend')
            expected_y = previous + (2 if previous < 6 else -2)
            if y != expected_y:
                return self._fail('poke_flute_start_cursor_moved_other_than_requested_step')
            self.pending_start_row = None
        if y == 6:
            self.stage = 'bag_opening'
        else:
            # pending_rows只擋相鄰相同畫面；此語意鎖跨越blank／partial，
            # 必須真正看到預期下一列才可再發出方向。
            self.pending_start_row = y
        return self._send('a' if y == 6 else 'down' if y < 6 else 'up', rows,
                          'select_only_verified_start_item', menu_label='ITEM')

    def _bag(self, rows, inventory, *, pending=False):
        if not any(rows[y][6:19].strip() for y in (4, 6, 8, 10)):
            return self._blank_or_fail(rows, 'await_bag_transition')
        # LIST_MENU_BOX只覆蓋(4,2)..(19,12)，其餘是原野外／START的
        # EXIT殘留。不能將任意上方／左側內容採納為selected_bag基線。
        for y, row in enumerate(rows):
            for x, c in enumerate(row):
                if 4 <= x <= 19 and 2 <= y <= 12:
                    if (y in (2, 3, 12) or x == 4) and c != ' ':
                        return self._fail('poke_flute_bag_unknown_content')
                    continue
                expected = 'EXIT'[x - 12] if y == 14 and 12 <= x < 16 else self.initial_world_rows[y][x]
                if c != expected:
                    return self._fail('poke_flute_bag_background_not_verified')
        markers = _markers(rows, '▶') + _markers(rows, '▷')
        if (len(markers) != 1 or markers[0][0] != 5 or markers[0][1] not in (4, 6, 8)
                or _markers(rows, '▼') not in ([], [(18, 11)])):
            return self._fail('poke_flute_bag_cursor_invalid')
        for y in range(12, 18):
            row = rows[y]
            if y == 14 and row[12:16] == 'EXIT':
                row = row[:12] + '    ' + row[16:]
            if row.strip():
                return self._fail('poke_flute_bag_unknown_lower_ui')
        labels, visible, cancel = _item_labels(), [], None
        for y in (4, 6, 8, 10):
            raw_label = rows[y][6:19].strip()
            if not re.fullmatch(r"[A-ZÉ0-9 .'-]+", raw_label):
                return self._fail('poke_flute_bag_label_characters_invalid')
            label = normalize(raw_label)
            if label == 'CANCEL':
                if raw_label != 'CANCEL':
                    return self._fail('poke_flute_bag_cancel_label_invalid')
                cancel = y
                break
            matches = [(item, qty) for item, qty in inventory if label and labels.get(item) == label]
            if len(matches) != 1:
                return self._fail('poke_flute_bag_item_label_invalid')
            item, qty = matches[0]
            if item == FLUTE and raw_label != 'POKÉ FLUTE':
                return self._fail('poke_flute_bag_flute_label_not_exact')
            printed = rows[y + 1][14:18].strip()
            match = re.fullmatch(r'×\s*(\d{1,2})', printed)
            if item in _KEY_ITEM_IDS and printed or item not in _KEY_ITEM_IDS and not (match and int(match[1]) == qty):
                return self._fail('poke_flute_bag_quantity_invalid')
            visible.append(item)
        occupied_rows = [4 + i * 2 for i in range(len(visible))]
        if cancel is not None:
            occupied_rows.append(cancel)
        for y in range(4, 12):
            for x, c in enumerate(rows[y]):
                allowed = (x in range(6, 19) and y in occupied_rows
                           or x == 5 and (x, y) == markers[0]
                           or x in range(14, 18) and y - 1 in occupied_rows and y - 1 != cancel
                           or (x, y) == (18, 11) and c == '▼')
                if 5 <= x <= 19 and c != ' ' and not allowed:
                    return self._fail('poke_flute_bag_unknown_content')
        offsets = [i for i in range(len(inventory) - len(visible) + 1)
                   if [item for item, _ in inventory[i:i + len(visible)]] == visible
                   and (cancel is None or i + len(visible) == len(inventory))]
        if len(offsets) != 1 or not visible:
            return self._fail('poke_flute_bag_order_invalid')
        current = offsets[0] + (markers[0][1] - 4) // 2
        target = next(i for i, (item, _) in enumerate(inventory) if item == FLUTE)
        if current >= len(inventory):
            return self._fail('poke_flute_bag_cursor_on_cancel')
        if pending:
            if current != target or markers[0] != self.bag_cursor:
                return self._fail('poke_flute_bag_cursor_changed_after_selection')
            return self._wait('await_use_menu_without_reselecting_flute')
        if _markers(rows, '▷'):
            return self._wait('await_active_verified_bag_cursor')
        if self.last_bag_index is not None and abs(current - self.last_bag_index) > 1:
            return self._fail('poke_flute_bag_cursor_jumped')
        if self.last_bag_index is not None and current != self.last_bag_index:
            expected = self.last_bag_index + (1 if self.last_bag_index < target else -1)
            if current != expected:
                return self._fail('poke_flute_bag_moved_opposite_to_request')
        self.stage = 'bag'
        if current == target and FLUTE in visible:
            self.stage, self.bag_cursor, self.selected_bag = 'flute_selected', markers[0], rows
            return self._send('a', rows, 'select_only_verified_flute', menu_label='POKé FLUTE')
        if self.last_bag_index == current:
            return self._wait('await_bag_cursor_move_without_resend')
        if self.scrolls >= 20:
            return self._fail('poke_flute_bag_scroll_budget_exhausted')
        self.scrolls += 1
        self.last_bag_index = current
        return self._send('down' if current < target else 'up', rows, 'scroll_verified_bag_to_flute',
                          bag_cursor_inventory_index=current, bag_visible_offset=offsets[0], bag_visible_item_ids=visible)

    def _use(self, rows, *, pending=False):
        if ({label: _positions(rows, label) for label in ('USE', 'TOSS')}
                != {'USE': [(15, 11)], 'TOSS': [(15, 13)]}
                or rows[11][15:].strip() != 'USE' or rows[13][15:].strip() != 'TOSS'):
            return self._fail('poke_flute_use_toss_layout_invalid')
        if (_markers(rows, '▶') != [(14, 11)] or _markers(rows, '▷') not in ([], [self.bag_cursor])
                or _markers(rows, '▼')):
            return self._fail('poke_flute_use_cursor_not_exactly_use')
        for y in range(4, 10):
            old = self.selected_bag[y]
            expected = old[:5] + '▷' + old[6:] if (5, y) == self.bag_cursor else old
            if rows[y][5:19] != expected[5:19]:
                return self._fail('poke_flute_selected_bag_background_changed')
        expected = [list(row) for row in self.selected_bag]
        expected[self.bag_cursor[1]][self.bag_cursor[0]] = '▷'
        for y in range(10, 15):
            expected[y][13:20] = [' '] * 7
        for x, y, label in ((15, 11, 'USE'), (15, 13, 'TOSS'), (14, 11, '▶')):
            expected[y][x:x + len(label)] = list(label)
        if rows != tuple(''.join(row) for row in expected):
            return self._fail('poke_flute_use_unknown_content')
        if pending:
            return self._wait('await_dialogue_after_single_use')
        self.used, self.stage = True, 'flute_used'
        return self._send('a', rows, 'use_flute_once_never_toss', menu_label='USE')

    def _blank_or_fail(self, rows, tactic):
        if any(c in ''.join(rows) for c in '▶▷▼') or ''.join(rows[12:18]).strip():
            return self._fail('poke_flute_unknown_transition_ui')
        if any(_positions(rows, label) for label in ('YES', 'NO', 'USE', 'TOSS', 'STATS', 'SWITCH', 'CANCEL')):
            return self._fail('poke_flute_unknown_transition_menu')
        if ''.join(rows).strip() and rows != self.initial_world_rows:
            return self._fail('poke_flute_unknown_transition_content')
        return self._wait(tactic)

    def _dialogue(self, rows):
        active, inactive, prompt = _markers(rows, '▶'), _markers(rows, '▷'), _markers(rows, '▼')
        if active or inactive or prompt not in ([], [(18, 16)]):
            return self._fail('poke_flute_dialogue_marker_conflict')
        if any(_positions(rows, label) for label in ('YES', 'NO', 'STATS', 'SWITCH', 'CANCEL')):
            return self._fail('poke_flute_dialogue_unknown_choices')
        # ItemUseReloadOverworldData先LoadCurrentMapView，再印下方訊息框；
        # 上方只能保留原地圖字碼或清空，不能藏入Delete／未知新對話。
        if any(c not in (' ', self.initial_world_rows[y][x])
               for y, row in enumerate(rows[:12]) for x, c in enumerate(row)):
            return self._fail('poke_flute_dialogue_background_not_verified')
        raw = ' '.join(row.replace('▼', ' ') for row in rows[12:18]).strip()
        compact = _compact(raw)
        pages = (_PLAYED,) if not self.played_confirmed else (_PLAYED, _WOKE, _RAGE)
        if not compact:
            if prompt:
                return self._fail('poke_flute_empty_prompt')
            return self._wait('await_known_flute_or_wake_transition')
        if not any(page.startswith(compact) for page in pages):
            return self._fail('poke_flute_unrecognized_dialogue')
        if compact not in pages:
            if prompt:
                return self._fail('poke_flute_partial_dialogue_has_prompt')
            return self._wait('await_known_partial_flute_or_wake_text')
        if compact == _PLAYED:
            if self.seen_woke or self.seen_rage:
                return self._fail('poke_flute_played_receipt_after_wake')
            if self.played_confirmed:
                return self._wait('await_music_without_reconfirming_played_receipt')
            if not prompt:
                return self._wait('await_played_receipt_prompt')
            self.played_confirmed = True
            return self._send('a', rows, 'confirm_complete_played_flute_prompt_once')
        if compact == _WOKE:
            if self.seen_rage:
                return self._fail('poke_flute_woke_after_final_rage')
            self.seen_woke = True
            if self.woke_confirmed or not prompt:
                return self._wait('await_wake_paragraph_or_battle_without_resend')
            self.woke_confirmed = True
            return self._send('a', rows, 'advance_verified_woke_paragraph_once')
        if prompt:
            return self._fail('poke_flute_unexpected_prompt_on_final_done_page')
        if self.seen_rage:
            return self._wait('await_battle_after_single_final_rage_confirmation')
        self.seen_rage = True
        # text_end(done)僅結束內層；Route12使用DisplayTextID，外層在
        # wDoNotWaitForButtonPressAfterDisplayingText=0時仍等待正常A/B。
        # 固定完整末頁沒有▼；只確認一次，重複畫面與空白不能再送A。
        return self._send('a', rows, 'confirm_final_rage_display_text_return_once')
