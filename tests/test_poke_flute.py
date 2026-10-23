"""純合成 decoder/progress/context；不讀ROM、存檔或實況，不執行按鍵。"""
from copy import deepcopy

import pytest

from laya_pokemon.observation import PROFILE
from laya_pokemon.poke_flute import INTENT, PokeFluteController


LABELS = {4: 'POKé BALL', 234: 'TM34', 42: 'HELIX FOSSIL', 49: 'NUGGET',
          63: 'S.S.TICKET', 228: 'TM28', 196: 'HM01', 73: 'POKé FLUTE',
          40: 'RARE CANDY', 72: 'SILPH SCOPE'}
KEYS = {42, 63, 196, 73, 72}
STANCE = {'map_id': 23, 'x': 10, 'y': 61, 'facing': 'down', 'facing_raw': 0}
NONE = {'raw': 0, 'active': False, 'kind': 'none', 'opponent_species': None, 'wild_opponent_species': None}
WILD = {'raw': 1, 'active': True, 'kind': 'wild', 'opponent_species': 'SNORLAX', 'wild_opponent_species': 'SNORLAX'}


def text_at(*entries, window=False):
    cells = [[' '] * 20 for _ in range(18)]
    for x, y, value in entries:
        for dx, char in enumerate(value):
            cells[y][x + dx] = char
    return {'profile': PROFILE, 'read_valid': True, 'alignment_verified': True,
            'window_visible': window, 'read_error': None, 'cells': cells,
            'warnings': ['文字候選尚未完全校準；原本的warning必須保留相容。']}


def progress(items=None):
    def mon(species, name, level, moves, pp, hp=79, max_hp=95):
        return {'species': species, 'species_name': name, 'level': level, 'exp': 20000,
                'hp': hp, 'max_hp': max_hp, 'status': 0, 'moves': moves, 'pp': pp}
    party = [mon(7, 'NIDOKING', 30, [61, 33, 30, 40], [15, 35, 25, 35]),
             mon(9, 'IVYSAUR', 31, [75, 15, 73, 22], [20, 30, 10, 25], 52, 86)]
    inventory = items if items is not None else [4, 234, 42, 49, 63, 228, 196, 73]
    return {'profile': 'gen1-wrapper-ram-progress-v1-unvalidated', 'initialization_candidate': True,
            'party_read_valid': True, 'party_count': 2, 'party': party, 'player_name_raw': 'KEVIN',
            'inventory': [{'item': i, 'quantity': 6 if i == 4 else 1} for i in inventory],
            'story_event_bits': {'beat_route12_snorlax': False}}


def start(cursor=6):
    labels = [(2, 'POKéDEX'), (4, 'POKéMON'), (6, 'ITEM'), (8, 'KEVIN'),
              (10, 'SAVE'), (12, 'OPTION'), (14, 'EXIT')]
    return text_at(*[(12, y, label) for y, label in labels], (11, cursor, '▶'), window=True)


def bag(p, *, offset=0, cursor=0, inactive=False, more=False):
    entries = [(5, 4 + cursor * 2, '▷' if inactive else '▶'), (12, 14, 'EXIT')]
    for n in range(4):
        index, y = offset + n, 4 + n * 2
        if index >= len(p['inventory']):
            entries.append((6, y, 'CANCEL'))
            break
        item = p['inventory'][index]
        entries.append((6, y, LABELS[item['item']]))
        if item['item'] not in KEYS:
            entries.append((14, y + 1, f'×{item["quantity"]:2d}'))
    if more:
        entries.append((18, 11, '▼'))
    return text_at(*entries, window=True)


def use_screen(selected, *, cursor=11):
    t = deepcopy(selected)
    for row in t['cells']:
        for x, c in enumerate(row):
            if c == '▶': row[x] = '▷'
    for y in range(10, 15):
        t['cells'][y][13:20] = [' '] * 7
    for x, y, value in [(15, 11, 'USE'), (15, 13, 'TOSS'), (14, cursor, '▶')]:
        t['cells'][y][x:x + len(value)] = list(value)
    return t


def played(*, prompt=True, partial=None):
    if partial is not None:
        return text_at((1, 14, partial), window=True)
    entries = [(1, 14, 'KEVIN played the'), (1, 16, 'POKé FLUTE.')]
    if prompt: entries.append((18, 16, '▼'))
    return text_at(*entries, window=True)


def woke(*, prompt=True):
    entries = [(1, 14, 'SNORLAX woke up!')]
    if prompt: entries.append((18, 16, '▼'))
    return text_at(*entries, window=True)


def rage():
    return text_at((1, 14, 'It attacked in a'), (1, 16, 'grumpy rage!'), window=True)


def wild_hud(level='30', *, command=False):
    entries = [(1, 0, 'SNORLAX'), (5, 1, level)]
    if command:
        entries += [(10, 14, 'FIGHT'), (16, 14, 'PKMN'), (10, 16, 'ITEM'),
                    (16, 16, 'RUN'), (9, 14, '▶')]
    else:
        entries += [(1, 14, 'Wild SNORLAX'), (1, 16, 'appeared!'), (18, 16, '▼')]
    return text_at(*entries, window=True)


