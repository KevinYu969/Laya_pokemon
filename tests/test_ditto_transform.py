"""百變怪變身的純getter與既有戰鬥guard回歸；不讀ROM／存檔或操作遊戲。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from laya_pokemon import ditto_transform as dt
from laya_pokemon.battle import read_battle_state, battle_context
from laya_pokemon.team_strategy import reference
from tests.test_battle import text_at


ROSTER = [154, 102, 35, 7, 132]


def memory():
    data = {0xD057: 1, 0xD05A: 0, 0xD05D: 0, 0xD069: 8, 0xD06D: 0, 0xCFD8: 76,
            0xCFE5: 35, 0xCFEA: 0, 0xCFEB: 2, 0xD059: 0, 0xD163: 5}
    data.update({0xCFDA + i: byte for i, byte in enumerate(dt._DITTO_NICK)})
    data.update({0xD164 + i: number for i, number in enumerate(ROSTER + [255])})
    return data


def read(data=None, *, frame=10, observation_frame=10, constants=None, ref=None):
    return dt.read_ditto_transform(SimpleNamespace(memory=memory() if data is None else data, frame_count=frame),
        observation_frame=observation_frame, constants=dt.SDK_ANCHORS if constants is None else constants,
        reference_data=reference() if ref is None else ref)


def party():
    return [{'species': s, 'level': 33, 'hp': 102, 'max_hp': 102,
             'moves': [64, 45, 43, 31], 'pp': [34, 40, 30, 20]} for s in ROSTER]


def command(*, hp='102/102', real=True):
    text = text_at((1, 0, 'DITTO'), (5, 1, '26'), (10, 7, 'FEAROW'), (15, 8, '33'),
                   (10, 10, hp), (10, 14, 'FIGHT'), (10, 16, 'ITEM'), (16, 16, 'RUN'), (9, 14, '▶'))
    if real:
        text.update(profile='gen1-visible-tile-text-candidates-v1-unvalidated', read_valid=True,
                    alignment_verified=True, read_error=None, window_visible=True)
    return text


def signal_state(data=None):
    return read_battle_state(SimpleNamespace(memory=memory() if data is None else data, frame_count=10))


def test_positive_proof_preserves_original_effective_types_and_raw_bytes():
    data = memory()
    before = deepcopy(data)
    signal = read(data)
    assert signal['read_valid'] and signal['original_species'] == 76 and signal['original_name'] == 'DITTO'
    assert signal['effective_species'] == 35 and signal['effective_name'] == 'FEAROW'
    assert signal['effective_type_bytes'] == [0, 2] and signal['effective_types'] == ['NORMAL', 'FLYING']
    assert signal['original_nickname_bytes'] == list(dt._DITTO_NICK)
    assert signal['raw_flags'] == {'is_in_battle': 1, 'battle_type': 0, 'enemy_battle_status3': 8, 'cur_opponent': 0}
    assert signal['party_species'] == ROSTER and data == before
    assert dt.verified_effective_enemy(signal, visible_enemy='DITTO', ram_enemy='FEAROW',
        party=party(), observation_frame=10, reference_data=reference()) == 'FEAROW'


@pytest.mark.parametrize('value', [0, 76])
def test_current_opponent_is_recorded_without_requiring_it_to_stay_species(value):
    data = memory(); data[0xD059] = value
    assert read(data)['read_valid']


@pytest.mark.parametrize('address,value', [
    (0xD057, 0), (0xD057, 2), (0xD05A, 1), (0xD069, 0), (0xD069, 0x88),
    (0xCFD8, 35), (0xCFE5, 0), (0xCFE5, 255), (0xCFEA, 22), (0xCFEB, 0),
    (0xCFDA, 0), (0xCFDF, 0), (0xD163, 0), (0xD163, 7),
    (0xD169, 0), (0xD166, 7), (0xD057, True), (0xD069, None)])
def test_unverified_raw_fields_never_get_valid_partial_signal(address, value):
    data = memory(); data[address] = value
    signal = read(data)
    assert signal['read_valid'] is False and 'effective_species' not in signal


@pytest.mark.parametrize('frame,observed', [(9, 10), (11, 10), (True, 1), (10, None), (10, -1)])
def test_unknown_or_wrong_observation_frame_fails_closed(frame, observed):
    assert not read(frame=frame, observation_frame=observed)['read_valid']


@pytest.mark.parametrize('change', ['sdk_missing', 'sdk_moved', 'commit', 'species', 'duplicate', 'types'])
def test_fixed_reference_and_sdk_anchors_are_required(change):
    sdk, ref = deepcopy(dt.SDK_ANCHORS), deepcopy(reference())
    if change == 'sdk_missing': del sdk['CURRENT_OPPONENT_ADDRESS']
    elif change == 'sdk_moved': sdk['BATTLE_TYPE_ADDRESS'] += 1
    elif change == 'commit': ref['source_commit'] = 'unverified'
    elif change == 'species': del ref['species']['FEAROW']
    elif change == 'duplicate': ref['species']['ALIAS'] = deepcopy(ref['species']['FEAROW'])
    else: ref['species']['FEAROW']['types'] = ['UNKNOWN']
    assert not read(constants=sdk, ref=ref)['read_valid']


def test_double_read_changes_and_missing_bytes_are_unknown():
    class Changing(dict):
        calls = 0
        def __getitem__(self, address):
            if address == 0xD069:
                self.calls += 1
                return 8 if self.calls == 1 else 0
            return super().__getitem__(address)
    assert read(Changing(memory()))['unknown_reason'] == 'bytes_changed_during_read'
    data = memory(); del data[0xCFDA]
    assert not read(data)['read_valid']


@pytest.mark.parametrize('end', [9, 11, None, True])
def test_frame_change_during_reads_fails_closed(end):
    class ChangingFrame:
        memory = memory()
        count = 0
        @property
        def frame_count(self):
            self.count += 1
            return 10 if self.count == 1 else end
    result = dt.read_ditto_transform(ChangingFrame(), observation_frame=10,
                                   constants=dt.SDK_ANCHORS, reference_data=reference())
    assert result['unknown_reason'] == 'frame_changed_during_read'


def test_monotype_effective_target_requires_duplicate_type_bytes():
    data = memory(); data[0xCFE5] = 132; data[0xCFEB] = 0
    assert read(data)['effective_name'] == 'SNORLAX'
    data[0xCFEB] = 2
    assert not read(data)['read_valid']


@pytest.mark.parametrize('change', ['frame', 'party_order', 'missing_target', 'spoof_read_valid', 'types', 'flags', 'original', 'name'])
def test_context_revalidates_full_certificate_and_same_frame_party(change):
    signal, members, frame = read(), party(), 10
    if change == 'frame': frame = 11
    elif change == 'party_order': members.reverse()
    elif change == 'missing_target': members.pop(2)
    elif change == 'spoof_read_valid': signal = {'read_valid': True}
    elif change == 'types': signal['effective_type_bytes'] = [0, 0]
    elif change == 'flags': signal['raw_flags']['enemy_battle_status3'] = 0
    elif change == 'original': signal['original_species'] = 35
    else: signal['effective_name'] = 'DITTO'
    assert dt.verified_effective_enemy(signal, visible_enemy='DITTO', ram_enemy='FEAROW',
        party=members, observation_frame=frame, reference_data=reference()) is None


def test_battle_only_resolves_verified_ditto_mismatch_and_keeps_existing_attack_policy():
    state = signal_state()
    assert state['opponent_species'] == 'FEAROW' and state['ditto_transform']['original_name'] == 'DITTO'
    data, text, members = deepcopy(state), command(), party()
    result = battle_context(text, state, members)
    assert result['phase'] == 'battle_menu' and result['enemy_species'] == 'FEAROW'
    assert result['battle_tactic'] == 'damage' and result['objective'] == 'Confirm the current selection.'
    assert state == data and text == command() and members == party()


def test_transformed_target_keeps_existing_low_hp_retreat():
    result = battle_context(command(hp='40/102'), signal_state(), party())
    assert result['battle_tactic'] == 'retreat' and result['enemy_species'] == 'FEAROW'


@pytest.mark.parametrize('change', ['not_transformed', 'missing_signal', 'wrong_species', 'not_wild', 'unknown_frame',
                                   'party_changed', 'unaligned', 'unknown_profile', 'other_visible_name'])
def test_all_other_mismatches_still_review(change):
    state, text, members = signal_state(), command(), party()
    if change == 'not_transformed': state['ditto_transform'] = read({**memory(), 0xD069: 0})
    elif change == 'missing_signal': state.pop('ditto_transform')
    elif change == 'wrong_species': state['opponent_species'] = 'PIDGEY'
    elif change == 'not_wild': state.update(raw=2, kind='trainer')
    elif change == 'unknown_frame': state.pop('observation_frame')
    elif change == 'party_changed': members[2]['species'] = 36
    elif change == 'unaligned': text.update(alignment_verified=False)
    elif change == 'unknown_profile': text['profile'] = 'unknown'
    else: text['cells'][0][1:6] = list('PIDGY')
    result = battle_context(text, state, members)
    if change == 'other_visible_name':
        # 使用另一個可辨識物種，不能靠變身訊號豁免非DITTO。
        text['cells'][0][1:7] = list('PIDGEY')
        result = battle_context(text, state, members)
    assert result['review_reason'] == 'visible_enemy_and_wild_opponent_signal_disagree'


def test_transform_exception_requires_real_decoder_profile_even_with_valid_signal():
    result = battle_context(command(real=False), signal_state(), party())
    assert result['review_reason'] == 'visible_enemy_and_wild_opponent_signal_disagree'


def test_validator_rejects_boolean_frame_even_when_equal_to_integer_one():
    signal = read(frame=1, observation_frame=1)
    assert signal['read_valid']
    signal['observation_frame'] = True
    assert dt.verified_effective_enemy(signal, visible_enemy='DITTO', ram_enemy='FEAROW',
        party=party(), observation_frame=1, reference_data=reference()) is None


def ko_memory():
    data = memory()
    data.update({0xD069: 0, 0xCFE6: 0, 0xCFE7: 0, 0xCFE9: 2})
    return data


def ko_read(data=None, *, observation_frame=10, frame=10, constants=None, ref=None):
    return dt.read_ditto_ko_transition(SimpleNamespace(memory=ko_memory() if data is None else data, frame_count=frame),
        observation_frame=observation_frame, constants=dt.SDK_ANCHORS if constants is None else constants,
        reference_data=reference() if ref is None else ref)


def ko_text(*lower, header=True):
    entries = [(10, 7, 'VENUSAUR'), (15, 8, '33'), (11, 10, '102/102')]
    if header:
        entries += [(1, 0, 'DITTO'), (5, 1, 'SLP')]
    text = text_at(*entries, *lower)
    text.update(profile='gen1-visible-tile-text-candidates-v1-unvalidated', read_valid=True,
                alignment_verified=True, read_error=None, window_visible=True)
    return text


def test_ko_getter_is_distinct_zero_hp_cleared_flag_proof_and_preserves_sleep():
    data = ko_memory(); before = deepcopy(data)
    signal = ko_read(data)
    assert signal['read_valid'] and signal['profile'] == dt.KO_PROFILE
    assert signal['stage'] == 'enemy_zero_hp_faint_transition' and signal['enemy_hp'] == 0
    assert signal['enemy_status'] == 2 and signal['raw_flags']['enemy_battle_status3'] == 0
    assert not read(data)['read_valid'] and data == before
    assert dt.verified_ko_transition(signal, ram_enemy='FEAROW', party=party(), observation_frame=10,
                                     reference_data=reference()) == signal


@pytest.mark.parametrize('address,value', [(0xCFE7,1),(0xCFE6,1),(0xD069,8),(0xD057,2),(0xD05A,1),
                                         (0xCFD8,35),(0xCFDA,0),(0xCFEB,0),(0xD166,7),(0xCFE9,255)])
def test_ko_getter_rejects_positive_hp_flags_identity_types_party_and_status(address, value):
    data = ko_memory(); data[address] = value
    assert ko_read(data)['read_valid'] is False


def test_ko_getter_rejects_unknown_reference_sdk_frame_and_torn_reads():
    ref = deepcopy(reference()); ref['source_commit'] = 'unknown'
    assert not ko_read(ref=ref)['read_valid']
    assert not ko_read(constants={})['read_valid']
    assert not ko_read(frame=11)['read_valid']
    assert not ko_read(observation_frame=True, frame=True)['read_valid']
    class Torn(dict):
        calls = 0
        def __getitem__(self, address):
            if address == 0xCFE7:
                self.calls += 1
                return 0 if self.calls == 1 else 1
            return super().__getitem__(address)
    assert ko_read(Torn(ko_memory()))['unknown_reason'] == 'bytes_changed_during_read'
    class MovingFrame:
        memory = ko_memory()
        calls = 0
        @property
        def frame_count(self):
            self.calls += 1
            return 10 if self.calls == 1 else 11
    assert not dt.read_ditto_ko_transition(MovingFrame(), observation_frame=10, constants=dt.SDK_ANCHORS,
                                          reference_data=reference())['read_valid']


def test_real_ko_old_headbutt_page_waits_never_attacks_or_claims_victory():
    members = party(); members[0]['moves'] = [29,133,156,0]
    text = ko_text((1,14,'VENUSAUR'),(1,16,'used HEADBUTT!'))
    state = signal_state(ko_memory())
    result = battle_context(text, state, members)
    assert result['phase'] == 'battle_animation' and result['available_actions'] == ['wait']
    assert state['victory_confirmed'] is None and 'enemy_species' not in result and 'chosen_move' not in result


def test_actual_snorlax_copied_case_waits_then_only_advances_full_native_receipts():
    data = ko_memory()
    roster = [132,7,102,154,35]
    data.update({0xCFE5:132,0xCFEB:0})
    data.update({0xD164+i: value for i,value in enumerate(roster+[255])})
    members = [{'species':s,'level':31,'hp':147,'max_hp':147,'moves':[29,133,156,0],
                'pp':[4,20,10,0]} for s in roster]
    state = signal_state(data)
    def text(*lower, header=False):
        entries = [(10,7,'SNORLAX'),(15,8,str(members[0]['level'])),(11,10,'147/147')]
        if header: entries += [(1,0,'DITTO'),(5,1,'SLP')]
        result = text_at(*entries,*lower)
        result.update(profile='gen1-visible-tile-text-candidates-v1-unvalidated',read_valid=True,
                      alignment_verified=True,read_error=None,window_visible=True)
        return result
    assert battle_context(text((1,14,'SNORLAX'),(1,16,'used HEADBUTT!'),header=True),state,members)['available_actions']==['wait']
    for lower in [((1,14,'Enemy DITTO'),(1,16,'fainted!')),
                  ((1,14,'SNORLAX gained'),(1,16,'123 EXP. Points!'))]:
        assert battle_context(text(*lower),state,members)['available_actions']==['a','wait']
    members[0]['level']=32
    assert battle_context(text((1,14,'SNORLAX grew'),(1,16,'to level 32!')),state,members)['available_actions']==['a','wait']
    data[0xCFE7]=1
    assert battle_context(text((1,14,'SNORLAX'),(1,16,'used HEADBUTT!'),header=True),
                          signal_state(data),members)['phase']=='strategy_review'


@pytest.mark.parametrize('lower', [((1,14,'Enemy DITTO'),(1,16,'fainted!')),
                                 ((1,14,'VENUSAUR gained'),(1,16,'123 EXP. Points!')),
                                 ((1,14,'VENUSAUR grew'),(1,16,'to level 33!'))])
def test_only_complete_original_fainted_lead_exp_or_matching_grew_can_advance(lower):
    result = battle_context(ko_text(*lower,header=False), signal_state(ko_memory()), party())
    assert result['phase'] == 'battle_dialogue' and result['available_actions'] == ['a','wait']
    assert 'victory_confirmed' not in result


@pytest.mark.parametrize('lower', [((1,14,'Enemy DITTO'),(1,16,'faint')),
                                 ((1,14,'VENUSAUR gained'),(1,16,'123 EXP. Poi')),
                                 ((1,14,'VENUSAUR grew'),(1,16,'to level 3'))])
def test_partial_fainted_exp_or_grew_only_waits(lower):
    result = battle_context(ko_text(*lower,header=False), signal_state(ko_memory()), party())
    assert result['phase'] == 'battle_animation' and result['available_actions'] == ['wait']


@pytest.mark.parametrize('change', ['unknown_attack','wrong_fainted','wrong_exp','wrong_grew','profile','alignment',
                                   'cursor','upper_pollution','frame','party','signal_frame_bool'])
def test_ko_unknown_or_contradictory_pages_review_without_a(change):
    text = ko_text((1,14,'Enemy DITTO'),(1,16,'fainted!'))
    state, members = signal_state(ko_memory()), party()
    if change == 'unknown_attack': text = ko_text((1,14,'VENUSAUR'),(1,16,'used EXPLOSION!'))
    elif change == 'wrong_fainted': text = ko_text((1,14,'Enemy FEAROW'),(1,16,'fainted!'))
    elif change == 'wrong_exp': text = ko_text((1,14,'SNORLAX gained'),(1,16,'123 EXP. Points!'))
    elif change == 'wrong_grew': text = ko_text((1,14,'VENUSAUR grew'),(1,16,'to level 34!'))
    elif change == 'profile': text.pop('profile')
    elif change == 'alignment': text['alignment_verified'] = False
    elif change == 'cursor': text['cells'][0][0] = '▶'
    elif change == 'upper_pollution': text['cells'][3][:6] = list('DELETE')
    elif change == 'frame': state['observation_frame'] = 11
    elif change == 'party': members.reverse()
    else: state['ditto_ko_transition']['observation_frame'] = True
    result = battle_context(text,state,members)
    assert result['phase'] == 'strategy_review' and result['available_actions'] == ['wait']

