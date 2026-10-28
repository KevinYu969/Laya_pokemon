"""Five fixed Route23 land badge dialogues; pure hints, never game inputs.

Uses the installed readonly Route23 source getter and exact four-page parser.
The native coordinate script starts the dialogue; this controller never opens it.
Source candidate only; not live calibrated. Preserve this instance across reload.
"""
from copy import deepcopy
import math

from .mart_purchase import _party, _inventory
from . import route23_surf as surf, route23_water as water

SOURCE_COMMIT = surf.SOURCE_COMMIT
MAX_SECONDS, MAX_CALLS, MAX_WAITS = 60, 240, 30
CASES = {
    'cascade': dict(x=7, y=136, bit=0, badge='CASCADEBADGE', tile=0x23),
    'thunder': dict(x=9, y=119, bit=1, badge='THUNDERBADGE', tile=0x23),
    'rainbow': dict(x=10, y=105, bit=2, badge='RAINBOWBADGE', tile=0x2c),
    'volcano': dict(x=11, y=56, bit=5, badge='VOLCANOBADGE', tile=0x2c),
    'earth': dict(x=7, y=35, bit=6, badge='EARTHBADGE', tile=0x2c),
}
INTENTS = {name: dict(kind='route23_land_guard', map_id=34, player_x=c['x'], player_y=c['y'],
                      case=name, badge=c['badge'], bit=c['bit']) for name, c in CASES.items()}
_ACTIONS = frozenset(('a', 'b', 'up', 'down', 'left', 'right', 'start', 'wait'))


def _int(v, lo=0, hi=2**63-1):
    return type(v) is int and lo <= v <= hi


def _intent(value):
    if type(value) is not dict or type(value.get('case')) is not str or value['case'] not in INTENTS:
        return False
    expected = INTENTS[value['case']]
    return (set(value) == set(expected) and value == expected
            and all(type(value[k]) is type(v) for k, v in expected.items()))


def _position(value):
    if not isinstance(value, dict) or not all(_int(value.get(k), 0, 255) for k in ('map_id', 'x', 'y')):
        return None
    return tuple(value[k] for k in ('map_id', 'x', 'y'))


def _source_signal(signal, position, frame):
    """Typed land contract; intentionally does not require surf's flags & 7 == 7."""
    return (isinstance(signal, dict) and signal.get('profile') == surf.PROFILE
            and signal.get('source_commit') == SOURCE_COMMIT and signal.get('read_valid') is True
            and signal.get('read_error') is None and _int(signal.get('observation_frame'))
            and signal['observation_frame'] == frame and _position(signal.get('location')) == position
            and type(signal.get('mode')) is int and signal['mode'] == 0
            and type(signal.get('battle_raw')) is int and signal['battle_raw'] == 0
            and type(signal.get('badges_raw')) is int and signal['badges_raw'] == 255
            and type(signal.get('route23_script')) is int and signal['route23_script'] in (0, 2)
            and type(signal.get('guard_flags')) is int and 0 <= signal['guard_flags'] < 128
            and type(signal.get('facing_raw')) is int and signal['facing_raw'] in (0, 4, 8, 12)
            and signal.get('facing') == {0:'down', 4:'up', 8:'left', 12:'right'}[signal['facing_raw']]
            and surf._npc_source(signal.get('npc_positions')))


def _fingerprint(progress):
    party = _party(progress)
    bag = _inventory(progress.get('inventory')) if isinstance(progress, dict) else None
    if (party is None or len(party) != 6 or len({m['species'] for m in party}) != 6
            or any(m['hp'] <= 0 or m['status'] != 0 for m in party) or bag is None
            or not _int(progress.get('money'), 0, 999999)
            or type(progress.get('badges_raw')) is not int or progress['badges_raw'] != 255
            or progress.get('player_name_raw') != 'KEVIN'):
        return None
    return deepcopy(dict(party=party, inventory=bag, money=progress['money'],
                         badges_raw=255, player_name_raw='KEVIN'))


def _world(grid, case, frame):
    c = CASES[case]
    return water._grid(grid, (34, c['x'], c['y'], 0, c['tile']), frame)


