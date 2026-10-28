"""Indigo174(7,7) Lapras TM24 的純子目標候選；不送鍵、不推幀、不改RAM。

只有下一個 fresh 真觀測的 previous[-1] 才提交 pending；回傳 A 候選不是 ACK。
來源白名單是工程候選，仍須真畫面校準。與既有 HM context 完全分開。
"""
from copy import deepcopy
from hashlib import sha256
import json
import math
import re

from .hm_teaching import (_rows, _blank, _put, _clear, _serial, _subset,
                          _inventory, _label, _KEY_ITEMS)
from .party_control import command
from .team_strategy import reference, species_key, move_key

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCES = [f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/{path}' for path in (
    'engine/items/item_effects.asm', 'engine/pokemon/learn_move.asm',
    'data/text/text_6.asm', 'data/text/text_4.asm',
    'constants/item_constants.asm', 'data/pokemon/base_stats/lapras.asm',
    'data/moves/moves.asm', 'engine/menus/party_menu.asm', 'home/list_menu.asm')]
INTENT = dict(kind='teach_thunderbolt_lapras', species=19, item=224,
              move=85, replace_move=109, replace_index=3)
LOCATION = dict(map_id=174, x=7, y=7)
ROSTER = frozenset((19, 132, 102, 154, 35, 7))
BEFORE, AFTER = [57, 34, 58, 109], [57, 34, 58, 85]
MAX_SECONDS, MAX_FRAMES, MAX_CALLS, MAX_WAITS = 60, 3600, 240, 160
_BLANK = (' ' * 20,) * 18
_ACTIONS = frozenset(('up', 'down', 'left', 'right', 'a', 'b', 'start', 'wait'))

NATIVE_RETURN_REVIEW = dict(
    kind='tm24_native_return_redraw_review19073_v1', game_id='game29', source_frame=19073,
    source_location=dict(map_id=174, x=7, y=7),
    original_step_id='game29-indigo-lapras-tm24-20261028',
    original_step_sha256='471e9ed19fde89c4a661bf7fa7c70ab119d26517c66399c1cacba055863828aa',
    training_job_sha256='b7e9ffa51e38f7901204e1e8b12ae00abecc42cdcbb37c398db7e4a51aebe6bf',
    plan_bytes_sha256='fe52e2c3c979c27573c365daf9eff4c730befce1742908c313c841762a828f9e',
    source_progress_sha256='7a6924ad5a0e0dd4fa82e92cf961044801ad2b84f6f95244a9c42c2c08e8341f',
    evidence=dict(review_sha256='aba4a5b7bbc3c0317f1d99c44497f9fc1254f196a5b88e308de072a328936cda',
        state_sha256='e42fe436f414122f47e7c8129d9a08797758a13cbfbd75a2b2bede197ffea716',
        preflight_sha256='f855a3fa75e03e61d62346cf6b8d71c12fdc76dd19e14c95783c922958dbf547'))