class Session:
    def __init__(self, p=None, **limits):
        self.p = progress() if p is None else p
        self.c = PokeFluteController(deepcopy(INTENT), **limits)
        self.frame, self.now = 0, 0
        self.selected = None

    def call(self, t=None, **kwargs):
        self.frame += 40; self.now += .1
        return self.c.context(text_at() if t is None else t, self.p,
                              location=kwargs.pop('location', deepcopy(STANCE)),
                              battle_state=kwargs.pop('battle_state', deepcopy(NONE)),
                              frame=kwargs.pop('frame', self.frame), now=kwargs.pop('now', self.now), **kwargs)

    def to_bag(self):
        assert self.call(overworld_ready=True)['available_actions'] == ['start', 'wait']
        assert self.call(start())['available_actions'] == ['a', 'wait']

    def select(self):
        self.to_bag()
        target = next(n for n, i in enumerate(self.p['inventory']) if i['item'] == 73)
        for index in range(target + 1):
            offset, cursor = max(0, index - 2), min(index, 2)
            self.selected = bag(self.p, offset=offset, cursor=cursor, more=index < target - 1)
            result = self.call(self.selected)
            assert result['available_actions'] == (['a', 'wait'] if index == target else ['down', 'wait']), result

    def use(self):
        self.select()
        assert self.call(use_screen(self.selected))['available_actions'] == ['a', 'wait']

    def play(self):
        self.use()
        assert self.call(played())['available_actions'] == ['a', 'wait']


@pytest.mark.parametrize('items', [[73], [4, 73, 42, 49], [4, 234, 42, 49, 63, 228, 196, 73]])
def test_normal_three_bag_viewport_sequences_only_wake_and_handoff(items):
    s = Session(progress(items)); before = deepcopy(s.p)
    s.play()
    assert s.call(woke())['available_actions'] == ['a', 'wait']
    assert s.call(rage())['available_actions'] == ['a', 'wait']
    result = s.call(wild_hud(), battle_state=WILD)
    assert result['poke_flute_handoff'] and not result['captured'] and not result['capture_complete']
    assert result['wild_species'] == 132 and result['visible_wild_level'] == 30
    assert result['flute_quantity_used'] == 0 and s.p == before
    assert not result.get('complete') and not result.get('poke_flute_complete')


@pytest.mark.parametrize('change', [lambda d: d.update(kind='catch_snorlax'), lambda d: d.update(map_id=28),
    lambda d: d.update(player_y=63), lambda d: d.update(facing='up'), lambda d: d.update(species=143),
    lambda d: d.update(item=True), lambda d: d.update(level=29), lambda d: d.update(extra=True)])
def test_intent_exact_and_copied(change):
    intent = deepcopy(INTENT); change(intent)
    with pytest.raises(ValueError): PokeFluteController(intent)
    good = deepcopy(INTENT); c = PokeFluteController(good); good['item'] = 4
    assert c.intent == INTENT


@pytest.mark.parametrize('limits', [{'max_calls': 241}, {'max_calls': True}, {'max_calls': 0},
    {'max_waits': 241}, {'max_seconds': 61}, {'max_seconds': True}, {'max_seconds': float('nan')}])
def test_limits_cannot_extend_budget(limits):
    with pytest.raises(ValueError): PokeFluteController(INTENT, **limits)


@pytest.mark.parametrize('mutation', [lambda p: p.update(profile='other'), lambda p: p.update(initialization_candidate=1),
    lambda p: p.update(party_read_valid=1), lambda p: p.update(party_count=True),
    lambda p: p['party'][0].update(species=31), lambda p: p['party'][0].update(species_name='SNORLAX'),
    lambda p: p['party'][0].update(hp=96), lambda p: p['party'][0].update(level=True),
    lambda p: p['party'][0].update(pp=[True, 35, 25, 35]), lambda p: p.update(player_name_raw='RED'),
    lambda p: p['inventory'].append({'item': 73, 'quantity': 1}),
    lambda p: p['inventory'][-1].update(quantity=2), lambda p: p['inventory'][-1].update(quantity=True),
    lambda p: p.update(inventory=[{'item': 255, 'quantity': 1}]),
    lambda p: p['story_event_bits'].update(beat_route12_snorlax=True),
    lambda p: p['story_event_bits'].update(beat_route12_snorlax=None)])
def test_preconditions_fail_closed_before_start(mutation):
    p = progress(); mutation(p); result = Session(p).call(overworld_ready=True)
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']


@pytest.mark.parametrize('field,value', [('map_id', 24), ('x', 9), ('y', 62), ('facing', 'up'),
                                       ('facing_raw', True), ('facing_raw', 4), ('x', True)])
def test_fixed_stance_never_corrected_by_guessing(field, value):
    loc = deepcopy(STANCE); loc[field] = value
    assert Session().call(location=loc, overworld_ready=True)['available_actions'] == ['wait']


