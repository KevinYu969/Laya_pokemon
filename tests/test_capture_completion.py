"""只用固定公開來源fixture與fake觀測；不載入ROM、存檔、模型或模擬器。"""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from laya_pokemon.capture_completion import CaptureCompletionController, INTENT, NEW_EXP, NEW_MOVES, NEW_PP
from laya_pokemon.observation import PROFILE, read_visible_text


FIXTURE = json.loads((Path(__file__).parent / 'data/capture-completion-source-fixture.json').read_text(encoding='utf-8'))
LOCATION = {'map_id': 23, 'x': 10, 'y': 61}
WILD = {'raw': 1, 'active': True, 'kind': 'wild', 'opponent_species': 'SNORLAX', 'wild_opponent_species': 'SNORLAX'}
NONE = {'raw': 0, 'active': False, 'kind': 'none', 'opponent_species': None, 'wild_opponent_species': None}


def text_at(*entries, window=True):
    cells = [[' '] * 20 for _ in range(18)]
    for x, y, value in entries:
        assert x + len(value) <= 20
        cells[y][x:x + len(value)] = list(value)
    return {'cells': cells, 'profile': PROFILE, 'read_valid': True, 'alignment_verified': True,
            'window_visible': window, 'read_error': None, 'warnings': ['保留decoder未完全校準警語']}


def progress(ball=3, quantity=6):
    def mon(species, name, level, hp, maximum, moves, pp):
        return {'species': species, 'species_name': name, 'level': level, 'exp': 20000,
                'hp': hp, 'max_hp': maximum, 'status': 0, 'moves': moves, 'pp': pp}
    return {'profile': 'gen1-wrapper-ram-progress-v1-unvalidated', 'party_read_valid': True,
            'initialization_candidate': True, 'party_count': 4, 'player_name_raw': 'KEVIN', 'money': 12000,
            'party': [mon(7, 'NIDOKING', 30, 79, 95, [61, 33, 30, 40], [15, 35, 25, 35]),
                      mon(9, 'IVYSAUR', 31, 52, 86, [75, 15, 73, 22], [20, 30, 10, 25]),
                      mon(35, 'FEAROW', 32, 80, 80, [31, 64, 43, 45], [20, 35, 30, 40]),
                      mon(102, 'EEVEE', 25, 63, 63, [33, 28, 0, 0], [35, 15, 0, 0])],
            'inventory': [{'item': 42, 'quantity': 1}, {'item': ball, 'quantity': quantity}, {'item': 73, 'quantity': 1}]}


def battle_text(p=None, enemy_status=0):
    p = progress() if p is None else p
    lead = p['party'][0]
    status = 'SLP' if enemy_status & 7 else {8: 'PSN', 16: 'BRN', 32: 'FRZ', 64: 'PAR'}.get(enemy_status, '30')
    return text_at((1, 0, 'SNORLAX'), (5, 1, status), (10, 7, lead['species_name']),
                   (15, 8, str(lead['level'])), (11, 10, f'{lead["hp"]:3}/{lead["max_hp"]:3}'),
                   (10, 14, 'FIGHT'), (10, 16, 'ITEM'), (16, 16, 'RUN'), (9, 14, '▶'))


def last_throw(ball=3, quantity=6, status=0, hp=40):
    p = progress(ball, quantity)
    return {'frame': 1000, 'now': 10., 'hud_frame': 920, 'ball_item': ball, 'progress': p,
            'location': deepcopy(LOCATION), 'battle_state': deepcopy(WILD),
            'enemy': {'species': 132, 'level': 30, 'hp': hp, 'max_hp': 140, 'status': status},
            'battle_text': battle_text(p, status)}


def page(name, snapshot=None, prompt=None):
    snap = last_throw() if snapshot is None else snapshot
    entries = FIXTURE['messages'][name]
    t = text_at(*entries)
    if name.startswith('dex_'):
        for x, y, word in FIXTURE['dex_header_projection']:
            t['cells'][y][x:x + len(word)] = list(word)
    elif name.startswith('caught_') or name.startswith('new_dex_'):
        t['cells'][:12] = deepcopy(snap['battle_text']['cells'][:12])
    if prompt is None:
        prompt = name in FIXTURE['prompt_pages']
    if prompt:
        t['cells'][16][18] = '▼'
    return t


