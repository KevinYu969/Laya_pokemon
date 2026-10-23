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