@pytest.mark.parametrize('field,value', [('profile', None), ('profile', 'other'), ('read_valid', False),
    ('read_valid', 1), ('alignment_verified', False), ('alignment_verified', 1),
    ('window_visible', None), ('window_visible', 0), ('read_error', 'incomplete')])
def test_exact_decoder_proof_required_even_if_blank_looks_overworld(field, value):
    t = text_at(); t[field] = value
    assert Session().call(t, overworld_ready=True)['review_reason'] == 'poke_flute_decoder_proof_required'


def test_legacy_no_profile_or_incomplete_cells_cannot_enter():
    t = text_at(); del t['profile']
    assert Session().call(t, overworld_ready=True)['phase'] == 'campaign_review'
    t = text_at(); t['cells'][0] = [' '] * 19
    assert Session().call(t, overworld_ready=True)['review_reason'] == 'poke_flute_full_cells_required'


@pytest.mark.parametrize('t', [start(), text_at((0, 0, '▶')), text_at((1, 14, 'A sleeping POKéMON')),
                              text_at((0, 0, 'ITEM')), text_at(window=True)])
def test_initial_existing_ui_never_passes_overworld_flag(t):
    assert Session().call(t, overworld_ready=True)['phase'] == 'campaign_review'


def test_same_frame_same_packet_and_static_start_are_not_resent():
    s = Session(); t = text_at(); result = s.call(t, overworld_ready=True)
    assert result['available_actions'] == ['start', 'wait']
    assert s.call(t, frame=40, overworld_ready=True)['available_actions'] == ['wait']
    assert s.call(t, overworld_ready=True)['available_actions'] == ['wait']
    assert s.call(start(2))['available_actions'] == ['down', 'wait']
    assert s.call(start(2))['available_actions'] == ['wait']
    assert s.call(start(4))['available_actions'] == ['down', 'wait']
    assert s.call(start(6))['available_actions'] == ['a', 'wait']
    assert s.call(start(6))['available_actions'] == ['wait']


def test_changed_packet_on_same_frame_is_not_new_choice():
    s = Session(); s.call(overworld_ready=True)
    assert s.call(start(), frame=40)['review_reason'] == 'poke_flute_same_frame_changed_packet'


def test_same_frame_window_proof_change_is_not_hidden_by_identical_blank_cells():
    s = Session(); s.call(overworld_ready=True)
    assert s.call(text_at(window=True), frame=40, overworld_ready=True)['review_reason'] == 'poke_flute_same_frame_changed_packet'


@pytest.mark.parametrize('field', ['progress', 'location', 'battle', 'text'])
def test_optional_frame_tags_must_match_without_forging(field):
    s = Session(); t = text_at(); loc, b = deepcopy(STANCE), deepcopy(NONE)
    obj = {'progress': s.p, 'location': loc, 'battle': b, 'text': t}[field]
    obj['observation_frame'] = 39
    assert s.call(t, location=loc, battle_state=b, overworld_ready=True)['phase'] == 'campaign_review'


def test_known_start_partial_waits_but_unknown_does_not():
    s = Session(); s.call(overworld_ready=True)
    assert s.call(text_at((12, 2, 'POKéD'), window=True))['available_actions'] == ['wait']
    assert s.call(start())['available_actions'] == ['a', 'wait']
    s = Session(); s.call(overworld_ready=True)
    assert s.call(text_at((0, 0, 'UNKNOWN')))['phase'] == 'campaign_review'


@pytest.mark.parametrize('change', ['shifted', 'duplicate', 'extra_cursor', 'partial_cursor', 'label_suffix'])
def test_start_layout_and_partial_markers_must_be_exact(change):
    s = Session(); s.call(overworld_ready=True); t = start()
    if change == 'shifted': t['cells'][6][12:16] = list(' ITE')
    elif change == 'duplicate': t['cells'][0][0:4] = list('ITEM')
    elif change == 'extra_cursor': t['cells'][0][0] = '▶'
    elif change == 'partial_cursor': t['cells'][4][12:19] = list('POKé   ')
    else: t['cells'][6][16] = 'X'
    assert s.call(t)['phase'] == 'campaign_review'


def test_static_bag_down_request_never_repeats_and_preview_row_is_not_selectable():
    s = Session(progress([4, 234, 42, 73, 49])); s.to_bag()
    t = bag(s.p, cursor=2, more=True)
    assert s.call(t)['available_actions'] == ['down', 'wait']
    assert s.call(t)['available_actions'] == ['wait']
    assert s.call(bag(s.p, offset=1, cursor=2))['menu_label'] == 'POKé FLUTE'


def test_reverse_scroll_and_inactive_bag_are_verified_without_a():
    s = Session(progress([4, 73, 42, 49])); s.to_bag()
    assert s.call(bag(s.p, cursor=2))['available_actions'] == ['up', 'wait']
    assert s.call(bag(s.p, cursor=1, inactive=True))['available_actions'] == ['wait']
    assert s.call(bag(s.p, cursor=1))['available_actions'] == ['a', 'wait']


