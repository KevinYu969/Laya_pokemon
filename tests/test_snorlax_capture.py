"""超級球捕捉純候選；fake觀測與公開來源，不讀ROM/state或操作遊戲。"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from laya_pokemon.observation import PROFILE
from laya_pokemon.snorlax_capture import SnorlaxCaptureController, INTENT, ENEMY_PROFILE


F = json.loads((Path(__file__).parent / 'data/snorlax-capture-source-fixture.json').read_text(encoding='utf-8'))
LOCATION = {'map_id': 23, 'x': 10, 'y': 61}
WILD = {'raw': 1, 'active': True, 'kind': 'wild', 'opponent_species': 'SNORLAX', 'wild_opponent_species': 'SNORLAX'}


def text_at(*entries):
    cells = [[' '] * 20 for _ in range(18)]
    for x, y, text in entries:
        assert x + len(text) <= 20
        cells[y][x:x + len(text)] = list(text)
    return {'cells': cells, 'profile': PROFILE, 'read_valid': True, 'alignment_verified': True,
            'window_visible': True, 'read_error': None, 'warnings': ['decoder尚未完全校準']}


def progress(starter=154, ids=None):
    def mon(species, name, level, hp, maximum):
        return {'species': species, 'species_name': name, 'level': level, 'hp': hp, 'max_hp': maximum,
                'status': 0, 'exp': 20000, 'moves': [33, 0, 0, 0], 'pp': [35, 0, 0, 0]}
    names = {9: 'IVYSAUR', 154: 'VENUSAUR'}
    items = [4, 3, 73, 42] if ids is None else ids
    return {'profile': 'gen1-wrapper-ram-progress-v1-unvalidated', 'party_read_valid': True,
        'initialization_candidate': True, 'party_count': 4, 'player_name_raw': 'KEVIN', 'money': 12000,
        'party': [mon(starter, names[starter], 33, 100, 105), mon(102, 'EEVEE', 30, 70, 75),
                  mon(35, 'FEAROW', 32, 80, 85), mon(7, 'NIDOKING', 31, 90, 95)],
        'inventory': [{'item': i, 'quantity': 20 if i == 3 else 6 if i == 4 else 1} for i in items]}


def fingerprint(hp=40, status=0):
    return {'species': 132, 'level': 30, 'hp': hp, 'max_hp': 140, 'status': status}


def snapshot(frame, enemy=None):
    enemy = fingerprint() if enemy is None else enemy
    return {'profile': ENEMY_PROFILE, 'source_commit': F['source_commit'], 'read_valid': True,
            'live_calibrated': False, 'unknown_reason': None, 'observation_frame': frame,
            'location': deepcopy(LOCATION), 'battle_kind': 'wild',
            'enemy': {**enemy, 'internal_id': 132, 'species_name': 'SNORLAX',
                      'moves': [29, 133, 156, 0], 'pp': [8, 18, 9, 0]}}


def hud(p, enemy=None):
    enemy = fingerprint() if enemy is None else enemy
    active = p['party'][0]
    def status(s, level):
        return 'SLP' if s & 7 else {8: 'PSN', 16: 'BRN', 32: 'FRZ', 64: 'PAR'}.get(s, str(level))
    return text_at((1, 0, 'SNORLAX'), (5, 1, status(enemy['status'], 30)),
        (10, 7, active['species_name']), (15, 8, status(active['status'], active['level'])),
        (11, 10, f'{active["hp"]:3}/{active["max_hp"]:3}'))


def command(p, cursor=(9, 16), enemy=None):
    t = hud(p, enemy)
    for x, y, value in [(10, 14, 'FIGHT'), (10, 16, 'ITEM'), (16, 16, 'RUN'), (*cursor, '▶')]:
        t['cells'][y][x:x + len(value)] = list(value)
    return t


def bag(p, *, offset=0, cursor=0, enemy=None, inactive=False):
    t = hud(p, enemy)
    for y in range(2, 13): t['cells'][y][4:20] = [' '] * 16
    t['cells'][4 + cursor * 2][5] = '▷' if inactive else '▶'
    canceled = False
    keys = set(F['key_items']) | set(range(196, 201))
    for i in range(4):
        y, index = 4 + i * 2, offset + i
        if index >= len(p['inventory']):
            t['cells'][y][6:12] = list('CANCEL'); canceled = True; break
        item = p['inventory'][index]; code = item['item']
        label = f'HM{code - 195:02d}' if 196 <= code <= 200 else f'TM{code - 200:02d}' if code >= 201 else F['item_labels'][str(code)]
        t['cells'][y][6:6 + len(label)] = list(label)
        if code not in keys: t['cells'][y + 1][14:17] = list(f'×{item["quantity"]:2d}')
    if not canceled: t['cells'][11][18] = '▼'
    return t


def dialogue(p, slots, enemy=None, *, prompt=True):
    t = hud(p, enemy)
    for x, y, value in slots: t['cells'][y][x:x + len(value)] = list(value)
    if prompt: t['cells'][16][18] = '▼'
    return t


class Session:
    def __init__(self, p=None, **limits):
        self.p = progress() if p is None else p
        self.c = SnorlaxCaptureController(deepcopy(INTENT), **limits)
        self.frame, self.now = 0, 0.
        self.enemy = fingerprint()

    def call(self, t=None, **kwargs):
        self.frame += 40; self.now += .05
        frame = kwargs.pop('frame', self.frame)
        return self.c.context(text_at() if t is None else t, self.p,
            location=kwargs.pop('location', deepcopy(LOCATION)), battle_state=kwargs.pop('battle_state', deepcopy(WILD)),
            enemy_snapshot=kwargs.pop('enemy_snapshot', snapshot(frame, self.enemy)),
            frame=frame, now=kwargs.pop('now', self.now), **kwargs)

    def open_bag(self):
        assert self.call(command(self.p, enemy=self.enemy))['available_actions'] == ['a', 'wait']

    def throw(self):
        self.open_bag()
        target = next(i for i, x in enumerate(self.p['inventory']) if x['item'] == 3)
        for index in range(target + 1):
            offset, cursor = max(0, index - 2), min(index, 2)
            result = self.call(bag(self.p, offset=offset, cursor=cursor, enemy=self.enemy))
            assert result['available_actions'] == (['a', 'wait'] if index == target else ['down', 'wait']), result
        return result

    def fail(self, name='broke_free'):
        result = self.call(dialogue(self.p, F['failure_pages'][name], self.enemy))
        assert result['available_actions'] == ['a', 'wait'], result
        for item in self.p['inventory']:
            if item['item'] == 3: item['quantity'] -= 1
        self.p['inventory'] = [x for x in self.p['inventory'] if x['quantity']]


def test_fixture_records_fixed_source_and_direct_battle_bag_not_use_toss():
    assert F['source_commit'] == 'a53671100ec22e5394ff26ec028d0812a238dae2' and F['intent'] == INTENT
    assert not F['live_ui_calibrated'] and F['ball'] == 3
    core = next(s for s in F['sources'] if s['path'] == 'engine/battle/core.asm')
    assert 'call UseItem' in ''.join(e['text'] for e in core['excerpts'])
    assert F['party']['exactly_one_starter'] == [9, 154]


@pytest.mark.parametrize('starter', [9, 154])
@pytest.mark.parametrize('ids', [[3, 73], [4, 3, 73, 42], [4, 234, 42, 49, 63, 228, 196, 73, 221, 72, 3]])
def test_full_normal_throw_then_caught_handoff_keeps_unmodified_last_throw(starter, ids):
    s = Session(progress(starter, ids)); original = deepcopy(s.p)
    s.throw()
    result = s.call(dialogue(s.p, F['caught_first_page']))
    assert result['available_actions'] == ['wait'] and result['capture_completion_handoff']
    assert not result['capture_complete'] and result['last_throw']['ball_item'] == 3
    assert result['last_throw']['progress'] == original == s.p
    assert result['last_throw']['enemy'] == fingerprint()
    assert len(result['last_throw']['enemy']) == 5 and 'pp' not in result['last_throw']['enemy']
    assert result['last_throw']['progress']['party'][0]['species'] == starter
    assert s.c.context(None, None, location=None, battle_state=None, enemy_snapshot=None, frame=-1, now=float('nan')) == result


def test_ivy_last_throw_snapshot_is_accepted_by_frozen_completion_baseline_contract():
    from laya_pokemon.capture_completion import CaptureCompletionController, INTENT as END_INTENT
    s = Session(progress(9)); s.throw(); result = s.call(dialogue(s.p, F['caught_first_page']))
    end = CaptureCompletionController(END_INTENT, last_throw=result['last_throw'])
    assert end.stage == 'caught_start'
    # Venusaur保持154；本測試不偽造9來蒙混尚未擴充的舊finalizer。


@pytest.mark.parametrize('cursor,action,expected', [((9, 14), 'down', (9, 16)),
    ((15, 14), 'left', (9, 14)), ((15, 16), 'left', (9, 16))])
def test_command_moves_only_toward_item_and_semantic_pending_survives_blank(cursor, action, expected):
    s = Session(); t = command(s.p, cursor)
    assert s.call(t)['available_actions'] == [action, 'wait']
    assert s.call()['available_actions'] == ['wait']
    assert s.call(t)['available_actions'] == ['wait']
    assert s.call(command(s.p, expected))['available_actions'] == (['a', 'wait'] if expected == (9, 16) else ['down', 'wait'])


def test_item_confirm_static_or_blank_then_old_command_does_not_repeat_a():
    s = Session(); s.open_bag(); s.call()
    assert s.call(command(s.p))['available_actions'] == ['wait']


def test_bag_scroll_and_throw_a_cannot_repeat_after_blank_or_old_page():
    s = Session(); s.open_bag(); t = bag(s.p)
    assert s.call(t)['available_actions'] == ['down', 'wait']
    s.call(); assert s.call(t)['available_actions'] == ['wait']
    selected = bag(s.p, cursor=1)
    assert s.call(selected)['available_actions'] == ['a', 'wait']
    s.call(); assert s.call(selected)['available_actions'] == ['wait']
    assert s.call(bag(s.p, cursor=1, inactive=True))['available_actions'] == ['wait']
    assert s.c.throws == 1


@pytest.mark.parametrize('failure', list(F['failure_pages']))
def test_only_complete_source_failure_prompt_is_confirmed_once(failure):
    s = Session(); s.throw(); t = dialogue(s.p, F['failure_pages'][failure])
    t['cells'][16][18] = ' '
    assert s.call(t)['available_actions'] == ['wait']
    t['cells'][16][18] = '▼'
    assert s.call(t)['available_actions'] == ['a', 'wait']
    s.call(); assert s.call(t)['available_actions'] == ['wait']


@pytest.mark.parametrize('prompt', list(F['enemy_prompts']))
def test_known_enemy_prompt_once_allows_rest_sleep_effect_without_flute(prompt):
    s = Session(); s.throw(); s.fail()
    if prompt in ('asleep', 'health', 'rest_cont'): s.enemy.update(hp=140, status=2)
    t = dialogue(s.p, F['enemy_prompts'][prompt], s.enemy)
    result = s.call(t)
    assert result['available_actions'] == ['a', 'wait'], result
    s.call(); assert s.call(t)['available_actions'] == ['wait']
    assert 'flute' not in result.get('menu_label', '').lower()


@pytest.mark.parametrize('page', list(F['passive_enemy_pages']))
def test_passive_used_move_or_rest_page_waits_without_a(page):
    s = Session(); s.throw(); s.fail()
    if page in ('rest_sleep', 'rest_healthy'): s.enemy.update(hp=140, status=2)
    t = dialogue(s.p, F['passive_enemy_pages'][page], s.enemy, prompt=False)
    assert s.call(t)['available_actions'] == ['wait']


def test_retry_uses_new_last_throw_baseline_and_current_real_rest_hp_status():
    s = Session(); s.throw(); first = deepcopy(s.c.last_throw); s.fail()
    s.enemy.update(hp=140, status=2)
    s.call(dialogue(s.p, F['enemy_prompts']['health'], s.enemy))
    s.throw()
    result = s.call(dialogue(s.p, F['caught_first_page'], s.enemy))
    last = result['last_throw']
    assert dict((x['item'], x['quantity']) for x in first['progress']['inventory'])[3] == 20
    assert dict((x['item'], x['quantity']) for x in last['progress']['inventory'])[3] == 19
    assert last['enemy']['hp'] == 140 and last['enemy']['status'] == 2


@pytest.mark.parametrize('hp,maximum,safe', [(60, 90, False), (61, 90, True), (59, 60, False), (60, 89, True)])
def test_exact_safety_threshold_is_at_least_sixty_and_strictly_over_two_thirds(hp, maximum, safe):
    p = progress(); p['party'][0].update(hp=hp, max_hp=maximum); s = Session(p)
    result = s.call(command(s.p))
    assert result['available_actions'] == (['a', 'wait'] if safe else ['wait'])
    if not safe:
        assert result['review_reason'] == 'snorlax_capture_safe_switch_requires_review'
        assert result['healthy_switch_candidates'] and not result['switch_implemented']


def test_damage_drops_safety_stops_before_further_enemy_prompt_or_throw():
    s = Session(); s.throw(); s.fail(); s.p['party'][0]['hp'] = 60
    result = s.call(dialogue(s.p, F['enemy_prompts']['critical']))
    assert result['review_reason'] == 'snorlax_capture_safe_switch_requires_review'
    assert s.c.throws == 1 and result['available_actions'] == ['wait']


@pytest.mark.parametrize('index', [0, 1, 2, 3])
def test_any_fainted_member_immediately_reviews(index):
    s = Session(); s.p['party'][index]['hp'] = 0
    assert s.call(command(s.p))['review_reason'] == 'snorlax_capture_any_party_fainted'


@pytest.mark.parametrize('change', ['no_starter', 'two_starters', 'repeat_other', 'wrong_name', 'bad_pp', 'count_bool'])
def test_four_party_is_specific_and_never_masquerades_venusaur_as_ivy(change):
    p = progress()
    if change == 'no_starter': p['party'][0].update(species=148, species_name='ABRA')
    elif change == 'two_starters': p['party'][1].update(species=9, species_name='IVYSAUR')
    elif change == 'repeat_other': p['party'][1] = deepcopy(p['party'][2])
    elif change == 'wrong_name': p['party'][0]['species_name'] = 'IVYSAUR'
    elif change == 'bad_pp': p['party'][0]['pp'] = [True, 0, 0, 0]
    else: p['party_count'] = True
    assert Session(p).call(command(p))['phase'] == 'campaign_review'


@pytest.mark.parametrize('change', ['upper_yes', 'left_delete', 'wrong_quantity', 'wrong_order', 'preview_cursor',
    'toss', 'exit', 'extra_cursor', 'inactive_swap', 'wrong_arrow', 'bag_partial_unknown'])
def test_bag_all_labels_quantities_order_and_entire_battle_background_are_verified(change):
    s = Session(); s.open_bag(); t = bag(s.p)
    if change == 'upper_yes': t['cells'][0][0:3] = list('YES')
    elif change == 'left_delete': t['cells'][5][0:4] = list('NOPE')
    elif change == 'wrong_quantity': t['cells'][7][15:17] = list('19')
    elif change == 'wrong_order': t['cells'][6][6:19] = list('POKé FLUTE'.upper().ljust(13))
    elif change == 'preview_cursor': t['cells'][4][5] = ' '; t['cells'][10][5] = '▶'
    elif change == 'toss': t['cells'][13][15:19] = list('TOSS')
    elif change == 'exit': t['cells'][14][12:16] = list('EXIT')
    elif change == 'extra_cursor': t['cells'][0][0] = '▶'
    elif change == 'inactive_swap': t['cells'][6][5] = '▷'
    elif change == 'wrong_arrow': t['cells'][11][18] = ' '; t['cells'][16][18] = '▼'
    else: t['cells'][0][0] = 'X'
    result = s.call(t)
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait'] and s.c.throws == 0


@pytest.mark.parametrize('change', ['wrong_move', 'jump'])
def test_bag_cursor_semantic_pending_rejects_wrong_movement(change):
    s = Session(progress(ids=[4, 234, 42, 3, 73])); s.open_bag()
    s.call(bag(s.p, cursor=1)); s.call()
    t = bag(s.p, cursor=0) if change == 'wrong_move' else bag(s.p, offset=2, cursor=2)
    assert s.call(t)['review_reason'] == 'snorlax_capture_bag_cursor_wrong_move'


@pytest.mark.parametrize('field,value', [('read_valid', False), ('profile', 'other'), ('source_commit', 'main'),
    ('observation_frame', 39), ('live_calibrated', True), ('unknown_reason', 'unknown'), ('battle_kind', 'trainer')])
def test_enemy_reader_contract_never_guesses_missing_or_other_frame_data(field, value):
    s = Session(); e = snapshot(40); e[field] = value
    assert s.call(command(s.p), enemy_snapshot=e)['review_reason'] == 'snorlax_capture_real_same_frame_enemy_snapshot_required'


@pytest.mark.parametrize('field,value', [('species', 143), ('level', 29), ('hp', 0), ('max_hp', 999), ('status', True)])
def test_wrong_real_enemy_fingerprint_reviews(field, value):
    s = Session(); e = snapshot(40); e['enemy'][field] = value
    assert s.call(command(s.p), enemy_snapshot=e)['phase'] == 'campaign_review'


def test_complete_caught_first_page_can_handoff_preserved_snapshot_during_known_zero_hp_getter_transition():
    s = Session(); s.throw(); frame = s.frame + 40
    e = {'profile': ENEMY_PROFILE, 'source_commit': F['source_commit'], 'live_calibrated': False,
         'observation_frame': frame, 'read_valid': False, 'enemy': None, 'unknown_reason': 'enemy_zero_hp_transition'}
    result = s.call(dialogue(s.p, F['caught_first_page']), enemy_snapshot=e)
    assert result['capture_completion_handoff'] and result['last_throw']['enemy']['hp'] == 40


@pytest.mark.parametrize('kind', ['unknown', 'wild_frame_changed_during_read', 'enemy_zero_hp_transition'])
def test_reader_unknown_before_full_caught_is_not_masked_by_partial(kind):
    s = Session(); s.throw(); e = snapshot(s.frame + 40)
    e.update(read_valid=False, enemy=None, unknown_reason=kind)
    assert s.call(enemy_snapshot=e)['phase'] == 'campaign_review'


@pytest.mark.parametrize('stage', ['command', 'result', 'enemy'])
@pytest.mark.parametrize('word', ['YES', 'Delete', 'UNKNOWN'])
def test_unknown_prompt_or_upper_text_cannot_be_hidden_by_known_body(stage, word):
    s = Session()
    if stage == 'command': t = command(s.p)
    else:
        s.throw()
        if stage == 'enemy': s.fail(); t = dialogue(s.p, F['enemy_prompts']['asleep'])
        else: t = dialogue(s.p, F['caught_first_page'])
    t['cells'][5][0:len(word)] = list(word)
    assert s.call(t)['phase'] == 'campaign_review'


@pytest.mark.parametrize('field,value', [('read_valid', False), ('alignment_verified', False),
    ('window_visible', None), ('profile', 'other'), ('read_error', 'unaligned')])
def test_decoder_proof_required_for_every_stage(field, value):
    s = Session(); s.throw(); t = dialogue(s.p, F['caught_first_page']); t[field] = value
    assert s.call(t)['review_reason'] == 'snorlax_capture_decoder_proof_required'


def test_enemy_pp_is_not_compared_to_fresh_capture_party_pp():
    s = Session(); s.open_bag(); e = snapshot(s.frame + 40); e['enemy']['pp'] = [0, 2, 1, 0]
    assert s.call(bag(s.p), enemy_snapshot=e)['available_actions'] == ['down', 'wait']
    e = snapshot(s.frame + 40); e['enemy']['pp'] = [0, 2, 1, 0]
    assert s.call(bag(s.p, cursor=1), enemy_snapshot=e)['available_actions'] == ['a', 'wait']
    assert set(s.c.last_throw['enemy']) == {'species', 'level', 'hp', 'max_hp', 'status'}


def test_twenty_failed_throws_stop_on_exhaustion_without_attack_or_run():
    s = Session()
    for _ in range(20): s.throw(); s.fail('close')
    result = s.call()
    assert result['review_reason'] == 'snorlax_capture_great_balls_exhausted'
    assert result['available_actions'] == ['wait'] and s.c.throws == 20


def test_smaller_throw_limit_stops_even_if_balls_remain():
    s = Session(max_throws=1); s.throw(); s.fail()
    assert s.call(command(s.p))['review_reason'] == 'snorlax_capture_twenty_throw_request_limit'


def test_clock_calls_wait_budget_and_error_latch():
    s = Session(max_calls=1); s.call(); failure = s.call()
    assert failure['review_reason'] == 'snorlax_capture_transaction_budget_exhausted'
    assert s.call(command(s.p)) == failure
    s = Session(); s.call(); assert s.call(now=61)['review_reason'] == 'snorlax_capture_transaction_budget_exhausted'
    s = Session(max_waits=1); s.call(); assert s.call()['review_reason'] == 'snorlax_capture_wait_budget_exhausted'


@pytest.mark.parametrize('value', [True, -1, float('nan'), float('inf'), '2'])
def test_bad_clock_never_requests_action(value):
    assert Session().call(now=value)['available_actions'] == ['wait']


def test_same_frame_same_packet_wait_and_conflicting_packet_review():
    s = Session(); t = command(s.p); s.call(t); frame = s.frame
    assert s.call(t, frame=frame)['available_actions'] == ['wait']
    t = deepcopy(t); t['cells'][5][0] = 'X'
    assert s.call(t, frame=frame)['review_reason'] == 'snorlax_capture_same_frame_changed_packet'


@pytest.mark.parametrize('quantity', [0, 1, 19, 21, True])
def test_initial_purchase_proof_requires_exact_twenty(quantity):
    p = progress(); p['inventory'][1]['quantity'] = quantity
    assert Session(p).call(command(p))['phase'] == 'campaign_review'


def test_party_change_or_healing_cannot_be_hidden_by_known_partial():
    s = Session(); s.open_bag(); s.p['party'][0]['hp'] += 1
    assert s.call()['review_reason'] == 'snorlax_capture_unexpected_party_healing'
    s = Session(); s.open_bag(); s.p['party'].reverse()
    assert s.call()['review_reason'] == 'snorlax_capture_party_identity_order_or_non_hp_data_changed'


def test_every_packet_left_unchanged_and_last_throw_is_a_deep_copy():
    s = Session(); t = command(s.p); loc = deepcopy(LOCATION); b = deepcopy(WILD); e = snapshot(40)
    before = deepcopy((t, s.p, loc, b, e))
    s.call(t, location=loc, battle_state=b, enemy_snapshot=e)
    assert (t, s.p, loc, b, e) == before
    s.call(bag(s.p)); s.call(bag(s.p, cursor=1))
    stored = deepcopy(s.c.last_throw); s.p['inventory'][1]['quantity'] = 19
    assert s.c.last_throw == stored


def test_enemy_prompt_cannot_be_resent_after_other_known_prompt_and_blank():
    s = Session(); s.throw(); s.fail()
    asleep = dialogue(s.p, F['enemy_prompts']['asleep'])
    assert s.call(asleep)['available_actions'] == ['a', 'wait']
    assert s.call(dialogue(s.p, F['enemy_prompts']['critical']))['available_actions'] == ['a', 'wait']
    s.call()
    assert s.call(asleep)['available_actions'] == ['wait']


def test_real_sdk_multichar_contraction_tile_is_conservative_review_not_claimed_live_support():
    s = Session(); s.throw(); s.fail()
    t = dialogue(s.p, F['enemy_prompts']['missed'])
    # SDK將0xBD解碼成"'s"一個tile；目前共用_rows保守拒多字元cell。
    t['cells'][14][14] = "'s"
    assert s.call(t)['review_reason'] == 'snorlax_capture_decoder_proof_required'


def test_five_field_handoff_matches_frozen_reader_pure_capture_fingerprint():
    from laya_pokemon.wild_opponent import capture_fingerprint
    s = Session(); s.throw()
    e = snapshot(s.frame + 40, s.enemy)
    assert s.c.last_throw['enemy'] == capture_fingerprint(e)


@pytest.mark.parametrize('field,value', [('max_calls', 241), ('max_waits', True), ('max_seconds', 61),
    ('max_throws', 21), ('max_throws', 0)])
def test_fixed_budget_constructor_cannot_be_expanded(field, value):
    with pytest.raises(ValueError): SnorlaxCaptureController(INTENT, **{field: value})


@pytest.mark.parametrize('mutation', [lambda x: x.update(ball_item=4), lambda x: x.update(species=143),
    lambda x: x.update(no_run=False), lambda x: x.update(map_id=True), lambda x: x.update(extra=True)])
def test_only_explicit_great_ball_route12_intent_is_accepted(mutation):
    intent = deepcopy(INTENT); mutation(intent)
    with pytest.raises(ValueError): SnorlaxCaptureController(intent)


@pytest.mark.parametrize('field', ['progress', 'location', 'battle'])
def test_individual_readonly_frame_tags_must_match(field):
    s = Session(); loc, b = deepcopy(LOCATION), deepcopy(WILD)
    {'progress': s.p, 'location': loc, 'battle': b}[field]['observation_frame'] = 39
    assert s.call(command(s.p), location=loc, battle_state=b)['review_reason'] == 'snorlax_capture_observation_frame_conflict'


def test_caught_incomplete_prompt_never_advances_or_handoffs():
    s = Session(); s.throw(); t = dialogue(s.p, F['caught_first_page'])
    t['cells'][16][11] = ' '
    assert s.call(t)['phase'] == 'campaign_review'


def test_initial_complete_single_row_go_with_real_matching_hud_only_waits_then_command_works():
    s = Session(); t = dialogue(s.p, [[1, 14, 'GO! VENUSAUR!']], prompt=False)
    assert s.call(t)['available_actions'] == ['wait']
    assert s.call(t)['available_actions'] == ['wait']
    assert s.c.hud_rows is None and s.c.throws == 0
    assert s.call(command(s.p))['available_actions'] == ['a', 'wait']


@pytest.mark.parametrize('change', ['wrong_species', 'partial', 'prompt', 'cursor'])
def test_initial_go_entry_does_not_mask_wrong_name_partial_or_menu_marker(change):
    s = Session(); t = dialogue(s.p, [[1, 14, 'GO! VENUSAUR!']], prompt=False)
    if change == 'wrong_species': t['cells'][14][1:14] = list('GO! IVYSAUR!  ')
    elif change == 'partial': t['cells'][14][12] = ' '
    elif change == 'prompt': t['cells'][16][18] = '▼'
    else: t['cells'][16][0] = '▶'
    assert s.call(t)['phase'] == 'campaign_review' and s.c.throws == 0


def test_complete_native_bag_without_optional_scroll_decoration_preserves_transaction():
    s = Session(progress(ids=[4, 234, 42, 49, 73, 3])); s.call(command(s.p))
    before = deepcopy(s.p)
    t = bag(s.p); t['cells'][11][18] = ' '
    assert s.call(t)['available_actions'] == ['down', 'wait']
    assert s.p == before and s.c.throws == 0


@pytest.mark.parametrize('position', [(17, 11), (18, 10), (19, 11)])
def test_bag_scroll_decoration_at_unknown_position_still_stops(position):
    s = Session(progress(ids=[4, 234, 42, 49, 73, 3])); s.call(command(s.p))
    t = bag(s.p); t['cells'][11][18] = ' '
    x, y = position; t['cells'][y][x] = '▼'
    assert s.call(t)['phase'] == 'campaign_review' and s.c.throws == 0


@pytest.mark.parametrize('word', ['GREAT', 'GREAT BALL!'])
def test_known_great_ball_use_text_is_passive_without_rethrow(word):
    s = Session(); s.throw(); before = deepcopy(s.c.last_throw)
    t = dialogue(s.p, [(1, 14, 'KEVIN USED'), (1, 16, word)], prompt=False)
    assert s.call(t)['available_actions'] == ['wait']
    assert s.call(t)['available_actions'] == ['wait']
    assert s.c.throws == 1 and s.c.last_throw == before


@pytest.mark.parametrize('name,item,prompt', [('ASH USED', 'GREAT BALL!', False),
    ('KEVIN USED', 'POKÉ BALL!', False), ('KEVIN USED', 'GREAT BALL!', True)])
def test_wrong_player_item_or_prompt_is_not_ball_use_wait(name,item,prompt):
    s = Session(); s.throw()
    t = dialogue(s.p, [(1, 14, name), (1, 16, item)], prompt=prompt)
    assert s.call(t)['phase'] == 'campaign_review' and s.c.throws == 1


def possessive_text(p, suffix='SPECI'):
    t = dialogue(p, [(1, 14, 'ENEMY SNORLAX'), (1, 16, suffix)], prompt=False)
    t['cells'][14][14] = "'s"
    return t


def test_native_single_tile_possessive_keeps_coordinates_and_only_waits_on_amnesia_text():
    s = Session(); s.throw(); s.fail(); t = possessive_text(s.p); before = deepcopy(t)
    assert s.call(t)['available_actions'] == ['wait']
    assert t == before and s.c.throws == 1


@pytest.mark.parametrize('change', ['wrong_position','wrong_name','other_token','literal_sentinel',
                                  'sentinel_alongside_valid_token','lines_conflict'])
def test_possessive_tile_reader_rejects_unverified_token_or_packet(change):
    s = Session(); s.throw(); s.fail(); t = possessive_text(s.p)
    if change == 'wrong_position': t['cells'][14][14], t['cells'][14][15] = ' ', "'s"
    elif change == 'wrong_name': t['cells'][14][7] = 'A'
    elif change == 'other_token': t['cells'][14][14] = "'d"
    elif change == 'literal_sentinel': t['cells'][14][14] = '\ue000'
    elif change == 'sentinel_alongside_valid_token': t['cells'][16][1] = '\ue000'
    else: t.update(lines=['not actual text'], line_rows=[14])
    assert s.call(t)['review_reason'] == 'snorlax_capture_decoder_proof_required'


def test_native_amnesia_one_tile_scroll_retains_original_rows_and_only_waits():
    s = Session(); s.throw(); s.fail()
    t = dialogue(s.p, [(1, 13, 'ENEMY SNORLAX'), (1, 15, 'SPECIAL')], prompt=False)
    t['cells'][13][14] = "'s"; before = deepcopy(t)
    assert s.call(t)['available_actions'] == ['wait']
    assert t == before and s.c.throws == 1


def headbutt_animation(s):
    t = dialogue(s.p, [(1,14,'ENEMY SNORLAX'),(1,16,'USED HEADBUTT!')], prompt=False)
    t.update(read_valid=False,alignment_verified=False,read_error='visible_tile_alignment_incomplete')
    return t


def test_only_exact_native_headbutt_decoder_transition_is_bounded_passive_wait():
    s = Session(); s.throw(); s.fail(); t = headbutt_animation(s); before = deepcopy(t)
    for _ in range(25):
        r = s.call(t); assert r['available_actions'] == ['wait'] and not r['controller_menu_verified']
    assert s.call(t)['review_reason'] == 'snorlax_capture_decoder_proof_required'
    assert t == before and s.c.throws == 1


@pytest.mark.parametrize('change',['wrong_move','prompt','wrong_error','wrong_ball_count','wrong_enemy'])
def test_native_animation_does_not_expand_unknown_decoder_to_actions(change):
    s = Session(); s.throw(); s.fail(); t = headbutt_animation(s)
    if change == 'wrong_move': t['cells'][16][6] = 'X'
    elif change == 'prompt': t['cells'][16][18] = '▼'
    elif change == 'wrong_error': t['read_error'] = 'unknown'
    elif change == 'wrong_ball_count': s.p['inventory'][1]['quantity'] -= 1
    else: s.enemy['hp'] -= 1
    assert s.call(t)['phase'] == 'campaign_review'


def countdown_text(s, hp=83):
    t = dialogue(s.p, [(1,14,'ENEMY SNORLAX'),(1,16,'USED HEADBUTT!')], prompt=False)
    t['cells'][10][11:18] = list(f'{hp:3}/{s.p["party"][0]["max_hp"]:3}')
    return t


def test_headbutt_countdown_only_waits_then_command_requires_native_party_hp_sync():
    s = Session(); s.throw(); s.fail(); t = countdown_text(s); before = deepcopy(s.p)
    assert s.call(t)['available_actions'] == ['wait'] and s.p == before
    cmd = command(s.p); cmd['cells'][10][11:18] = list(' 83/105')
    assert s.call(cmd)['phase'] == 'campaign_review' and s.c.throws == 1


def test_native_mainloop_party_hp_sync_allows_next_verified_command_without_fabrication():
    s = Session(); s.throw(); s.fail(); assert s.call(countdown_text(s))['available_actions'] == ['wait']
    s.p['party'][0]['hp'] = 83
    assert s.call(command(s.p))['available_actions'] == ['a','wait']
    assert s.c.throws == 1


@pytest.mark.parametrize('change',['healed','zero','wrong_max','wrong_move','prompt'])
def test_headbutt_countdown_does_not_broaden_unknown_hud_or_confirm(change):
    s = Session(); s.throw(); s.fail(); t = countdown_text(s)
    if change == 'healed': t = countdown_text(s, 101)
    elif change == 'zero': t = countdown_text(s, 0)
    elif change == 'wrong_max': t['cells'][10][17] = '6'
    elif change == 'wrong_move': t['cells'][16][7] = 'X'
    else: t['cells'][16][18] = '▼'
    assert s.call(t)['phase'] == 'campaign_review'


def test_complete_critical_with_lower_live_hud_confirms_once_then_synced_low_hp_stops_before_throw():
    s = Session(); s.throw(); s.fail()
    t = countdown_text(s, 56)
    t['cells'][14] = list(' CRITICAL HIT!'.ljust(20)); t['cells'][16] = [' '] * 20
    assert s.call(t)['available_actions'] == ['wait']
    t['cells'][16][18] = '▼'
    assert s.call(t)['available_actions'] == ['a','wait']
    assert s.call(t)['available_actions'] == ['wait']
    s.p['party'][0]['hp'] = 56
    r=s.call(command(s.p))
    assert r['review_reason'] == 'snorlax_capture_safe_switch_requires_review'
    assert s.c.throws == 1


@pytest.mark.parametrize('hp', [0,None])
def test_critical_cannot_fall_back_to_cached_upper_when_hp_is_zero_or_missing(hp):
    s = Session(); s.throw(); s.fail(); t = countdown_text(s, hp or 0)
    if hp is None: t['cells'][10] = [' '] * 20
    t['cells'][14] = list(' CRITICAL HIT!'.ljust(20))
    t['cells'][16] = [' '] * 20; t['cells'][16][18] = '▼'
    r=s.call(t)
    assert r['phase'] == 'campaign_review' and r['available_actions'] == ['wait']


def test_complete_woke_prompt_with_missing_hp_never_confirms_from_cached_upper():
    s = Session(); s.throw(); s.fail(); t = dialogue(s.p, F['enemy_prompts']['woke'])
    t['cells'][10] = [' '] * 20
    r=s.call(t)
    assert r['phase'] == 'campaign_review' and r['available_actions'] == ['wait']


@pytest.mark.parametrize('offset',[0,-1])
def test_native_headbutt_frame_is_not_lost_before_a_critical_packet(offset):
    s=Session();s.throw();s.fail();t=headbutt_animation(s)
    assert s.call(t)['available_actions']==['wait'];frame=s.frame
    critical=dialogue(s.p,[(1,14,'CRITICAL HIT!')])
    r=s.call(critical,frame=frame+offset)
    assert r['phase']=='campaign_review' and r['available_actions']==['wait']