class Route23LandGuardController:
    def __init__(self, intent=INTENTS['cascade']):
        if not _intent(intent):
            raise ValueError('Only five explicit fixed Route23 land guard intents are supported')
        self.intent, self.contract = deepcopy(intent), deepcopy(intent)
        self.page = 0
        self.stage = 'initial'
        self.pending = None
        self.error = None
        self.fingerprint = None
        self.flags = self.expected_flags = None
        self.started = self.last_now = None
        self.last_frame = -1
        self.last_packet = None
        self.calls = self.waits = 0
        self.done_frame = None
        self.final_offer_frame = self.final_ack_frame = None
        self.final_ack = False
        self.event_seen = False
        self.script2_seen = False
        self.closed_frames = []

    def _hint(self, action, tactic, complete=False):
        return dict(phase='route23_land_guard',
            objective='Wait.' if action == 'wait' else 'Confirm the current selection.',
            available_actions=['wait'] if action == 'wait' else [action, 'wait'],
            controller_menu_verified=action != 'wait', route23_land_guard_complete=complete,
            route23_land_guard_case=self.contract['case'], route23_land_guard_page=self.page,
            route23_land_guard_stage=self.stage, route23_land_guard_tactic=tactic,
            route23_land_guard_script2_seen=self.script2_seen, source_commit=SOURCE_COMMIT)

    def _fail(self, reason):
        self.error = self.error or 'route23_land_guard_' + reason
        return {**self._hint('wait', 'review'), 'phase':'campaign_review', 'review_reason':self.error}

    def _wait(self, reason):
        self.waits += 1
        return self._fail('wait_budget_exhausted') if self.waits > MAX_WAITS else self._hint('wait', reason)

    def _offer(self, rows, frame):
        self.pending = dict(frame=frame, rows=rows, executed=False, page=self.page)
        if self.page == 3:
            self.final_offer_frame = frame
        self.stage = 'dialogue'
        return self._hint('a', 'verified_native_badge_page')

    def context(self, state, *, grid, signal, movement, previous, now):
        if self.error:
            return self._fail('sticky')
        frame = state.get('frame') if isinstance(state, dict) else None
        if (not _intent(self.intent) or self.intent != self.contract or not _int(frame)
                or frame < self.last_frame or type(now) not in (int, float)
                or not math.isfinite(now) or now < 0 or self.last_now is not None and now < self.last_now):
            return self._fail('intent_clock_or_frame_unverified')
        self.calls += 1
        if self.started is None:
            self.started = now
        if self.calls > MAX_CALLS or now - self.started > MAX_SECONDS:
            return self._fail('budget_exhausted')
        self.last_now = now
        if type(previous) not in (list, tuple) or any(type(a) is not str or a not in _ACTIONS for a in previous):
            return self._fail('actual_previous_unverified')
        case = CASES[self.contract['case']]
        position = _position(state.get('location'))
        if position != (34, case['x'], case['y']):
            return self._fail('fixed_location_changed')
        battle = state.get('battle_state')
        if (not isinstance(battle, dict) or type(battle.get('raw')) is not int or battle['raw'] != 0
                or battle.get('active') is not False or battle.get('kind') != 'none'
                or type(battle.get('observation_frame')) is not int or battle['observation_frame'] != frame):
            return self._fail('battle_not_verified_none')
        if not _source_signal(signal, position, frame):
            return self._fail('land_source_signal_unverified')
        idle = surf._idle(movement, frame)
        if idle is None:
            return self._fail('movement_packet_unverified')
        text = state.get('text')
        rows = surf._rows(text)
        if rows is None:
            return self._fail('text_decoder_unverified')
        for packet in (state.get('location'), state.get('progress'), text, grid, movement):
            if isinstance(packet, dict) and 'observation_frame' in packet and (
                    type(packet['observation_frame']) is not int or packet['observation_frame'] != frame):
                return self._fail('packet_frame_conflict')
        fingerprint = _fingerprint(state.get('progress'))
        if fingerprint is None:
            return self._fail('six_party_inventory_or_money_invalid')
        if self.fingerprint is not None and fingerprint != self.fingerprint:
            return self._fail('party_inventory_money_or_pp_changed')
        packet = deepcopy((state, grid, signal, movement, previous))
        if frame == self.last_frame:
            return self._fail('same_frame_conflict') if packet != self.last_packet else self._hint('wait', 'same_frame_no_action')
        self.last_frame, self.last_packet = frame, packet
        if self.fingerprint is None:
            if signal['guard_flags'] & (1 << case['bit']) or signal['route23_script'] != 0:
                return self._fail('initial_guard_already_passed_or_script_invalid')
            self.fingerprint = fingerprint
            self.flags = signal['guard_flags']
            self.expected_flags = self.flags | (1 << case['bit'])
            self.stage = 'await_native_intro'

        # A candidate is an offer. Only the next real previous-action packet can ACK it.
        if self.pending is not None and not self.pending['executed']:
            if frame > self.pending['frame'] and previous and previous[-1] == 'a':
                self.pending['executed'] = True
                if self.page == 3:
                    self.final_ack = True
                    self.final_ack_frame = frame
                    self.pending = None
                    self.stage = 'await_native_reset'
            else:
                same_page = water._guard_page(rows, case['badge'], self.page) if text['window_visible'] else None
                if same_page is None or self.page == 3 and same_page['arrow']:
                    return self._fail('page_changed_without_actual_a')
                if signal['guard_flags'] != self.flags or signal['route23_script'] != 0:
                    return self._fail('event_before_final_actual_a')
                return self._hint('a', 'retry_unexecuted_native_candidate') if same_page['full'] and (
                    self.page == 3 or same_page['arrow']) else self._wait('await_unexecuted_page_prompt')

        if self.final_ack:
            done_page = water._guard_page(rows, case['badge'], 3) if rows != surf._blank() else None
            if rows != surf._blank() and (done_page is None or done_page['arrow']):
                return self._fail('unknown_page_after_done_actual_a')
            if signal['guard_flags'] not in (self.flags, self.expected_flags):
                return self._fail('foreign_guard_event_changed')
            if signal['guard_flags'] == self.flags:
                if self.event_seen:
                    return self._fail('own_guard_event_regressed')
                if signal['route23_script'] != 0:
                    return self._fail('native_script_before_own_event')
                self.closed_frames = []
                if rows != surf._blank() and water._guard_page(rows, case['badge'], 3) is None:
                    return self._fail('unknown_page_after_done_actual_a')
                return self._wait('await_native_own_event_after_done_actual_a')
            self.event_seen = True
            if signal['route23_script'] == 2:
                self.script2_seen = True
                self.closed_frames = []
                return self._wait('native_guard_reset_script')
            if rows != surf._blank() or text['window_visible'] is not False or not idle:
                self.closed_frames = []
                if rows != surf._blank() and water._guard_page(rows, case['badge'], 3) is None:
                    return self._fail('unknown_native_completion_page')
                return self._wait('await_native_closed_world')
            if not _world(grid, self.contract['case'], frame):
                self.closed_frames = []
                return self._wait('await_true_closed_world_grid')
            self.closed_frames.append(frame)
            if len(self.closed_frames) < 2:
                return self._wait('first_fresh_closed_guard_frame')
            self.stage = 'complete'
            return self._hint('wait', 'verified_land_guard_native_closure', True)

        if signal['guard_flags'] != self.flags or signal['route23_script'] != 0:
            return self._fail('event_before_final_actual_a')
        if self.pending is not None:
            old_page = water._guard_page(rows, case['badge'], self.page) if text['window_visible'] else None
            if old_page is not None:
                return self._wait('await_native_page_after_actual_a')
            if rows == surf._blank():
                return self._wait('native_page_transition')
            if self.page >= 3 or water._guard_page(rows, case['badge'], self.page + 1) is None:
                return self._fail('unknown_page_or_page_jump')
            self.page += 1
            self.pending = None
            self.done_frame = None
        if rows == surf._blank():
            return self._wait('await_native_intro_or_prefix')
        if text['window_visible'] is not True:
            return self._fail('native_page_window_missing')
        page = water._guard_page(rows, case['badge'], self.page)
        if page is None:
            return self._fail('unknown_or_polluted_native_page')
        if not page['full']:
            self.done_frame = None
            return self._wait('known_native_page_printing')
        if self.page < 3:
            if not page['arrow']:
                return self._wait('native_prompt_arrow_blink')
        else:
            if page['arrow']:
                return self._fail('done_page_has_prompt_arrow')
            if self.done_frame is None:
                self.done_frame = frame
                return self._wait('first_full_native_done_frame')
        return self._offer(rows, frame)