@pytest.mark.parametrize('change', ['quantity', 'order', 'unknown', 'cursor_on_preview', 'extra_cursor',
                                   'bad_more_arrow', 'lower_unknown', 'duplicate_viewport'])
def test_unknown_bag_never_scrolls_or_selects(change):
    s = Session(); s.to_bag(); t = bag(s.p, more=True)
    if change == 'quantity': t['cells'][5][15] = '9'
    elif change == 'order': t['cells'][6][6:10] = list('HM01')
    elif change == 'unknown': t['cells'][4][6:16] = list('ULTRA BALL')
    elif change == 'cursor_on_preview': t['cells'][4][5] = ' '; t['cells'][10][5] = '▶'
    elif change == 'extra_cursor': t['cells'][0][0] = '▶'
    elif change == 'bad_more_arrow': t['cells'][11][18] = ' '; t['cells'][16][18] = '▼'
    elif change == 'lower_unknown': t['cells'][16][1:7] = list('Delete')
    else: t['cells'][6][6:10] = list('TM34'); t['cells'][8][6:18] = list('TM34        ')
    assert s.call(t)['phase'] == 'campaign_review'


def test_bag_wrong_direction_or_jump_stops():
    s = Session(); s.to_bag(); s.call(bag(s.p, cursor=1))
    assert s.call(bag(s.p, cursor=0))['review_reason'] == 'poke_flute_bag_moved_opposite_to_request'
    s = Session(); s.to_bag(); s.call(bag(s.p, cursor=0))
    assert s.call(bag(s.p, offset=2, cursor=2))['review_reason'] == 'poke_flute_bag_cursor_jumped'


def test_selected_flute_and_use_are_confirmed_only_once():
    s = Session(); s.select()
    assert s.call(s.selected)['available_actions'] == ['wait']
    inactive = deepcopy(s.selected)
    inactive['cells'][8][5] = '▷'
    assert s.call(inactive)['available_actions'] == ['wait']
    u = use_screen(s.selected)
    assert s.call(u)['available_actions'] == ['a', 'wait']
    assert s.call(u)['available_actions'] == ['wait']


@pytest.mark.parametrize('change', ['toss_cursor', 'fake_use', 'shifted', 'duplicate', 'extra_cursor',
                                   'wrong_inactive', 'quantity_background', 'visible_prompt'])
def test_use_toss_never_tosses_and_rejects_ambiguous_ui(change):
    s = Session(); s.select(); t = use_screen(s.selected)
    if change == 'toss_cursor': t['cells'][11][14] = ' '; t['cells'][13][14] = '▶'
    elif change == 'fake_use': t['cells'][11][18] = 'D'
    elif change == 'shifted': t['cells'][11][14:18] = list('    '); t['cells'][10][14:18] = list('▶USE')
    elif change == 'duplicate': t['cells'][0][0:3] = list('USE')
    elif change == 'extra_cursor': t['cells'][0][0] = '▶'
    elif change == 'wrong_inactive': t['cells'][8][5] = ' '; t['cells'][6][5] = '▷'
    elif change == 'quantity_background': t['cells'][7][14:18] = list('× 8 ')
    else: t['cells'][16][18] = '▼'
    result = s.call(t)
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']


def test_toss_cursor_after_use_is_never_repaired_or_confirmed():
    s = Session(); s.use()
    assert s.call(use_screen(s.selected, cursor=13))['review_reason'] == 'poke_flute_use_cursor_not_exactly_use'


def test_partial_flute_text_music_woke_and_rage_are_bounded_and_not_reconfirmed():
    s = Session(); s.use()
    assert s.call(played(partial='KEVIN played'))['available_actions'] == ['wait']
    assert s.call(played(prompt=False))['available_actions'] == ['wait']
    assert not s.c.played_confirmed
    assert s.call(played())['available_actions'] == ['a', 'wait']
    assert s.call(played(prompt=False))['available_actions'] == ['wait']
    assert s.call(played())['available_actions'] == ['wait']
    assert s.call()['available_actions'] == ['wait']
    assert s.call(text_at((1, 14, 'SNORLAX woke'), window=True))['available_actions'] == ['wait']
    assert s.call(woke(prompt=False))['available_actions'] == ['wait']
    assert s.call(woke())['available_actions'] == ['a', 'wait']
    assert s.call(woke(prompt=False))['available_actions'] == ['wait']
    assert s.call(woke())['available_actions'] == ['wait']
    assert s.call(rage())['available_actions'] == ['a', 'wait']


def test_final_display_text_wait_receives_one_a_then_waits_through_repeated_or_blank_pages():
    s = Session(); s.play()
    assert s.call(woke())['available_actions'] == ['a', 'wait']
    first = s.call(rage())
    assert first['available_actions'] == ['a', 'wait']
    assert first['poke_flute_tactic'] == 'confirm_final_rage_display_text_return_once'
    for t in [rage(), text_at(), rage(), rage()]:
        assert s.call(t)['available_actions'] == ['wait']
    handoff = s.call(wild_hud(), battle_state=WILD)
    assert handoff['poke_flute_handoff'] and not handoff['capture_complete']


