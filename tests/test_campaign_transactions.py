"""正常交易橋接的邊界測試；禁止模擬器寫入或直接執行按鍵。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from laya_pokemon import campaign_transactions as tx
from tests.test_battle import text_at
from tests.test_gift_eevee import progress


class ReadOnlyMemory:
    def __init__(self):
        self.data = {0xC109: 8, 0xD5AE: 0}

    def __getitem__(self, address):
        return self.data[address]

    def __setitem__(self, address, value):
        raise AssertionError('交易橋接不得寫入遊戲記憶體')


@pytest.fixture(autouse=True)
def clean_registry():
    tx._CONTROLLERS.clear()
    tx._BINDINGS.clear()
    tx._TURNS.clear()
    tx._COMPLETED.clear()
    yield
    tx._CONTROLLERS.clear()
    tx._BINDINGS.clear()
    tx._TURNS.clear()
    tx._COMPLETED.clear()


def setup(mechanic='gift_eevee'):
    emulator = SimpleNamespace(memory=ReadOnlyMemory())
    state = {'phase': 'unclassified', 'location': {'map_id': 132, 'x': 5, 'y': 3},
             'battle_state': {'kind': 'none', 'active': False}, 'progress': progress()}
    step = {'id': 'gift', 'kind': 'interact', 'mechanic': mechanic,
            'map_id': 132, 'target': [5, 3]}
    plan = {'steps': [step, {'id': 'after'}]}
    return emulator, state, plan


def call(args, text=None, grid=None):
    return tx.context(*args, 'gift', text or text_at(), grid)


def test_only_explicit_supported_interactions_can_enter():
    args = setup()
    del args[2]['steps'][0]['mechanic']
    assert call(args) is None
    args[2]['steps'][0]['mechanic'] = 'unknown'
    assert call(args)[0]['review_reason'] == 'unsupported_explicit_transaction'


def test_requires_arrival_and_verified_nonbattle_before_start():
    args = setup()
    args[1]['location']['x'] = 4
    assert call(args) is None
    args[1]['location']['x'] = 5
    args[1]['battle_state']['kind'] = 'trainer'
    assert call(args)[0]['review_reason'] == 'transaction_nonbattle_signal_conflict'
    args[1]['battle_state']['kind'] = 'none'
    args[1]['battle_state']['active'] = True
    assert call(args)[0]['review_reason'] == 'transaction_nonbattle_signal_conflict'
    assert not tx._CONTROLLERS


def test_facing_only_suggested_with_verified_grid_and_never_executes():
    args = setup()
    args[0].memory.data[0xC109] = 4
    assert call(args)[0]['review_reason'] == 'gift_turn_requires_verified_overworld'
    assert call(args, grid={})[0]['available_actions'] == ['left', 'wait']
    assert not tx._CONTROLLERS


def test_gift_removal_flag_is_read_and_unknown_initial_screen_refused():
    args = setup()
    snapshot = deepcopy(args[1])
    args[0].memory.data[0xD5AE] = 0x20
    assert call(args, grid={})[0]['review_reason'] == 'eevee_gift_ball_visibility_unverified'
    assert args[1] == snapshot


def test_started_transaction_rejects_changed_location_or_intent():
    args = setup()
    assert call(args, grid={})[0]['available_actions'] == ['a', 'wait']
    args[1]['location']['x'] = 4
    assert call(args)[0]['review_reason'] == 'transaction_location_changed'
    args[1]['location']['x'] = 5
    args[2]['steps'][0]['mechanic'] = 'teach_bubblebeam'
    assert call(args)[0]['review_reason'] == 'transaction_intent_changed'


@pytest.mark.parametrize('mechanic,flag', [('gift_eevee', 'gift_eevee_complete'),
                                         ('teach_bubblebeam', 'tm_teaching_complete')])
def test_completion_only_advances_on_controller_verified_transaction(monkeypatch, mechanic, flag):
    args = setup(mechanic)

    class Fake:
        def __init__(self, *unused):
            pass

        def context(self, *unused, **kwargs):
            return {'phase': 'done', 'available_actions': ['wait'], flag: True}

    module = tx.gift_eevee if mechanic == 'gift_eevee' else tx.teach_bubblebeam
    name = 'EeveeGiftController' if mechanic == 'gift_eevee' else 'BubbleBeamController'
    monkeypatch.setattr(module, name, Fake)
    result, next_id = call(args, grid={})
    assert result['field_move_complete'] is True
    assert result['field_move_kind'] == mechanic
    assert next_id == 'after'


def test_real_incomplete_gift_never_advances_on_ball_inspection():
    result, next_id = call(setup(), grid={})
    assert next_id == 'gift'
    assert not result.get('field_move_complete')


@pytest.mark.parametrize('started', ['turn', 'inspect'])
def test_removing_mechanic_or_step_cannot_fall_back_to_generic_a(started):
    args = setup()
    if started == 'turn':
        args[0].memory.data[0xC109] = 4
    assert call(args, grid={})[0]['available_actions'] == (['left', 'wait'] if started == 'turn' else ['a', 'wait'])
    step = args[2]['steps'][0]
    del step['mechanic']
    assert tx.applies('gift', step)
    assert call(args)[0]['review_reason'] == 'transaction_intent_changed'
    args[2]['steps'].pop(0)
    assert tx.applies('gift', None)
    assert call(args)[0]['review_reason'] == 'transaction_intent_changed'


@pytest.mark.parametrize('phase,text', [('strategy_review', text_at()),
                                      ('unclassified', text_at((1, 14, 'UNKNOWN MESSAGE'))),
                                      ('unclassified', text_at((0, 0, '▶')))])
def test_turn_cannot_override_existing_review_or_unknown_ui(phase, text):
    args = setup()
    args[0].memory.data[0xC109] = 4
    args[1]['phase'] = phase
    assert call(args, text=text, grid={})[0]['phase'] == 'campaign_review'
    assert not tx._CONTROLLERS and not tx._BINDINGS


def test_turn_is_bounded_when_direction_never_changes():
    args = setup()
    args[0].memory.data[0xC109] = 4
    for _ in range(3):
        assert call(args, grid={})[0]['available_actions'] == ['left', 'wait']
    assert call(args, grid={})[0]['review_reason'] == 'gift_turn_budget_exhausted'


def test_new_step_id_cannot_restart_unfinished_transaction():
    args = setup()
    call(args, grid={})
    args[2]['steps'][0]['id'] = 'another-gift'
    result, _ = tx.context(*args, 'another-gift', text_at(), {})
    assert result['review_reason'] == 'unfinished_transaction_step_changed'
    assert set(tx._CONTROLLERS) == {'gift'}


@pytest.mark.parametrize('reason,allowed', [('learning_case_not_verified',True),
                                         ('forget_move_menu_requires_live_calibration',True),
                                         ('natural_learning_progress_party_mismatch',False),
                                         ('battle_loss_requires_review',False),
                                         ('unknown',False)])
def test_only_started_tm_can_receive_specific_generic_learning_guards(monkeypatch, reason, allowed):
    args = setup('teach_bubblebeam')

    class Fake:
        stage = 'party_confirm'
        def context(self,*unused,**kwargs):
            return {'phase':'tm_teaching_menu','available_actions':['wait']}

    monkeypatch.setattr(tx.teach_bubblebeam,'BubbleBeamController',Fake)
    tx._CONTROLLERS['gift']=Fake()
    tx._BINDINGS['gift']=('teach_bubblebeam',132,(5,3))
    args[1].update(phase='strategy_review',review_reason=reason)
    result,_=call(args,grid={})
    if allowed:
        assert result['phase']=='tm_teaching_menu'
        assert result['delegated_generic_learning_guard']==reason
    else:
        assert result['phase']=='campaign_review'


def test_unstarted_tm_and_gift_keep_all_generic_reviews():
    for mechanic in ('teach_bubblebeam','gift_eevee'):
        args=setup(mechanic)
        args[1].update(phase='strategy_review',review_reason='learning_case_not_verified')
        assert call(args,grid={})[0]['phase']=='campaign_review'


def test_waypoint_arrival_never_sends_generic_a_before_transaction_adapter():
    from laya_pokemon.campaign_route import waypoint
    for mechanic in ('gift_eevee','teach_bubblebeam'):
        args=setup(mechanic)
        step=args[2]['steps'][0]
        before={'id':'before','kind':'move','map_id':132,'target':[5,3]}
        plan={'steps':[before,step]}
        args[1]['progress']['story_event_bits']={}
        result,next_id=waypoint(None,args[1],plan,'before',['up'])
        assert next_id=='gift'
        assert result['available_actions']==['wait']
        assert result['goal']=='field_transaction_pending'


@pytest.mark.parametrize('text',[text_at((13,2,'POKéDEX'),(13,6,'ITEM')),
                               text_at((1,14,'NIDORINO learned')),
                               text_at((0,0,'▶'))])
def test_valid_background_grid_is_not_overworld_while_window_ui_visible(text):
    assert not tx.ui_overworld_ready(text,{})
    assert tx.ui_overworld_ready(text_at(),{})


def arrow_setup():
    from laya_pokemon.arrow_floor import ArrowFloorController
    from tests.test_arrow_floor import observation
    args=setup('arrow_floor')
    args[1]['location']={'map_id':201,'x':13,'y':11}
    args[1]['frame']=100
    args[0].frame_count=100
    args[0].memory.data.update({0xCD38:0,0xCD6B:0,0xCFC5:0,0xD736:0})
    args[2]['steps'][0].update(map_id=201,target=[13,11],trigger=[12,11])
    model=ArrowFloorController(201,(12,11))
    return args,model,observation


def test_arrow_adapter_reads_real_getters_and_allows_only_verified_moving_location():
    args,model,observation=arrow_setup()
    _,grid=observation(model,frame=100)
    result,next_id=call(args,grid=grid)
    assert result['available_actions']==['left','wait'] and next_id=='gift'
    assert result['arrow_observed_movement']['read_valid'] is True
    for frame in (132,164):
        location,grid=observation(model,model.hop['expected_landing'],frame)
        args[1].update(location=location,frame=frame);args[0].frame_count=frame
        result,next_id=call(args,grid=grid)
        assert result['available_actions']==['wait']
        assert bool(result.get('field_move_complete'))==(frame==164)
    assert next_id=='after' and 'gift' in tx._COMPLETED


def test_arrow_adapter_cannot_promote_stale_frame_to_verified_movement():
    args,model,observation=arrow_setup()
    args[0].frame_count=101
    _,grid=observation(model,frame=100)
    result,_=call(args,grid=grid)
    assert result['review_reason']=='arrow_movement_read_not_verified'
    assert result['available_actions']==['wait']


def test_arrow_adapter_rejects_unreviewed_trigger_or_wrong_explicit_stance():
    args,model,observation=arrow_setup()
    args[2]['steps'][0]['trigger']=[0,0]
    assert call(args)[0]['review_reason']=='arrow_explicit_trigger_unverified'
    args[2]['steps'][0]['trigger']=[12,11]
    args[2]['steps'][0]['target']=[12,11]
    assert call(args)[0]['review_reason']=='arrow_explicit_stance_unverified'


def decoded_observation(*, mode='aligned'):
    from laya_pokemon.observation import read_visible_text
    from tests.test_observation import emulator, DECODING
    game = emulator()
    if mode in {'window', 'aligned_window'}:
        game.memory[0xFF40] = 0xB1
        game.screen.tilemap_position_list = [[0, 0, 4 if mode == 'window' else 0, 0] for _ in range(144)]
        # 未對齊時這個真實可見marker會被decoder安全略過，不能當成無UI。
        if mode == 'window':
            game.tilemap_window.cells[(0, 0)] = 7
    elif mode == 'scanline':
        game.screen.tilemap_position_list[3][0] = 8
    elif mode == 'unknown_scanline':
        game.screen.tilemap_position_list[10][0] = None
    return read_visible_text(game, DECODING)


def test_real_decoder_ready_uses_structured_evidence_and_not_warning_wording():
    valid = decoded_observation()
    assert valid['warnings'] and tx.ui_overworld_ready(valid, {})
    invalid = decoded_observation(mode='window')
    invalid['warnings'] = []
    assert not tx.ui_overworld_ready(invalid, {})
    # 對齊但空白的Window仍不證明野外，背景grid不會替可見UI背書。
    aligned_window = decoded_observation(mode='aligned_window')
    assert aligned_window['read_valid'] and aligned_window['alignment_verified']
    assert not tx.ui_overworld_ready(aligned_window, {})
    assert tx.ui_overworld_ready(text_at(), {})  # 舊純fixture沒有實際decoder profile。


@pytest.mark.parametrize('change', ['missing_read', 'missing_alignment', 'missing_window',
                                   'numeric_read', 'numeric_alignment', 'unknown_profile'])
def test_actual_decoder_profile_cannot_omit_or_coerce_validity_proof(change):
    text = decoded_observation()
    if change == 'missing_read': text.pop('read_valid')
    elif change == 'missing_alignment': text.pop('alignment_verified')
    elif change == 'missing_window': text.pop('window_visible')
    elif change == 'numeric_read': text['read_valid'] = 1
    elif change == 'numeric_alignment': text['alignment_verified'] = 1
    else: text['profile'] = 'unknown-decoder'
    assert not tx.ui_overworld_ready(text, {})


@pytest.mark.parametrize('mode', ['window', 'aligned_window', 'scanline', 'unknown_scanline'])
def test_incomplete_real_decoder_ui_cannot_send_arrow_entry(mode):
    args, model, observation = arrow_setup()
    _, grid = observation(model, frame=100)
    result, next_id = call(args, text=decoded_observation(mode=mode), grid=grid)
    assert result['available_actions'] == ['wait'] and result['phase'] == 'campaign_review'
    assert not result.get('field_move_complete') and next_id == 'gift'


@pytest.mark.parametrize('mode', ['window', 'aligned_window', 'scanline', 'unknown_scanline'])
def test_incomplete_real_decoder_cannot_complete_arrow_and_resets_idle_samples(mode):
    args, model, observation = arrow_setup()
    _, grid = observation(model, frame=100)
    assert call(args, text=decoded_observation(), grid=grid)[0]['available_actions'] == ['left', 'wait']
    for frame, text in [(132, decoded_observation()), (164, decoded_observation(mode=mode)),
                        (196, decoded_observation(mode=mode)), (228, decoded_observation())]:
        location, grid = observation(model, model.hop['expected_landing'], frame)
        args[1].update(location=location, frame=frame)
        args[0].frame_count = frame
        result, next_id = call(args, text=text, grid=grid)
        assert result['available_actions'] == ['wait'] and not result.get('field_move_complete')
        assert next_id == 'gift'
    location, grid = observation(model, model.hop['expected_landing'], 260)
    args[1].update(location=location, frame=260)
    args[0].frame_count = 260
    result, next_id = call(args, text=decoded_observation(), grid=grid)
    assert result['field_move_complete'] is True and next_id == 'after'


@pytest.mark.parametrize('mechanic', ['gift_eevee', 'teach_bubblebeam'])
def test_other_transactions_keep_rejection_of_incomplete_actual_decoder(mechanic):
    args = setup(mechanic)
    result, next_id = call(args, text=decoded_observation(mode='window'), grid={})
    assert result['review_reason'] == 'transaction_visible_text_not_verified'
    assert result['available_actions'] == ['wait'] and next_id == 'gift'
    assert not tx._CONTROLLERS