def nickname(cursor=8):
    t = page('nickname_menu')
    t['cells'][8][16:19] = list('YES')
    t['cells'][10][16:18] = list('NO')
    if cursor is not None:
        t['cells'][cursor][15] = '▶'
    return t


def grid(frame):
    cells = [[x, y] for y in range(60, 63) for x in range(8, 12)]
    return {'observation_frame': frame, 'verified_location': [23, 10, 61],
            'screen_cells_verified': 12, 'visible_verified_cells': cells}


class Session:
    def __init__(self, snapshot=None, **limits):
        self.snapshot = last_throw() if snapshot is None else snapshot
        self.p = deepcopy(self.snapshot['progress'])
        self.c = CaptureCompletionController(deepcopy(INTENT), last_throw=self.snapshot, **limits)
        self.frame, self.now = 1000, 10.

    def call(self, t=None, *, world=False, **kwargs):
        self.frame += 40; self.now += .1
        frame = kwargs.pop('frame', self.frame)
        return self.c.context(text_at(window=False) if t is None else t, self.p,
            location=kwargs.pop('location', deepcopy(LOCATION)),
            battle_state=kwargs.pop('battle_state', deepcopy(NONE if world else WILD)),
            frame=frame, now=kwargs.pop('now', self.now), overworld_ready=kwargs.pop('overworld_ready', world),
            grid=kwargs.pop('grid', grid(frame) if world else None), **kwargs)

    def through(self, last='nickname_intro'):
        for name in ('caught_start', 'caught_receipt', 'new_dex_start', 'new_dex_receipt',
                     'dex_first', 'dex_second', 'nickname_intro'):
            result = self.call(page(name, self.snapshot))
            assert result['available_actions'] == ['a', 'wait'], result
            if name == last:
                break

    def decline(self, initializing=False):
        self.through()
        if initializing:
            self.p.update(party_count=5, party=[], party_read_valid=False, initialization_candidate=False)
        assert self.call(nickname())['available_actions'] == ['down', 'wait']
        result = self.call(nickname(10))
        assert result['available_actions'] == ['a', 'wait'] and result['menu_label'] == 'NO'

    def finalize_data(self):
        self.p = deepcopy(self.snapshot['progress'])
        e = self.snapshot['enemy']
        self.p['party'].append({'species': 132, 'species_name': 'SNORLAX', 'level': 30, 'exp': 33750,
            'hp': e['hp'], 'max_hp': e['max_hp'], 'status': e['status'], 'moves': [29, 133, 156, 0], 'pp': [15, 20, 10, 0]})
        self.p['party_count'] = 5
        ball = self.snapshot['ball_item']
        self.p['inventory'] = [dict(i, quantity=i['quantity'] - (i['item'] == ball))
                               for i in self.p['inventory'] if i['item'] != ball or i['quantity'] > 1]