@pytest.mark.parametrize('partial', ['It attacked', 'It attacked in a', 'It attacked in a grumpy rage'])
def test_final_rage_partial_page_never_confirms_display_text_return(partial):
    s = Session(); s.play(); s.call(woke())
    # Source wraps the complete sentence to the next text line; partials wait.
    if len(partial) <= 18:
        t = text_at((1, 14, partial), window=True)
    else:
        t = text_at((1, 14, 'It attacked in a'), (1, 16, partial[17:]), window=True)
    assert s.call(t)['available_actions'] == ['wait']


def test_complete_wild_intro_without_hud_gets_one_a_to_reveal_level_before_handoff():
    s=Session();s.play();s.call(woke());s.call(rage())
    intro=text_at((1,14,'Wild SNORLAX'),(1,16,'appeared!'),(18,16,'▼'),window=True)
    result=s.call(intro,battle_state=WILD)
    assert result['available_actions']==['a','wait'] and not result.get('poke_flute_handoff')
    for t in [intro,text_at(),intro]:
        assert s.call(t,battle_state=WILD)['available_actions']==['wait']
    result=s.call(wild_hud(),battle_state=WILD)
    assert result['poke_flute_handoff'] and result['visible_wild_level']==30


@pytest.mark.parametrize('change',[lambda t:t['cells'][16].__setitem__(18,' '),
    lambda t:t['cells'][14].__setitem__(12,' '),lambda t:t['cells'][1].__setitem__(1,'X')])
def test_wild_intro_without_exact_full_text_or_blank_upper_never_confirms(change):
    s=Session();s.play();s.call(woke());s.call(rage())
    t=text_at((1,14,'Wild SNORLAX'),(1,16,'appeared!'),(18,16,'▼'),window=True);change(t)
    assert s.call(t,battle_state=WILD)['available_actions']==['wait']


@pytest.mark.parametrize('partial',['Go!','Go! NIDO'])
def test_readable_level30_with_known_partial_go_page_waits(partial):
    s=Session();s.play();s.call(woke());s.call(rage())
    t=text_at((1,0,'SNORLAX'),(5,1,'30'),(1,14,partial),window=True)
    assert s.call(t,battle_state=WILD)['available_actions']==['wait']
    t=text_at((1,0,'SNORLAX'),(5,1,'30'),(1,14,'Go! NIDOKING!'),window=True)
    assert s.call(t,battle_state=WILD)['poke_flute_handoff']


@pytest.mark.parametrize('t', [text_at((1, 14, 'Played the POKé'), (1, 16, "catchy tune!")),
    text_at((1, 14, 'Use item on which'), (1, 16, 'POKéMON?')),
    text_at((1, 14, 'KEVIN found'), (1, 16, 'POKé FLUTE!')),
    text_at((1, 14, 'UNKNOWN')), text_at((1, 14, 'SNORLAX woke up!!')),
    text_at((1, 14, 'All right!'), (1, 16, 'SNORLAX was caught!'))])
def test_unknown_wrong_page_party_selection_or_fake_caught_reviews(t):
    s = Session(); s.use()
    assert s.call(t)['phase'] == 'campaign_review'


@pytest.mark.parametrize('marker,x,y', [('▶', 0, 0), ('▷', 5, 8), ('▼', 17, 16)])
def test_dialogue_marker_conflicts_never_press_a(marker, x, y):
    s = Session(); s.use(); t = played(prompt=False); t['cells'][y][x] = marker
    assert s.call(t)['phase'] == 'campaign_review'


def test_partial_prompt_and_unknown_choices_do_not_confirm():
    s = Session(); s.use(); t = played(partial='KEVIN played'); t['cells'][16][18] = '▼'
    assert s.call(t)['review_reason'] == 'poke_flute_partial_dialogue_has_prompt'
    s = Session(); s.use(); t = played(); t['cells'][0][0:3] = list('YES')
    assert s.call(t)['review_reason'] == 'poke_flute_dialogue_unknown_choices'


@pytest.mark.parametrize('field,value', [('raw', 2), ('raw', True), ('active', None), ('kind', 'trainer'),
    ('opponent_species', 'PIDGEY'), ('wild_opponent_species', 143), ('level', 29), ('enemy_level', True)])
def test_wrong_or_unknown_battle_never_handoffs(field, value):
    s = Session(); s.play(); b = deepcopy(WILD); b[field] = value
    result = s.call(wild_hud(), battle_state=b)
    assert result['phase'] == 'campaign_review' and not result.get('poke_flute_handoff')


@pytest.mark.parametrize('level', ['29', '31', '130', '30X', 'TRUE'])
def test_wrong_visible_level_does_not_borrow_static_source30(level):
    s = Session(); s.play()
    assert s.call(wild_hud(level), battle_state=WILD)['phase'] == 'campaign_review'


