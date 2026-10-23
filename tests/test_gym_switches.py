from laya_pokemon.gym_switches import CANS, GymSwitchController, second_candidates
from tests.test_battle import text_at


def blank():
    return text_at()


def progress(first=False, second=False):
    return {'story_event_bits': {'first_lock_opened': first, 'second_lock_opened': second}}


def grid():
    cells = [[1] * 10 for _ in range(18)]
    for x, y in CANS:
        cells[y][x] = 0
    return {'walkable': cells, 'tileset_id': 7, 'screen_cells_verified': 60}


def location(x=1, y=8):
    return {'map_id': 92, 'x': x, 'y': y}


def start_check(controller, first=False, *, at=None, now=0):
    at = location() if at is None else at
    state = progress(first)
    hint = controller.context(blank(), at, state, grid(), now=now)
    assert hint['controller_interaction'] and hint['available_actions'][0] in {'up', 'down', 'left', 'right'}
    direction = hint['available_actions'][0]
    hint = controller.context(blank(), at, state, grid(), previous=[direction], now=now + .1)
    assert hint['available_actions'][0] == 'a'
    return at


def first_success(controller, now=0):
    at = start_check(controller, now=now)
    index = controller.current_can
    result = controller.context(text_at((1, 14, "Hey! There's a"), (1, 16, 'switch under the')), at,
                                progress(True), None, previous=['a'], now=now + .2)
    assert result['gym_switch_dialogue'] == 'first_lock_wrapped_page'
    assert controller.state == 'search_first'
    result = controller.context(text_at((1, 14, 'The 1st electric'), (1, 16, 'lock opened!')), at,
                                progress(True), None, previous=['a'], now=now + .3)
    assert controller.state == 'search_second' and controller.first_can == index
    return at, index, result


def test_can_layout_and_second_candidates_include_original_red_bug():
    assert CANS[0] == (1, 7) and CANS[1] == (1, 9) and CANS[14] == (9, 11)
    assert second_candidates(4) == [1, 3, 5, 7, 0]
    assert second_candidates(0) == [1, 3, 0]


def test_adjacent_source_position_is_faced_before_a_and_wait_does_not_count_as_press():
    controller = GymSwitchController()
    at = start_check(controller)
    assert controller.current_can == 0 and controller.attempts == 0
    result = controller.context(blank(), at, progress(), grid(), previous=['wait'], now=.2)
    assert result['available_actions'][0] == 'a' and controller.attempts == 0
    result = controller.context(text_at((1, 14, "Nope, there's"), (1, 16, 'only trash here.')),
                                at, progress(), None, previous=['a'], now=.3)
    assert controller.attempts == 1 and controller.checked == {0}
    assert result['gym_switch_dialogue'] == 'trash_confirmed'


def test_first_lock_wrapped_pages_keep_bucket_until_final_text_and_event_match():
    controller = GymSwitchController()
    at, index, _ = first_success(controller)
    assert index == 0
    repeat = controller.context(text_at((1, 14, 'The 1st electric'), (1, 16, 'lock opened!')),
                                at, progress(True), None, previous=['a'], now=.4)
    assert repeat['gym_switch_dialogue'] == 'first_lock_confirmed'
    assert len(controller.history) == 1
    hint = controller.context(blank(), at, progress(True), grid(), previous=['a'], now=.5)
    assert hint['gym_switch_can'] == 1 and hint['gym_switch_state'] == 'search_second'


def test_second_failure_first_trash_page_and_final_reset_only_count_once():
    controller = GymSwitchController()
    at, index, _ = first_success(controller)
    controller.context(blank(), at, progress(True), grid(), previous=['a'], now=.4)
    # 到已選定第二桶的相鄰位置，完成轉向和實際 A。
    at = start_check(controller, True, now=.5)
    trash = text_at((1, 14, "Nope! There's"), (1, 16, 'only trash here.'))
    first_page = controller.context(trash, at, progress(), None, previous=['a'], now=.7)
    assert first_page['gym_switch_state'] == 'reset' and controller.resets == 1
    final = text_at((1, 14, 'Hey! The electric'), (1, 16, 'locks were reset!'))
    controller.context(final, at, progress(), None, previous=['a'], now=.8)
    controller.context(final, at, progress(), None, previous=['a'], now=.9)
    assert controller.resets == 1 and controller.checked == set()
    assert controller.second_rotations[index] == 1
    hint = controller.context(blank(), at, progress(), grid(), previous=['a'], now=1)
    assert hint['gym_switch_state'] == 'search_first'


def test_second_success_requires_events_then_open_door_never_searches_again():
    controller = GymSwitchController()
    at, _, _ = first_success(controller)
    result = controller.context(text_at((1, 14, 'The 2nd electric'), (1, 16, 'lock opened!')),
                                at, progress(True, True), None, now=.4)
    assert result['gym_switch_dialogue'] == 'second_lock_confirmed'
    done = controller.context(blank(), at, progress(True, True), grid(), now=.5)
    assert done['gym_switches_complete'] and done['available_actions'] == ['wait']
    assert controller.context(blank(), at, progress(True, True), grid(), now=1)['gym_switches_complete']