def _review_sha(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _int(value, low, high):
    return type(value) is int and low <= value <= high


def _intent(value):
    return (isinstance(value, dict) and value == INTENT
            and all(type(value[k]) is type(v) for k, v in INTENT.items()))


def _idle(movement, frame):
    return (isinstance(movement, dict)
            and movement.get('profile') == 'gen1-arrow-movement-source-v1'
            and movement.get('source_commit') == SOURCE_COMMIT
            and movement.get('read_valid') is True and movement.get('read_error') is None
            and type(movement.get('observation_frame')) is int
            and movement['observation_frame'] == frame and movement.get('spinning') is False
            and all(type(movement.get(k)) is int and movement[k] == 0 for k in (
                'simulated_remaining', 'joy_ignore', 'walk_counter', 'movement_flags')))


class TM24TeachingController:
    """固定單次資源交易。錯誤鎖存、budget/pending可跨 bridge reload 保留。"""

    def __init__(self, intent):
        if not _intent(intent):
            raise ValueError('只允許 Lapras19 TM24/224→85 取代109/index3')
        self.intent = deepcopy(intent)
        self.stage, self.error = 'preflight', None
        self.calls = self.waits = 0
        self.started_at = self.start_frame = self.last_now = self.last_frame = None
        self.last_packet = self.pending = self.stale_rows = self.cursor_expected = None
        self.party_before = self.inventory_before = self.inventory_after = None
        self.money_before = self.player_name = self.target_index = None
        self.bag_offset = self.bag_cursor = None
        self.world_frame = self.closed_frame = None
        self.and_acked = self.learned_acked = self.consumed = False

    def _hint(self, action, tactic):
        meta = dict(tm24_controller=INTENT['kind'], tm24_stage=self.stage,
                    tm24_tactic=tactic, source_commit=SOURCE_COMMIT, sources=SOURCES)
        if action == 'wait':
            return dict(phase='tm24_menu', objective='Wait.', available_actions=['wait'], **meta)
        return command(action, 'tm24_menu', meta)

    def _fail(self, reason):
        if self.error is None:
            self.error = 'tm24_' + reason.removeprefix('tm24_')
        return dict(self._hint('wait', 'sticky_review'), phase='campaign_review',
                    review_reason=self.error, controller_menu_verified=False)

    def fail(self, reason):
        """Bridge owner/binding errors also latch the same original controller."""
        return self._fail(reason)

    def _wait(self, reason):
        self.waits += 1
        return (self._fail('wait_budget_exhausted') if self.waits > MAX_WAITS
                else self._hint('wait', reason))

    def _offer(self, action, rows, stage, tactic, *, cursor=None, flag=None):
        if self.pending is not None:
            return self._fail('pending_overwritten')
        self.pending = dict(action=action, frame=self.last_frame, rows=rows,
                            stage=stage, cursor=cursor, flag=flag)
        return self._hint(action, tactic)

    def _ack(self, previous):
        pending = self.pending
        if pending is None:
            return None
        if not previous or previous[-1] != pending['action']:
            return self._fail('actual_previous_did_not_ack_' + pending['action'])
        self.stage = pending['stage']
        self.stale_rows = pending['rows']
        self.cursor_expected = pending['cursor']
        if pending['flag']:
            setattr(self, pending['flag'], True)
        self.pending = None
        return None

    def _progress(self, p):
        if (not isinstance(p, dict) or p.get('profile') != 'gen1-wrapper-ram-progress-v1-unvalidated'
                or p.get('initialization_candidate') is not True or p.get('party_read_valid') is not True
                or type(p.get('party_count')) is not int or p['party_count'] != 6
                or not isinstance(p.get('party'), list) or len(p['party']) != 6):
            return 'progress_or_six_party_unverified'
        party, ref = p['party'], reference()
        if (ref.get('source_commit') != SOURCE_COMMIT
                or ref['moves']['THUNDERBOLT']['id'] != 85
                or ref['moves']['THUNDERBOLT']['pp'] != 15
                or 'THUNDERBOLT' not in ref['species']['LAPRAS']['tmhm']):
            return 'reference_contract_mismatch'
        for mon in party:
            if (not isinstance(mon, dict) or not _int(mon.get('species'), 1, 190)
                    or mon.get('species_name') != species_key(mon['species'])
                    or not _int(mon.get('level'), 1, 100) or not _int(mon.get('exp'), 0, 0xFFFFFF)
                    or not _int(mon.get('max_hp'), 1, 999) or not _int(mon.get('hp'), 1, mon['max_hp'])
                    or type(mon.get('status')) is not int or mon['status'] != 0
                    or any(not isinstance(mon.get(k), list) or len(mon[k]) != 4
                           or any(not _int(v, 0, hi) for v in mon[k])
                           for k, hi in (('moves', 165), ('pp', 255)))):
                return 'party_fingerprint_invalid'
            for move, pp in zip(mon['moves'], mon['pp']):
                name = move_key(move) if move else None
                if ((move == 0 and pp != 0) or move and (name is None
                        or (pp & 63) > ref['moves'][name]['pp'] * (5 + (pp >> 6)) // 5)):
                    return 'party_pp_invalid'
        if {mon['species'] for mon in party} != ROSTER:
            return 'fixed_roster_changed'
        inv = [] if p.get('inventory') == [] else _inventory(p.get('inventory'))
        if inv is None or not _int(p.get('money'), 0, 999999):
            return 'inventory_or_money_invalid'
        if self.party_before is None:
            index = next(i for i, mon in enumerate(party) if mon['species'] == 19)
            if party[index]['moves'] != BEFORE or (224, 1) not in inv:
                return 'initial_lapras_moves_or_unique_tm24_invalid'
            if not isinstance(p.get('player_name_raw'), str) or not re.fullmatch('[A-Z]{1,7}', p['player_name_raw']):
                return 'player_name_unverified'
            self.target_index, self.party_before = index, deepcopy(party)
            self.inventory_before, self.inventory_after = inv, [item for item in inv if item[0] != 224]
            self.money_before, self.player_name = p['money'], p['player_name_raw']
        if p['money'] != self.money_before or p.get('player_name_raw') != self.player_name:
            return 'money_or_player_changed'
        if inv == self.inventory_after:
            if not self.learned_acked:
                return 'tm_consumed_before_actual_learned_a'
            self.consumed = True
        elif inv != self.inventory_before or self.consumed:
            return 'inventory_difference_or_reversion'
        for index, (mon, old) in enumerate(zip(party, self.party_before)):
            if index != self.target_index:
                if mon != old:
                    return 'other_party_member_changed'
                continue
            pp = old['pp'][:3] + [15]
            after = dict(old, moves=AFTER, pp=pp)
            if mon == old:
                if self.learned_acked or self.consumed:
                    return 'learned_moves_missing_or_reverted'
            elif mon != after or not self.and_acked:
                return 'unexpected_or_premature_move_pp_change'
        return None

    def review_native_return_redraw(self, *, review_capsule, source_evidence):
        """Parent first proves the same native/bridge/binding/full peer mutex.

        This one named review changes only error/history. No context call, ACK,
        pending replacement, packet replacement, clock change or budget refund.
        """
        try:
            if (_review_sha(review_capsule) != _review_sha(NATIVE_RETURN_REVIEW)
                    or _review_sha(source_evidence) != _review_sha(NATIVE_RETURN_REVIEW['evidence'])
                    or self.error != 'tm24_unknown_or_out_of_stage_source_page'
                    or self.stage != 'native_return' or self.last_frame != 19073
                    or type(self.last_frame) is not int or self.pending is not None
                    or self.cursor_expected is not None or self.closed_frame is not None
                    or self.and_acked is not True or self.learned_acked is not True or self.consumed is not True
                    or not _intent(self.intent) or self.party_before is None or self.inventory_before is None
                    or type(self.calls) is not int or not 1 <= self.calls <= MAX_CALLS
                    or type(self.waits) is not int or not 0 <= self.waits <= MAX_WAITS
                    or type(self.start_frame) is not int or not 0 <= self.last_frame-self.start_frame <= MAX_FRAMES
                    or any(type(v) not in (int,float) or not math.isfinite(v) or v < 0
                           for v in (self.started_at,self.last_now))
                    or not 0 <= self.last_now-self.started_at <= MAX_SECONDS
                    or type(self.last_packet) is not tuple or len(self.last_packet) != 7
                    or getattr(self, 'native_return_review_history', None) not in (None, [])):
                return self._fail('native_return_review_unverified')
            text, progress, location, battle, movement, ready, previous = self.last_packet
            if (_rows(text) != _serial(self._start(6, '▷')) or ready is not False
                    or any(type(location.get(k)) is not int or location[k] != v for k,v in LOCATION.items())
                    or battle.get('kind') != 'none' or battle.get('active') is not False
                    or type(battle.get('raw')) is not int or battle['raw'] != 0
                    or type(battle.get('observation_frame')) is not int or battle['observation_frame'] != 19073
                    or not _idle(movement,19073) or type(previous) not in (list,tuple)
                    or not previous or previous[-1] != 'a'
                    or _review_sha(progress) != review_capsule['source_progress_sha256']
                    or any('observation_frame' in p and (type(p['observation_frame']) is not int
                            or p['observation_frame'] != 19073) for p in (text,progress,location))
                    or self._progress(progress) is not None):
                return self._fail('native_return_review_packet_unverified')
            preserved = {k: deepcopy(getattr(self,k)) for k in (
                'stage','calls','waits','started_at','start_frame','last_now','last_frame',
                'pending','cursor_expected','world_frame','closed_frame')}
            self.native_return_review_history = [dict(
                old_error=self.error, review_capsule=deepcopy(review_capsule), preserved=preserved,
                original_packet_sha256=_review_sha(self.last_packet),
                original_progress_sha256=_review_sha(progress))]
            self.error = None
            return dict(self._hint('wait','reviewed_native_return_redraw_wait'), tm24_native_return_reviewed=True)
        except (KeyError,TypeError,ValueError,AttributeError,IndexError,RecursionError):
            return self._fail('native_return_review_unverified')

    def context(self, text, progress, *, location, battle_state, movement, frame, now,
                overworld_ready=False, previous=()):
        if self.error:
            return self._fail(self.error)
        self.calls += 1
        if not _intent(self.intent):
            return self._fail('intent_changed')
        if (not _int(frame, 0, 0x7FFFFFFFFFFFFFFF)
                or type(now) not in (int, float) or not math.isfinite(now) or now < 0
                or self.last_frame is not None and frame < self.last_frame
                or self.last_now is not None and now < self.last_now):
            return self._fail('frame_or_clock_invalid')
        if self.started_at is None:
            self.started_at, self.start_frame = now, frame
        if (self.calls > MAX_CALLS or now - self.started_at > MAX_SECONDS
                or frame - self.start_frame > MAX_FRAMES):
            return self._fail('transaction_budget_exhausted')
        self.last_now = now
        if (not isinstance(previous, (list, tuple)) or len(previous) > 8
                or any(type(a) is not str or a not in _ACTIONS for a in previous)):
            return self._fail('actual_previous_invalid')
        rows = _rows(text)
        if rows is None or type(overworld_ready) is not bool:
            return self._fail('native_text_or_world_proof_invalid')
        if (any(not isinstance(p, dict) or 'observation_frame' in p and (
                type(p['observation_frame']) is not int or p['observation_frame'] != frame)
                for p in (text, progress, location, battle_state, movement))
                or any(type(p.get('observation_frame')) is not int or p['observation_frame'] != frame
                       for p in (battle_state, movement))):
            return self._fail('same_observation_frame_required')
        if any(type(location.get(k)) is not int or location[k] != v for k, v in LOCATION.items()):
            return self._fail('fixed_location_changed')
        if (battle_state.get('kind') != 'none' or battle_state.get('active') is not False
                or type(battle_state.get('raw')) is not int or battle_state['raw'] != 0):
            return self._fail('known_nonbattle_required')
        if (movement.get('profile') != 'gen1-arrow-movement-source-v1'
                or movement.get('source_commit') != SOURCE_COMMIT
                or movement.get('read_valid') is not True or movement.get('read_error') is not None
                or type(movement.get('spinning')) is not bool
                or any(not _int(movement.get(k), 0, 255) for k in
                       ('simulated_remaining', 'joy_ignore', 'walk_counter', 'movement_flags'))
                or movement['joy_ignore'] not in (0, 255)
                or movement['movement_flags'] & 0x38
                or movement['spinning'] != bool(movement['movement_flags'] & 0x80)):
            return self._fail('movement_observation_invalid')
        packet = deepcopy((text, progress, location, battle_state, movement, overworld_ready, previous))
        if frame == self.last_frame:
            if packet != self.last_packet:
                return self._fail('same_frame_conflicting_packet')
            return self._wait('same_frame_no_resend_or_ack')
        self.last_frame, self.last_packet = frame, packet
        ack = self._ack(previous)
        if ack:
            return ack
        error = self._progress(progress)
        if error:
            return self._fail(error)
        closed = (rows == _BLANK and text['window_visible'] is False
                  and overworld_ready and _idle(movement, frame))
        if self.stage == 'preflight':
            if not closed:
                return self._fail('two_closed_idle_world_preflight_required')
            if self.world_frame is None:
                self.world_frame = frame
                return self._wait('first_fresh_closed_idle_world')
            return self._offer('start', rows, 'start', 'open_start_after_two_fresh_worlds')
        if self.stage == 'complete':
            if not closed or not self.consumed or not self.learned_acked:
                return self._fail('completed_transaction_or_world_changed')
            return self._complete()
        if self.stage in ('native_return', 'close_bag', 'close_start') and closed:
            if self.stage != 'close_start' or not self.consumed or not self.learned_acked:
                return self._fail('world_closed_before_native_return_and_close')
            if self.closed_frame is None:
                self.closed_frame = frame
                return self._wait('first_fresh_closed_post_world')
            self.stage = 'complete'
            return self._complete()
        if self.stage == 'close_start' and self.closed_frame is not None:
            return self._fail('post_closed_world_not_stable')
        if overworld_ready:
            return self._fail('unexpected_overworld_before_close')
        if rows == self.stale_rows:
            return self._wait('actual_ack_wait_for_native_page_change')
        if rows == _BLANK:
            return self._wait('stage_local_blank_transition')
        views = self._views()
        matches = [(kind, key) for kind, key, view in views if rows == view]
        if not matches:
            if any(_subset(rows, view) for _, _, view in views):
                return self._wait('stage_local_source_text_drawing')
            return self._fail('unknown_or_out_of_stage_source_page')
        kind, key = matches[0]
        if kind == 'inactive':
            return self._wait('native_inactive_cursor')
        if kind == 'prompt_wait':
            return self._wait('await_true_native_prompt_arrow')
        if self.cursor_expected is not None:
            expected_kind, expected_key = self.cursor_expected
            actual_kind, actual_key = ('bag_index', key[0] + key[1]) if kind == 'bag' else (kind, key)
            if actual_kind != expected_kind or actual_key != expected_key:
                return self._fail('cursor_did_not_move_one_source_item')
            self.cursor_expected = None
        if kind == 'start':
            if self.stage == 'close_bag':
                return self._offer('b', rows, 'close_start', 'close_native_returned_start')
            if key == 6:
                return self._offer('a', rows, 'bag', 'open_item_bag')
            target = key + (2 if key < 6 else -2)
            return self._offer('down' if key < 6 else 'up', rows, 'start', 'move_start_cursor_once', cursor=('start', target))
        if kind == 'bag':
            offset, cursor = key
            if self.stage == 'native_return':
                if not self.consumed:
                    return self._wait('await_exact_tm24_consumption_before_close')
                return self._offer('b', rows, 'close_bag', 'close_verified_post_consumption_bag')
            current = offset + cursor
            target = self.inventory_before.index((224, 1))
            if current == target:
                self.bag_offset, self.bag_cursor = offset, cursor
                return self._offer('a', rows, 'use', 'select_exact_tm24')
            d = 1 if current < target else -1
            # Visible absolute bag index is checked after ACK, including scroll.
            return self._offer('down' if d == 1 else 'up', rows, 'bag', 'move_bag_cursor_once', cursor=('bag_index', current + d))
        if kind == 'use':
            if key == 13:
                return self._offer('up', rows, 'use', 'select_use_only', cursor=('use', 11))
            return self._offer('a', rows, 'boot', 'confirm_tm24_use')
        if kind in ('teach', 'delete'):
            if key == 10:
                return self._offer('up', rows, self.stage, 'select_' + kind + '_yes', cursor=(kind, 8))
            return self._offer('a', rows, 'party' if kind == 'teach' else 'forget', 'confirm_' + kind + '_yes')
        if kind == 'party':
            if key == self.target_index:
                return self._offer('a', rows, 'intro0', 'choose_only_lapras')
            d = 1 if key < self.target_index else -1
            return self._offer('down' if d == 1 else 'up', rows, 'party', 'move_learner_cursor_once', cursor=('party', key + d))
        if kind == 'forget':
            if key == 11:
                return self._offer('a', rows, 'poof', 'forget_only_confuse_ray_index3')
            return self._offer('down', rows, 'forget', 'move_forget_cursor_once', cursor=('forget', key + 1))
        transitions = dict(boot='contained', contained='teach', intro0='intro1', intro1='intro2',
                           intro2='intro3', intro3='delete_scroll', delete_scroll='delete',
                           poof='forgot', forgot='and', **{'and': 'learned', 'learned': 'native_return'})
        if kind in transitions:
            if kind == 'learned':
                mon = progress['party'][self.target_index]
                if not self.and_acked or mon['moves'] != AFTER or mon['pp'] != self.party_before[self.target_index]['pp'][:3] + [15]:
                    return self._fail('learned_receipt_without_exact_move_and_pp')
            return self._offer('a', rows, transitions[kind], 'ack_exact_' + kind + '_native_prompt',
                               flag='and_acked' if kind == 'and' else 'learned_acked' if kind == 'learned' else None)
        return self._fail('unsupported_source_stage')

    def _start(self, cursor, marker='▶'):
        r = _blank()
        for y, label in ((2, 'POKÉDEX'), (4, 'POKÉMON'), (6, 'ITEM'),
                         (8, self.player_name), (10, 'SAVE'), (12, 'OPTION'), (14, 'EXIT')):
            _put(r, 12, y, label)
        _put(r, 11, cursor, marker)
        return r

    def _bag(self, offset, cursor, marker='▶', *, post=False, arrow=False):
        inventory = self.inventory_after if post else self.inventory_before
        r = self._start(6)
        _clear(r, 4, 2, 19, 12)
        for n in range(4):
            index, y = offset + n, 4 + n * 2
            if index == len(inventory):
                _put(r, 6, y, 'CANCEL')
                break
            if index > len(inventory):
                break
            item, quantity = inventory[index]
            _put(r, 6, y, _label(item))
            if item not in _KEY_ITEMS:
                _put(r, 14, y + 1, f'×{quantity:2}')
        _put(r, 5, 4 + cursor * 2, marker)
        if arrow:
            _put(r, 18, 11, '▼')
        return r

    def _use(self, cursor=11, marker='▶'):
        r = self._bag(self.bag_offset, self.bag_cursor, '▷')
        _clear(r, 13, 10, 19, 15)
        _put(r, 15, 11, 'USE'); _put(r, 15, 13, 'TOSS'); _put(r, 14, cursor, marker)
        return r

    def _party(self, cursor, marker='▶'):
        r = _blank()
        for i, mon in enumerate(self.party_before):
            _put(r, 3, i * 2, mon['species_name'])
            _put(r, 13, i * 2, f"{mon['level']:3}")
            able = 'THUNDERBOLT' in reference()['species'][mon['species_name']]['tmhm']
            _put(r, 12, i * 2 + 1, 'ABLE' if able else 'NOT ABLE')
        _put(r, 0, cursor * 2 + 1, marker)
        _put(r, 1, 14, 'Use TM on which'); _put(r, 1, 16, 'POKéMON?')
        return r

    def _dialog(self, lines, *, party=False, arrow=None, question=None, marker='▶'):
        r = self._party(self.target_index, '▷') if party else self._use(11, '▷')
        _clear(r, 0, 12, 19, 17)
        if question is not None:
            _clear(r, 14, 7, 19, 12)
            _put(r, 16, 8, 'YES'); _put(r, 16, 10, 'NO'); _put(r, 15, question, marker)
        for y, text in lines:
            _put(r, 1, y, text)
        if arrow is not None:
            _put(r, 18, arrow, '▼')
        return r

    def _forget(self, cursor):
        r = self._party(self.target_index, '▷')
        _clear(r, 4, 7, 19, 12); _clear(r, 0, 12, 19, 17)
        for index, move in enumerate(BEFORE):
            _put(r, 6, 8 + index, move_key(move).replace('_', ' '))
        _put(r, 5, cursor, '▶')
        _put(r, 1, 14, 'Which move should'); _put(r, 1, 16, 'be forgotten?')
        return r

    def _views(self):
        """Only the current ACKed stage may recognize a source page."""
        out = []
        def add(kind, key, rows):
            out.append((kind, key, _serial(rows)))
        stage = self.stage
        if stage in ('start', 'close_bag', 'close_start'):
            for y in (2, 4, 6, 8, 10, 12, 14):
                if stage != 'close_start':
                    add('start', y, self._start(y))
                add('inactive', None, self._start(y, '▷'))
            if stage == 'close_bag':
                for offset in range(max(1, len(self.inventory_after))):
                    for cursor in range(min(3, len(self.inventory_after) - offset + 1)):
                        add('inactive', None, self._bag(offset, cursor, '▷', post=True))
        elif stage in ('bag', 'native_return'):
            post = stage == 'native_return'
            redraw = (post and self.and_acked is True and self.learned_acked is True and self.consumed is True)
            if redraw:
                # Success restores inactive Start buffer2, then redraws the bag.
                # It is never a Start action or a substitute for the real bag B.
                add('inactive', None, self._start(6, '▷'))
            inventory = self.inventory_after if post else self.inventory_before
            for offset in range(max(1, len(inventory))):
                for cursor in range(min(3, len(inventory) - offset + 1)):
                    for arrow in ((False, True) if offset + 3 < len(inventory) else (False,)):
                        add('bag', (offset, cursor), self._bag(offset, cursor, post=post, arrow=arrow))
                        add('inactive', None, self._bag(offset, cursor, '▷', post=post, arrow=arrow))
                        if redraw:
                            # BG copies one third per frame: OPTION may remain
                            # until the bag frame is complete; cursor is not active.
                            drawing = self._bag(offset, cursor, ' ', post=True, arrow=arrow)
                            _put(drawing, 12, 12, 'OPTION')
                            add('inactive', None, drawing)
        elif stage == 'use':
            for y in (11, 13):
                add('use', y, self._use(y)); add('inactive', None, self._use(y, '▷'))
        elif stage == 'party':
            for index in range(6):
                add('party', index, self._party(index)); add('inactive', None, self._party(index, '▷'))
        elif stage == 'forget':
            for y in range(8, 12):
                add('forget', y, self._forget(y))
            add('prompt_wait', None, self._dialog([(14, 'Which move should'), (16, 'be forgotten?')], party=True))
        else:
            lines = {
                'boot': [[(14, 'Booted up a TM!')]],
                'contained': [[(14, 'It contained'), (16, 'THUNDERBOLT!')]],
                'teach': [[(14, 'Teach THUNDERBOLT'), (16, 'to a POKéMON?')]],
                'intro0': [[(14, 'LAPRAS is'), (16, 'trying to learn')]],
                'intro1': [[(14, 'trying to learn'), (16, 'THUNDERBOLT!')], [(14, 'THUNDERBOLT!')]],
                'intro2': [[(14, 'But, LAPRAS'), (16, "can't learn more")]],
                'intro3': [[(14, "can't learn more"), (16, 'than 4 moves!')], [(14, 'than 4 moves!')]],
                'delete_scroll': [[(14, 'Delete an older'), (16, 'move to make room')]],
                'delete': [[(14, 'move to make room'), (16, 'for THUNDERBOLT?')]],
                'poof': [[(14, '1, 2 and...')], [(14, '1, 2 and... Poof!')]],
                'forgot': [[(14, 'LAPRAS forgot'), (16, 'CONFUSE RAY!')]],
                'and': [[(14, 'And...')]],
                'learned': [[(14, 'LAPRAS learned'), (16, 'THUNDERBOLT!')]],
            }.get(stage, [])
            party = stage not in ('boot', 'contained', 'teach')
            for variant in lines:
                if stage in ('teach', 'delete'):
                    add('prompt_wait', None, self._dialog(variant, party=party))
                    for y in (8, 10):
                        add(stage, y, self._dialog(variant, party=party, question=y))
                        add('inactive', None, self._dialog(variant, party=party, question=y, marker='▷'))
                else:
                    add('prompt_wait', None, self._dialog(variant, party=party))
                    if stage != 'poof' or variant == [(14, '1, 2 and... Poof!')]:
                        for arrow in (16, 17):
                            add(stage, None, self._dialog(variant, party=party, arrow=arrow))
        return out

    def _complete(self):
        return dict(self._hint('wait', 'complete_transaction_observed'), phase='tm24_complete',
                    tm24_complete=True, machine_kind='TM', item=224, quantity_used=1,
                    moves_verified=AFTER[:], new_move_pp=15,
                    other_party_and_resources_unchanged=True,
                    learned_actual_a_acked=self.learned_acked,
                    first_closed_observation_frame=self.closed_frame,
                    closed_observation_frame=self.last_frame)