def test_battle_requires_use_and_prompt_and_visible_level():
    assert Session().call(wild_hud(), battle_state=WILD)['review_reason'] == 'poke_flute_battle_before_verified_use'
    s = Session(); s.use()
    assert s.call(wild_hud(), battle_state=WILD)['review_reason'] == 'poke_flute_battle_before_verified_use'
    s = Session(); s.play()
    assert s.call(wild_hud(''), battle_state=WILD)['available_actions'] == ['wait']
    assert not s.c.handed_off
    assert s.call(wild_hud(command=True), battle_state=WILD)['poke_flute_handoff']


def test_invalid_party_only_waits_in_proven_battle_transition_then_handoffs_when_valid():
    s = Session(); s.play(); s.p['party_read_valid'] = False
    result = s.call(wild_hud(), battle_state=WILD)
    assert result['available_actions'] == ['wait'] and not result.get('poke_flute_handoff')
    s.p['party_read_valid'] = True
    assert s.call(wild_hud(), battle_state=WILD)['poke_flute_handoff']


@pytest.mark.parametrize('change', ['flute_consumed', 'other_bag', 'party_hp', 'party_move', 'reorder'])
def test_fingerprint_changes_cannot_be_hidden_by_partial_or_handoff(change):
    s = Session(); s.play()
    if change == 'flute_consumed': s.p['inventory'].pop()
    elif change == 'other_bag': s.p['inventory'][0]['quantity'] -= 1
    elif change == 'party_hp': s.p['party'][0]['hp'] -= 1
    elif change == 'party_move': s.p['party'][0]['moves'][1] = 91
    else: s.p['party'].reverse()
    assert s.call(wild_hud(), battle_state=WILD)['phase'] == 'campaign_review'


def test_partial_or_unaligned_real_decoder_cannot_handoff():
    s = Session(); s.play(); t = wild_hud(); t['alignment_verified'] = False
    assert s.call(t, battle_state=WILD)['phase'] == 'campaign_review'


def test_handoff_is_latched_without_any_further_field_or_battle_operations():
    s = Session(); s.play(); result = s.call(wild_hud(), battle_state=WILD)
    assert result['available_actions'] == ['wait'] and result['poke_flute_handoff']
    # 已交棒後不再讀新packet，不回START／A／方向；原收據只描述交棒那一幀。
    for _ in range(5):
        assert s.c.context(None, None, location=None, battle_state=None,
                           frame=-1, now=float('nan'), intent={'kind': 'catch'}) == result


@pytest.mark.parametrize('bad', [True, -1, float('nan'), float('inf'), '1'])
def test_bad_clock_stops(bad):
    assert Session().call(now=bad, overworld_ready=True)['review_reason'] == 'poke_flute_clock_or_frame_invalid'


def test_time_calls_wait_budget_intent_and_errors_latch():
    s = Session(max_calls=1); s.call(overworld_ready=True)
    failed = s.call(start())
    assert failed['review_reason'] == 'poke_flute_transaction_budget_exhausted'
    assert s.call(played()) == failed
    s = Session(); s.call(overworld_ready=True)
    assert s.call(start(), now=61)['review_reason'] == 'poke_flute_transaction_budget_exhausted'
    s = Session(max_waits=1); s.call(overworld_ready=True); s.call()
    assert s.call()['review_reason'] == 'poke_flute_wait_budget_exhausted'
    s = Session(); s.call(overworld_ready=True); s.c.intent['item'] = 4
    assert s.call(start())['review_reason'] == 'poke_flute_intent_changed'
    s = Session(); s.call(overworld_ready=True)
    assert s.call(start(), intent={'kind': 'catch'})['review_reason'] == 'poke_flute_intent_changed'


def test_context_never_mutates_any_provided_packet():
    s = Session(); t = text_at(); loc, b = deepcopy(STANCE), deepcopy(NONE)
    before = deepcopy((t, s.p, loc, b))
    result = s.call(t, location=loc, battle_state=b, overworld_ready=True)
    assert result['available_actions'] == ['start', 'wait']
    assert (t, s.p, loc, b) == before


def test_start_with_unknown_dialogue_behind_menu_never_confirms():
    s = Session(); s.call(overworld_ready=True); t = start()
    t['cells'][16][0:6] = list('Delete')
    assert s.call(t)['review_reason'] == 'poke_flute_start_background_dialogue_conflict'


@pytest.mark.parametrize('label', ['POKé FLUTE?', 'POKé FLUTE.', 'POKE FLUTE', 'POKé FLUTE!!'])
def test_flute_bag_label_must_be_source_exact_not_only_normalized(label):
    s = Session(progress([73])); s.to_bag(); t = bag(s.p)
    t['cells'][4][6:19] = list(label.upper().ljust(13))
    assert s.call(t)['phase'] == 'campaign_review'


@pytest.mark.parametrize('x,y,value', [(7, 5, 'WHY'), (17, 8, '?'), (14, 7, '× 3')])
def test_bag_extra_or_wrong_quantity_content_never_passes(x, y, value):
    s = Session(); s.to_bag(); t = bag(s.p)
    t['cells'][y][x:x + len(value)] = list(value)
    assert s.call(t)['phase'] == 'campaign_review'