def test_public_fixture_matches_fixed_source_boundaries_not_live_claims():
    assert FIXTURE['source_commit'] == 'a53671100ec22e5394ff26ec028d0812a238dae2'
    assert FIXTURE['intent'] == INTENT
    assert not FIXTURE['live_ui_calibrated']
    assert FIXTURE['snorlax']['moves'] == NEW_MOVES and FIXTURE['snorlax']['pp'] == NEW_PP
    assert FIXTURE['snorlax']['experience'] == NEW_EXP == 5 * 30**3 // 4
    sources = {x['path']: x for x in FIXTURE['sources']}
    assert len(sources) == 19 and all(x['source_commit'] == FIXTURE['source_commit'] for x in sources.values())
    dex = sources['data/pokemon/dex_text.asm']['excerpts'][0]['text']
    assert 'page "bulk builds, it"' in dex and 'next "more slothful"' in dex and '\tdex' in dex
    assert 'predef AskName' in sources['engine/pokemon/add_mon.asm']['excerpts'][0]['text']
    # 固定CalcStat的HP式；wild b=0不加EV，HP DV由四個LSB合成0..15。
    possible_hp = [((160 + dv) * 2 * 30) // 100 + 30 + 10 for dv in range(16)]
    assert [min(possible_hp), max(possible_hp)] == FIXTURE['snorlax']['fresh_wild_max_hp_range']


@pytest.mark.parametrize('ball', [2, 3, 4])
@pytest.mark.parametrize('quantity', [1, 6])
@pytest.mark.parametrize('status', [0, 2, 8, 64])
def test_complete_normal_source_pages_nickname_no_and_two_world_frames(ball, quantity, status):
    s = Session(last_throw(ball, quantity, status)); original = deepcopy(s.snapshot)
    s.decline(initializing=True); s.finalize_data()
    assert s.call(world=True)['available_actions'] == ['wait']
    result = s.call(world=True)
    assert result['capture_complete'] and result['captured_species'] == 132
    assert result['captured_level'] == 30 and result['last_throw_ball_quantity_used'] == 1
    assert s.snapshot == original and s.p['party'][:4] == original['progress']['party']
    assert not result.get('poke_flute_handoff')
    assert s.c.context(None, None, location=None, battle_state=None, frame=-1, now=float('nan')) == result


def test_last_successful_throw_baseline_does_not_require_whole_battle_one_ball():
    # 先前9→6可能是三次失敗；本候選只得到本次最後一投6→5，不讀整場初值。
    s = Session(last_throw(quantity=6)); s.decline(); s.finalize_data()
    assert next(x['quantity'] for x in s.p['inventory'] if x['item'] == 3) == 5
    s.call(world=True)
    assert s.call(world=True)['capture_complete']


def test_evolved_venusaur_roster_keeps_actual_order_and_fingerprint_through_completion():
    snap=last_throw();p=snap['progress'];plant=p['party'][1]
    plant.update(species=154,species_name='VENUSAUR',level=33,hp=105,max_hp=105,exp=30051)
    p['party']=[plant,p['party'][3],p['party'][2],p['party'][0]]
    snap['battle_text']=battle_text(p)
    s=Session(snap);s.decline();s.finalize_data();s.call(world=True)
    assert s.call(world=True)['capture_complete']
    assert [m['species'] for m in s.p['party']]==[154,102,35,7,132]


def test_both_plant_forms_cannot_replace_a_required_other_roster_member():
    snap=last_throw();p=snap['progress'];p['party'][3].update(species=154,species_name='VENUSAUR')
    snap['battle_text']=battle_text(p)
    with pytest.raises(ValueError):CaptureCompletionController(INTENT,last_throw=snap)


@pytest.mark.parametrize('name', ['caught_start', 'caught_receipt', 'new_dex_start', 'new_dex_receipt',
                                  'dex_first', 'dex_second', 'nickname_intro'])
def test_known_partial_and_blank_wait_then_full_page_confirms_exactly_once(name):
    s = Session()
    if name != 'caught_start':
        previous = list(FIXTURE['messages'])[list(FIXTURE['messages']).index(name) - 1]
        s.through(previous)
    partial = page(name)
    x, y, value = FIXTURE['messages'][name][-1]
    partial['cells'][y][x + len(value) - 1] = ' '
    partial['cells'][16][18] = ' '
    assert s.call(partial)['available_actions'] == ['wait']
    full = page(name)
    assert s.call(full)['available_actions'] == ['a', 'wait']
    assert s.call()['available_actions'] == ['wait']
    assert s.call(full)['available_actions'] == ['wait']


def test_nickname_down_semantic_lock_survives_blank_and_partial_old_page():
    s = Session(); s.through()
    assert s.call(nickname())['available_actions'] == ['down', 'wait']
    assert s.call()['available_actions'] == ['wait']
    assert s.call(page('nickname_menu'))['available_actions'] == ['wait']
    assert s.call(nickname())['available_actions'] == ['wait']
    assert s.call(nickname(10))['available_actions'] == ['a', 'wait']
    assert s.call()['available_actions'] == ['wait']
    assert s.call(nickname(10))['available_actions'] == ['wait']


@pytest.mark.parametrize('name', list(FIXTURE['messages']))
@pytest.mark.parametrize('pollution', ['YES', 'NO', 'Delete', 'UNKNOWN'])
def test_any_unexpected_upper_text_reviews_before_action_or_partial_wait(name, pollution):
    s = Session()
    if name == 'nickname_menu': s.through()
    elif name != 'caught_start':
        previous = list(FIXTURE['messages'])[list(FIXTURE['messages']).index(name) - 1]; s.through(previous)
    t = nickname() if name == 'nickname_menu' else page(name)
    t['cells'][5][0:len(pollution)] = list(pollution)
    result = s.call(t)
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']


@pytest.mark.parametrize('change', ['wrong_no_row', 'extra_yes', 'active_yes_extra', 'toss_cursor',
                                    'partial_question', 'wrong_species', 'partial_label_with_prompt', 'inactive'])
def test_nickname_unknown_layout_never_sends_a(change):
    s = Session(); s.through(); t = nickname()
    if change == 'wrong_no_row': t['cells'][10][16:18] = list('  '); t['cells'][0][1:3] = list('NO')
    elif change == 'extra_yes': t['cells'][0][0:3] = list('YES')
    elif change == 'active_yes_extra': t['cells'][0][0] = '▶'
    elif change == 'toss_cursor': t['cells'][8][15] = ' '; t['cells'][11][14] = '▶'
    elif change == 'partial_question': t['cells'][16][11] = ' '
    elif change == 'wrong_species': t['cells'][16][4:11] = list('PIKACHU')
    elif change == 'partial_label_with_prompt': t['cells'][10][17] = ' '; t['cells'][16][18] = '▼'
    else: t['cells'][8][15] = '▷'
    result = s.call(t)
    assert result['available_actions'] == ['wait'] and not s.c.no_confirmed


def test_nickname_initial_no_without_requested_down_is_not_auto_confirmed():
    s = Session(); s.through()
    assert s.call(nickname(10))['review_reason'] == 'capture_completion_no_cursor_without_requested_move'


@pytest.mark.parametrize('name', ['caught_start', 'caught_receipt', 'new_dex_start', 'new_dex_receipt', 'dex_first', 'nickname_intro'])
def test_prompt_requires_complete_page_and_no_wrong_cursor(name):
    s = Session()
    if name != 'caught_start': s.through(list(FIXTURE['messages'])[list(FIXTURE['messages']).index(name) - 1])
    t = page(name); x, y, value = FIXTURE['messages'][name][-1]; t['cells'][y][x + len(value) - 1] = ' '
    assert s.call(t)['phase'] == 'campaign_review'


@pytest.mark.parametrize('change', ['wrong_species', 'wrong_number', 'height', 'weight', 'missing_period', 'unknown_lower', 'final_arrow'])
def test_dex_both_pages_geometry_and_final_end_are_verified(change):
    s = Session(); s.through('dex_first'); t = page('dex_second')
    if change == 'wrong_species': t['cells'][2][9:16] = list('PIKACHU')
    elif change == 'wrong_number': t['cells'][8][4:7] = list('132')
    elif change == 'height': t['cells'][6][13] = '7'
    elif change == 'weight': t['cells'][8][11] = '9'
    elif change == 'missing_period': t['cells'][15][13] = ' '
    elif change == 'unknown_lower': t['cells'][16][1:7] = list('Delete')
    else: t['cells'][16][18] = '▼'
    result = s.call(t)
    assert result['available_actions'] == ['wait'] and s.c.stage != 'nickname_intro'


@pytest.mark.parametrize('mutation', [lambda p: p['party'][0].update(hp=78), lambda p: p['party'].reverse(),
    lambda p: p['party'][1]['moves'].__setitem__(0, 33), lambda p: p['inventory'][0].update(quantity=2),
    lambda p: p['inventory'][1].update(quantity=5), lambda p: p.update(player_name_raw='BLUE'),
    lambda p: p.update(money=11999)])
def test_fingerprint_errors_precede_partial_and_blank_wait(mutation):
    s = Session(); mutation(s.p)
    assert s.call()['phase'] == 'campaign_review'


@pytest.mark.parametrize('field,value', [('species', 148), ('level', 29), ('hp', 140), ('max_hp', 141),
    ('status', 8), ('exp', 33749), ('moves', [29, 133, 34, 0]), ('pp', [1, 20, 10, 0]),
    ('species_name', 'KEVIN'), ('nickname', 'KEVIN')])
def test_new_member_requires_real_capture_hp_status_species_level_moves_and_fresh_pp(field, value):
    s = Session(); s.decline(); s.finalize_data(); s.p['party'][4][field] = value
    result = s.call(world=True)
    assert result['review_reason'] in {'capture_completion_new_snorlax_fingerprint_invalid', 'capture_completion_party_unverified'}
    assert result['available_actions'] == ['wait'] and not s.c.completion


def test_party_count_five_alone_never_completes_and_missing_data_cannot_hide_other_error():
    s = Session(); s.decline(initializing=True)
    assert s.call(world=True)['available_actions'] == ['wait']
    assert not s.c.completion
    s.p['player_name_raw'] = 'BLUE'
    assert s.call()['review_reason'] == 'capture_completion_player_name_changed'


@pytest.mark.parametrize('field,value', [('party_read_valid', None), ('party_count', 6), ('initialization_candidate', True)])
def test_unknown_or_wrong_initializing_party_does_not_get_source_timing_exception(field, value):
    s = Session(); s.through(); s.p.update(party=[], party_count=5, party_read_valid=False, initialization_candidate=False)
    s.p[field] = value
    assert s.call(nickname())['phase'] == 'campaign_review'


def test_early_party_five_and_skipped_newdex_or_full_caught_string_review():
    s = Session(); s.finalize_data()
    assert s.call(page('caught_start'))['phase'] == 'campaign_review'
    s = Session(); s.through('caught_receipt')
    assert s.call(page('nickname_intro'))['phase'] == 'campaign_review'
    s = Session()
    assert s.call(text_at((1, 14, 'SNORLAX was'), (1, 16, 'caught!'), (18, 16, '▼')))['phase'] == 'campaign_review'


@pytest.mark.parametrize('field,value', [('read_valid', False), ('alignment_verified', False), ('profile', 'other'),
    ('window_visible', None), ('read_error', 'partial')])
def test_actual_decoder_proof_required_even_if_page_looks_complete(field, value):
    s = Session(); t = page('caught_start'); t[field] = value
    assert s.call(t)['review_reason'] == 'capture_completion_decoder_proof_required'


def test_actual_decoder_unaligned_scanline_with_retained_receipt_never_a():
    class Tiles:
        def __init__(self): self.data = {}
        def __getitem__(self, xy): return self.data.get(xy, 0)
    source = page('caught_start'); chars = set(''.join(''.join(r) for r in source['cells']))
    decoding = {i: c for i, c in enumerate(sorted(chars), 1)}; encoding = {v: k for k, v in decoding.items()}
    tiles = Tiles()
    for y, row in enumerate(source['cells']):
        for x, c in enumerate(row): tiles.data[x, y] = encoding[c]
    positions = [[0, 0, 0, 0] for _ in range(144)]
    for line in positions[:8]: line[0] = 4
    fake = SimpleNamespace(memory={0xFF40: 0x91}, tilemap_background=tiles, tilemap_window=Tiles(),
                           screen=SimpleNamespace(tilemap_position_list=positions))
    text = read_visible_text(fake, decoding)
    assert not text['read_valid'] and any('CAUGHT' not in x for x in text['lines'])
    assert Session().call(text)['review_reason'] == 'capture_completion_decoder_proof_required'


@pytest.mark.parametrize('field,value', [('raw', 2), ('active', None), ('kind', 'trainer'),
    ('opponent_species', 'ABRA'), ('wild_opponent_species', 143), ('enemy_level', 31)])
def test_wrong_battle_state_never_advances(field, value):
    b = deepcopy(WILD); b[field] = value
    assert Session().call(page('caught_start'), battle_state=b)['phase'] == 'campaign_review'


def test_same_frame_unchanged_no_resend_changed_packet_reviews():
    s = Session(); t = page('caught_start'); s.call(t); frame = s.frame
    assert s.call(t, frame=frame)['available_actions'] == ['wait']
    assert s.call(page('caught_receipt'), frame=frame)['review_reason'] == 'capture_completion_same_frame_changed_packet'


@pytest.mark.parametrize('clock', [True, -1, float('nan'), float('inf'), '10'])
def test_invalid_clock_stops(clock):
    assert Session().call(page('caught_start'), now=clock)['review_reason'] == 'capture_completion_clock_or_frame_invalid'


def test_time_calls_waits_and_mutated_intent_are_bounded_and_latched():
    s = Session(max_calls=1); s.call(); assert s.call()['review_reason'] == 'capture_completion_transaction_budget_exhausted'
    s = Session(); assert s.call(now=71)['review_reason'] == 'capture_completion_transaction_budget_exhausted'
    s = Session(max_waits=1); s.call(); assert s.call()['review_reason'] == 'capture_completion_wait_budget_exhausted'
    s = Session(); s.c.intent['nickname'] = 'YES'
    failure = s.call(page('caught_start'))
    assert failure['review_reason'] == 'capture_completion_intent_changed'
    assert s.call(nickname()) == failure


@pytest.mark.parametrize('change', ['no_grid', 'old_frame', 'wrong_position', 'count_bool', 'few_cells', 'duplicates',
                                    'missing_player', 'visible_window', 'battle_still_wild', 'upper_delete', 'menu'])
def test_closing_requires_real_same_frame_grid_and_no_ui(change):
    s = Session(); s.decline(); s.finalize_data(); t = text_at(window=False); g = grid(s.frame + 40); battle = deepcopy(NONE)
    if change == 'no_grid': g = None
    elif change == 'old_frame': g['observation_frame'] -= 1
    elif change == 'wrong_position': g['verified_location'][1] = 11
    elif change == 'count_bool': g['screen_cells_verified'] = True
    elif change == 'few_cells': g['screen_cells_verified'] = 11; g['visible_verified_cells'].pop()
    elif change == 'duplicates': g['visible_verified_cells'][-1] = g['visible_verified_cells'][0]
    elif change == 'missing_player': g['visible_verified_cells'][6] = [20, 70]
    elif change == 'visible_window': t['window_visible'] = True
    elif change == 'battle_still_wild': battle = deepcopy(WILD)
    elif change == 'upper_delete': t['cells'][0][0:6] = list('Delete')
    else: t = nickname(10)
    result = s.call(t, world=True, grid=g, battle_state=battle)
    assert result['phase'] == 'campaign_review' and not s.c.completion


def test_two_world_frames_are_distinct_and_interrupted_proof_restarts_confirmation():
    s = Session(); s.decline(); s.finalize_data()
    assert not s.call(world=True)['capture_complete']
    assert not s.call()['capture_complete']
    assert not s.call(world=True)['capture_complete']
    assert s.call(world=True)['capture_complete']


def test_all_input_objects_copied_or_left_unchanged():
    snap = last_throw(); original = deepcopy(snap); s = Session(snap)
    t = page('caught_start'); loc = deepcopy(LOCATION); b = deepcopy(WILD)
    before = deepcopy((t, s.p, loc, b))
    s.call(t, location=loc, battle_state=b)
    assert (t, s.p, loc, b) == before and snap == original
    snap['progress']['party'][0]['hp'] -= 1
    assert s.c.before_party[0]['hp'] == 79


@pytest.mark.parametrize('change', ['no_enemy', 'wrong_level', 'wrong_hp', 'bool_ball', 'master_ball', 'full_party',
                                    'missing_pp', 'old_name', 'hud_delete', 'hud_false', 'hud_level', 'hud_money', 'too_old_frame'])
def test_constructor_demands_real_last_throw_snapshot_not_whole_battle_guess(change):
    snap = last_throw()
    if change == 'no_enemy': snap.pop('enemy')
    elif change == 'wrong_level': snap['enemy']['level'] = 29
    elif change == 'wrong_hp': snap['enemy']['max_hp'] = 300
    elif change == 'bool_ball': snap['ball_item'] = True
    elif change == 'master_ball': snap['ball_item'] = 1
    elif change == 'full_party': snap['progress']['party_count'] = 6
    elif change == 'missing_pp': snap['progress']['party'][0].pop('pp')
    elif change == 'old_name': snap['progress']['party'][0]['species_name'] = 'KEVIN'
    elif change == 'hud_delete': snap['battle_text']['cells'][5][0:6] = list('Delete')
    elif change == 'hud_false': snap['battle_text']['read_valid'] = False
    elif change == 'hud_level': snap['battle_text']['cells'][1][5:7] = list('29')
    elif change == 'hud_money': snap['battle_text']['cells'][14][0:6] = list('Delete')
    else: snap['hud_frame'] = 1001
    with pytest.raises(ValueError): CaptureCompletionController(INTENT, last_throw=snap)


@pytest.mark.parametrize('field,value', [('max_calls', True), ('max_calls', 241), ('max_calls', 0),
    ('max_waits', 241), ('max_seconds', 61), ('max_seconds', float('nan')), ('max_seconds', False)])
def test_constructor_budgets_cannot_be_extended(field, value):
    with pytest.raises(ValueError): CaptureCompletionController(INTENT, last_throw=last_throw(), **{field: value})


@pytest.mark.parametrize('mutation', [lambda x: x.update(species=148), lambda x: x.update(level=31),
    lambda x: x.update(map_id=28), lambda x: x.update(party_count_before=True),
    lambda x: x.update(nickname='YES'), lambda x: x.update(dex_branch='skip'), lambda x: x.update(extra=True)])
def test_constructor_intent_only_accepts_fixed_source_case(mutation):
    intent = deepcopy(INTENT); mutation(intent)
    with pytest.raises(ValueError): CaptureCompletionController(intent, last_throw=last_throw())


@pytest.mark.parametrize('field', ['text', 'progress', 'location', 'battle'])
def test_optional_frame_tags_cannot_be_forged_as_same_observation(field):
    s = Session(); t = page('caught_start'); loc = deepcopy(LOCATION); b = deepcopy(WILD)
    obj = {'text': t, 'progress': s.p, 'location': loc, 'battle': b}[field]
    obj['observation_frame'] = 1039
    result = s.call(t, location=loc, battle_state=b)
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']


@pytest.mark.parametrize('value', [132.0, True, None, '132', 'snorlax'])
def test_opponent_species_type_is_not_coerced(value):
    b = deepcopy(WILD); b['opponent_species'] = value
    assert Session().call(page('caught_start'), battle_state=b)['phase'] == 'campaign_review'


def test_no_ball_deduction_or_two_balls_never_completes():
    s = Session(); s.decline(); s.finalize_data()
    s.p['inventory'][1]['quantity'] = 6
    assert not s.call(world=True)['capture_complete']
    assert not s.call(world=True)['capture_complete']
    s.p['inventory'][1]['quantity'] = 4
    assert s.call(world=True)['review_reason'] == 'capture_completion_inventory_changed'


def test_real_decoder_metadata_lines_cannot_disagree_with_cells():
    t = page('caught_start'); t.update(lines=['SNORLAX was caught!'], line_rows=[14])
    assert Session().call(t)['review_reason'] == 'capture_completion_decoder_proof_required'


def test_dex_special_glyph_projection_is_actual_decoder_behavior_not_invented_text():
    from pyboy.plugins.game_wrapper_pokemon_gen1_constants import POKEMON_TEXT_DECODING
    class Tiles:
        def __init__(self, values): self.values = values
        def __getitem__(self, xy): return self.values.get(xy, 0x7f)
    values = {(i, 0): value for i, value in enumerate(FIXTURE['decoder_blank_glyphs'].values())}
    fake = SimpleNamespace(memory={0xFF40: 0x91}, tilemap_background=Tiles(values), tilemap_window=Tiles({}),
        screen=SimpleNamespace(tilemap_position_list=[[0, 0, 0, 0] for _ in range(144)]))
    result = read_visible_text(fake, POKEMON_TEXT_DECODING)
    assert result['read_valid'] and result['alignment_verified']
    assert not ''.join(''.join(row) for row in result['cells']).strip()


def test_same_frame_world_observation_never_counts_as_second_frame():
    s = Session(); s.decline(); s.finalize_data()
    assert not s.call(world=True)['capture_complete']
    frame = s.frame
    assert not s.call(world=True, frame=frame, grid=grid(frame))['capture_complete']
    assert s.call(world=True)['capture_complete']


def placeholder():
    return text_at((9,2,'SNORLAX'),(9,4,'SLEEPING'),(9,6,'HT'),(13,6,'?'),(15,6,'??'),
                   (4,8,'143'),(9,8,'WT'),(14,8,'???'),(17,8,'lb'))


def test_initial_source_dex_question_marks_only_wait_then_real_owned_page_can_confirm():
    s=Session();s.through(last='new_dex_receipt');t=placeholder();before=deepcopy(t)
    assert s.call(t)['available_actions']==['wait']
    assert s.call(t)['available_actions']==['wait'] and t==before
    assert s.call(page('dex_first',s.snapshot))['available_actions']==['a','wait']


@pytest.mark.parametrize('change',['species','dex_number','wrong_question_position','prompt','unknown_body'])
def test_dex_placeholder_cannot_accept_other_header_or_confirm_unknown_page(change):
    s=Session();s.through(last='new_dex_receipt');t=placeholder()
    if change=='species':t['cells'][2][9]='X'
    elif change=='dex_number':t['cells'][8][6]='4'
    elif change=='wrong_question_position':t['cells'][6][13],t['cells'][6][12]=' ','?'
    elif change=='prompt':t['cells'][16][18]='▼'
    else:t['cells'][11][1]='X'
    assert s.call(t)['phase']=='campaign_review'