def test_reconnect_to_open_door_requires_events_and_verified_door_grid():
    controller = GymSwitchController()
    assert controller.context(blank(), location(), progress(True, True), grid(), now=0)['gym_switches_complete']
    closed = grid()
    closed['walkable'][4][4] = 0
    assert GymSwitchController().context(blank(), location(), progress(True, True), closed,
                                        now=0)['review_reason'] == 'gym_switch_open_door_unverified'


def test_battle_interruption_does_not_send_buttons_or_spend_battle_wait_budget():
    controller = GymSwitchController(max_seconds=1)
    at = start_check(controller)
    assert controller.context(text_at((1, 14, 'I am a trainer!')), at, progress(), None,
                              battle_state={'kind': 'trainer', 'active': True}, previous=['a'], now=.2) is None
    assert controller.context(blank(), at, progress(), None,
                              battle_state={'kind': 'trainer', 'active': True}, now=100) is None
    hint = controller.context(blank(), at, progress(), grid(), now=100.1)
    assert hint['gym_switch_can'] == 0 and hint['available_actions'][0] == 'up'
    assert controller.attempts == 0 and controller.active_seconds < 1


def test_unrelated_trainer_dialogue_is_left_to_outer_controller():
    controller = GymSwitchController()
    assert controller.context(text_at((1, 14, "I'm good with"), (1, 16, 'electricity!')),
                              location(), progress(), None, now=0) is None


def test_unverified_grid_missing_events_and_text_event_mismatch_stop():
    bad = grid()
    bad['screen_cells_verified'] = 11
    assert GymSwitchController().context(blank(), location(), progress(), bad,
                                        now=0)['review_reason'] == 'gym_switch_grid_unverified'
    assert GymSwitchController().context(blank(), location(), {}, grid(),
                                        now=0)['review_reason'] == 'gym_switch_events_unavailable'
    result = GymSwitchController().context(text_at((1, 14, 'The 2nd electric'), (1, 16, 'lock opened!')),
                                           location(), progress(True), None, now=0)
    assert result['review_reason'] == 'gym_switch_second_text_event_mismatch'


def test_finite_attempt_time_and_response_limits_review_without_blind_a():
    controller = GymSwitchController(max_attempts=1)
    at = start_check(controller)
    controller.context(text_at((1, 14, "Nope, there's"), (1, 16, 'only trash here.')),
                       at, progress(), None, previous=['a'], now=.2)
    assert controller.context(blank(), at, progress(), grid(), now=.3)['review_reason'] == 'gym_switch_budget_exhausted'
    timed = GymSwitchController(max_seconds=1)
    timed.context(blank(), at, progress(), grid(), now=0)
    assert timed.context(blank(), at, progress(), grid(), now=1)['review_reason'] == 'gym_switch_budget_exhausted'
    missing = GymSwitchController(max_response_steps=2)
    at = start_check(missing)
    assert missing.context(blank(), at, progress(), grid(), previous=['a'], now=.2)['gym_switch_waiting_for_result']
    assert missing.context(blank(), at, progress(), grid(), previous=['wait'], now=.3)['review_reason'] == 'gym_switch_response_not_verified'


def test_state_is_on_controller_instance_and_not_reset_by_another_context_call():
    controller = GymSwitchController()
    at, first, _ = first_success(controller)
    alias = controller  # 主控熱載入仍持有原來的 controller instance。
    assert alias.first_can == first and alias.state == 'search_second'
    assert alias.context(blank(), at, progress(True), grid(), now=.4)['gym_switch_state'] == 'search_second'


def test_different_map_yields_none_and_unknown_existing_first_lock_requires_review():
    assert GymSwitchController().context(blank(), {'map_id': 5}, progress(), None, now=0) is None
    result = GymSwitchController().context(blank(), location(), progress(True), grid(), now=0)
    assert result['review_reason'] == 'gym_switch_first_origin_unknown'


def test_visible_switch_intro_and_event_can_survive_an_outer_dialogue_advance():
    controller = GymSwitchController()
    at = start_check(controller)
    controller.context(text_at((1, 14, "Hey! There's a"), (1, 16, 'switch under the')),
                       at, progress(True), None, previous=['a'], now=.2)
    result = controller.context(blank(), at, progress(True), grid(), previous=['a'], now=.3)
    assert result['gym_switch_state'] == 'search_second' and controller.first_can == 0
    assert controller.history[-1]['evidence'] == 'visible_intro_and_event'


def test_repeated_known_dialogue_is_still_bounded_by_active_time():
    controller = GymSwitchController(max_seconds=1)
    at = start_check(controller)
    intro = text_at((1, 14, "Hey! There's a"), (1, 16, 'switch under the'))
    controller.context(intro, at, progress(True), None, previous=['a'], now=.2)
    result = controller.context(intro, at, progress(True), None, previous=['a'], now=1)
    assert result['review_reason'] == 'gym_switch_budget_exhausted'


def test_first_intro_cannot_be_reused_to_misattribute_a_pending_second_check():
    controller = GymSwitchController()
    at, first, _ = first_success(controller)
    controller.context(blank(), at, progress(True), grid(), previous=['a'], now=.4)
    at = start_check(controller, True, now=.5)
    result = controller.context(blank(), at, progress(True), grid(), previous=['a'], now=.7)
    assert result['gym_switch_waiting_for_result'] and controller.first_can == first