def test_unknown_yes_or_party_content_outside_use_box_is_not_hidden():
    s = Session(); s.select(); t = use_screen(s.selected)
    t['cells'][0][0:3] = list('YES')
    assert s.call(t)['review_reason'] == 'poke_flute_use_unknown_content'


def test_real_decoder_unknown_scanline_proof_cannot_be_bypassed_after_use():
    s = Session(); s.use(); t = played()
    t.update(read_valid=False, alignment_verified=False, read_error='visible_scanline_incomplete')
    assert s.call(t)['review_reason'] == 'poke_flute_decoder_proof_required'


def test_unknown_battle_ui_or_visible_wrong_species_never_handoffs():
    s = Session(); s.play(); t = wild_hud()
    t['cells'][0][1:8] = list('PIDGEY ')
    assert s.call(t, battle_state=WILD)['phase'] == 'campaign_review'
    s = Session(); s.play(); t = wild_hud(); t['cells'][13][15:19] = list('TOSS')
    assert s.call(t, battle_state=WILD)['phase'] == 'campaign_review'


def test_unknown_party_battle_wait_still_obeys_time_budget_and_frame_guard():
    s = Session(); s.play(); s.p['party_read_valid'] = False
    assert s.call(wild_hud(), battle_state=WILD)['available_actions'] == ['wait']
    previous = s.frame
    s.p['party_read_valid'] = True
    assert s.call(wild_hud(), frame=previous, battle_state=WILD)['review_reason'] == 'poke_flute_same_frame_changed_packet'
    s = Session(); s.play(); s.p['party_read_valid'] = False
    assert s.call(wild_hud(), battle_state=WILD, now=61)['review_reason'] == 'poke_flute_transaction_budget_exhausted'


def test_backwards_clock_or_frame_and_rage_reordering_are_not_partial_waits():
    s = Session(); s.call(overworld_ready=True)
    assert s.call(start(), frame=39)['review_reason'] == 'poke_flute_clock_or_frame_invalid'
    s = Session(); s.call(overworld_ready=True)
    assert s.call(start(), now=0)['review_reason'] == 'poke_flute_clock_or_frame_invalid'
    s = Session(); s.play(); s.call(rage())
    assert s.call(woke())['review_reason'] == 'poke_flute_woke_after_final_rage'


@pytest.mark.parametrize('unknown', ['Delete', 'SNORLAX was caught!', 'Choose a POKéMON.'])
def test_visible_hud_alone_cannot_hide_unknown_battle_dialogue(unknown):
    s = Session(); s.play(); t = text_at((1, 0, 'SNORLAX'), (5, 1, '30'), (1, 14, unknown), window=True)
    assert s.call(t, battle_state=WILD)['phase'] == 'campaign_review'


def test_battle_hud_partial_or_blank_only_waits_and_known_go_page_can_handoff():
    s = Session(); s.play()
    t = text_at((1, 0, 'SNORLAX'), (5, 1, '30'), window=True)
    assert s.call(t, battle_state=WILD)['available_actions'] == ['wait']
    assert not s.c.handed_off
    t = text_at((1, 0, 'SNORLAX'), (5, 1, '30'), (1, 14, 'Wild SNORLAX'), window=True)
    assert s.call(t, battle_state=WILD)['available_actions'] == ['wait']
    t = text_at((1, 0, 'SNORLAX'), (5, 1, '30'), (1, 14, 'Go! NIDOKING!'), window=True)
    assert s.call(t, battle_state=WILD)['poke_flute_handoff']


@pytest.mark.parametrize('cursor', [2, 4, 8, 10, 12, 14])
@pytest.mark.parametrize('transition', ['blank', 'partial', 'blank_then_partial'])
def test_pending_start_direction_survives_transition_until_cursor_really_moves(cursor, transition):
    s = Session(); s.call(overworld_ready=True)
    old = start(cursor)
    assert s.call(old)['available_actions'] == (['down', 'wait'] if cursor < 6 else ['up', 'wait'])
    if 'blank' in transition:
        assert s.call(text_at())['available_actions'] == ['wait']
    if 'partial' in transition:
        assert s.call(text_at((12, 2, 'POKéD'), window=True))['available_actions'] == ['wait']
    result = s.call(old)
    assert result['available_actions'] == ['wait']
    assert result['poke_flute_tactic'] == 'await_start_cursor_move_without_resend'
    expected = cursor + (2 if cursor < 6 else -2)
    result = s.call(start(expected))
    assert result['available_actions'] == (['a', 'wait'] if expected == 6 else
                                            ['down', 'wait'] if expected < 6 else ['up', 'wait'])


@pytest.mark.parametrize('old,new', [(2, 6), (4, 2), (8, 10), (14, 6)])
def test_start_pending_rejects_jump_or_opposite_after_blank(old, new):
    s = Session(); s.call(overworld_ready=True); s.call(start(old)); s.call(text_at())
    assert s.call(start(new))['review_reason'] == 'poke_flute_start_cursor_moved_other_than_requested_step'


def test_start_pending_old_page_keeps_wait_budget_instead_of_resending():
    s = Session(max_waits=3); s.call(overworld_ready=True); s.call(start(2))
    for t in (text_at(), start(2), text_at()):
        assert s.call(t)['available_actions'] == ['wait']
    assert s.call(start(2))['review_reason'] == 'poke_flute_wait_budget_exhausted'


def test_bag_scroll_and_a_pending_survive_blank_without_resend():
    s = Session(progress([4, 73, 42, 49])); s.to_bag()
    old = bag(s.p, cursor=0)
    assert s.call(old)['available_actions'] == ['down', 'wait']
    assert s.call(text_at())['available_actions'] == ['wait']
    assert s.call(old)['available_actions'] == ['wait']
    selected = bag(s.p, cursor=1)
    assert s.call(selected)['available_actions'] == ['a', 'wait']
    assert s.call(text_at())['available_actions'] == ['wait']
    assert s.call(selected)['available_actions'] == ['wait']
    u = use_screen(selected)
    assert s.call(u)['available_actions'] == ['a', 'wait']
    assert s.call(text_at())['available_actions'] == ['wait']
    assert s.call(u)['available_actions'] == ['wait']


@pytest.mark.parametrize('word', ['YES', 'NO', 'Delete', 'UNKNOWN', 'X', '30'])
def test_initial_readable_unknown_text_cannot_become_trusted_background(word):
    t = text_at((0, 0, word))
    result = Session().call(t, overworld_ready=True)
    assert result['review_reason'] == 'poke_flute_initial_readable_text_not_verified'
    assert result['available_actions'] == ['wait']


@pytest.mark.parametrize('x,y,word', [(0, 0, 'YES'), (0, 1, 'NO'), (0, 4, 'Delete'),
    (0, 11, 'WHY'), (17, 0, 'YES'), (5, 2, 'YES'), (4, 4, 'X'), (0, 15, 'Delete')])
def test_bag_outside_content_is_validated_before_flute_selection_and_use_baseline(x, y, word):
    s = Session(progress([73])); s.to_bag(); t = bag(s.p)
    t['cells'][y][x:x + len(word)] = list(word)
    result = s.call(t)
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']
    assert s.c.selected_bag is None and not s.c.used
    # 原反例會把受污染bag存成selected_bag，接著又A選USE；現在錯誤鎖存。
    assert s.call(use_screen(t))['available_actions'] == ['wait']
    assert not s.c.used


@pytest.mark.parametrize('x,y,word', [(0, 0, 'YES'), (0, 1, 'NO'), (0, 3, 'Delete'),
    (0, 11, 'UNKNOWN'), (10, 0, 'X'), (10, 16, 'NO'), (19, 16, 'X')])
def test_start_content_in_background_or_border_never_moves_or_confirms(x, y, word):
    s = Session(); s.call(overworld_ready=True); t = start()
    t['cells'][y][x:x + len(word)] = list(word)
    result = s.call(t)
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']


@pytest.mark.parametrize('word', ['YES', 'NO', 'Delete', 'UNKNOWN'])
def test_use_unknown_upper_content_cannot_be_hidden_by_verified_flute(word):
    s = Session(progress([73])); s.select(); t = use_screen(s.selected)
    t['cells'][0][0:len(word)] = list(word)
    result = s.call(t)
    assert result['phase'] == 'campaign_review' and not s.c.used


@pytest.mark.parametrize('page', ['partial', 'played', 'woke', 'rage', 'blank'])
@pytest.mark.parametrize('word', ['YES', 'NO', 'Delete', 'UNKNOWN'])
def test_dialogue_upper_unknown_text_is_never_hidden_by_known_lower_prefix(page, word):
    s = Session()
    if page in ('partial', 'played', 'blank'):
        s.use()
    else:
        s.play()
    t = {'partial': lambda: played(partial='KEVIN played'), 'played': played,
         'woke': woke, 'rage': rage, 'blank': text_at}[page]()
    t['cells'][0][0:len(word)] = list(word)
    result = s.call(t)
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']


def test_source_preserved_background_symbols_are_not_replaced_by_new_menu_baseline():
    s = Session(progress([73])); world = text_at((0, 0, '()'))
    assert s.call(world, overworld_ready=True)['available_actions'] == ['start', 'wait']
    st = start(); st['cells'][0][0:2] = list('()')
    assert s.call(st)['available_actions'] == ['a', 'wait']
    selected = bag(s.p); selected['cells'][0][0:2] = list('()')
    assert s.call(selected)['available_actions'] == ['a', 'wait']
    assert s.call(use_screen(selected))['available_actions'] == ['a', 'wait']
    p = played(); p['cells'][0][0:2] = list('()')
    assert s.call(p)['available_actions'] == ['a', 'wait']
    assert s.call(text_at())['available_actions'] == ['wait']
