"""即時控制的事件與期限契約；不載入 PyBoy、Torch 或 ROM。"""
from threading import Event, get_ident

import pytest

from laya_pokemon import game


PAUSE = object()
UNPAUSE = object()


class Emulator:
    def __init__(self, on_tick=None):
        self.events = []
        self.tick_count = 0
        self.on_tick = on_tick

    def send_input(self, event):
        self.events.append(("input", event))

    def tick(self, *args):
        self.tick_count += 1
        self.events.append(("tick", self.tick_count))
        return True if self.on_tick is None else self.on_tick(self.tick_count)

    def button_press(self, button):
        self.events.append(("press", button))

    def button_release(self, button):
        self.events.append(("release", button))


class ImmediateThread:
    """以決定性排程重現 operation 在下一個事件 tick 前完成。"""
    def __init__(self, *, target, **kwargs):
        self.target = target

    def start(self):
        self.target()


def test_worker_operation_keeps_event_ticks_on_main_thread(monkeypatch):
    monkeypatch.setattr(game.time, "perf_counter", lambda: 0)
    main_thread = get_ident()
    started, released, finished = Event(), Event(), Event()
    operation_threads = []
    decision = {"action": "a"}

    def operation():
        operation_threads.append(get_ident())
        started.set()
        try:
            assert released.wait(2), "主執行緒未持續處理事件"
            return decision
        finally:
            finished.set()

    def on_tick(count):
        assert get_ident() == main_thread
        if count == 2:
            assert started.wait(2)
            assert not finished.is_set()
            released.set()
            assert finished.wait(2)
        return True

    emulator = Emulator(on_tick)
    try:
        assert game.run_with_window_events(emulator, operation, 100, PAUSE, UNPAUSE) is decision
    finally:
        released.set()
    assert operation_threads and operation_threads[0] != main_thread
    assert emulator.tick_count >= 2
    assert emulator.events[0] == ("input", PAUSE)
    assert emulator.events[-1] == ("input", UNPAUSE)


def test_operation_error_is_preserved_and_unpauses(monkeypatch):
    monkeypatch.setattr(game, "Thread", ImmediateThread)
    monkeypatch.setattr(game.time, "perf_counter", lambda: 0)
    original_error = ValueError("model failed")

    def operation():
        raise original_error

    emulator = Emulator()
    with pytest.raises(ValueError) as raised:
        game.run_with_window_events(emulator, operation, 100, PAUSE, UNPAUSE)
    assert raised.value is original_error
    assert emulator.events[-1] == ("input", UNPAUSE)


@pytest.mark.parametrize("close_on_tick", [1, 2])
def test_window_close_is_normal_stop_and_unpauses(monkeypatch, close_on_tick):
    class PendingThread:
        def __init__(self, **kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(game, "Thread", PendingThread)
    monkeypatch.setattr(game.time, "perf_counter", lambda: 0)
    emulator = Emulator(lambda count: count != close_on_tick)
    with pytest.raises(game.WindowClosed):
        game.run_with_window_events(emulator, lambda: None, 100, PAUSE, UNPAUSE)
    assert emulator.tick_count == close_on_tick
    assert emulator.events[-1] == ("input", UNPAUSE)


def test_expired_deadline_does_not_start_operation_or_pause(monkeypatch):
    monkeypatch.setattr(game, "Thread", ImmediateThread)
    monkeypatch.setattr(game.time, "perf_counter", lambda: 100)
    called = []
    emulator = Emulator()
    with pytest.raises(game.TimeBudgetReached):
        game.run_with_window_events(emulator, lambda: called.append(True), 100, PAUSE, UNPAUSE)
    assert called == []
    assert emulator.events == []


def test_first_event_tick_can_exhaust_deadline_before_operation(monkeypatch):
    clock = [0]
    called = []

    def on_tick(count):
        clock[0] = 100
        return True

    monkeypatch.setattr(game, "Thread", ImmediateThread)
    monkeypatch.setattr(game.time, "perf_counter", lambda: clock[0])
    emulator = Emulator(on_tick)
    with pytest.raises(game.TimeBudgetReached):
        game.run_with_window_events(emulator, lambda: called.append(True), 100, PAUSE, UNPAUSE)
    assert called == []
    assert emulator.events[-1] == ("input", UNPAUSE)


def test_immediate_result_finishing_after_deadline_is_not_returned(monkeypatch):
    clock = [0]

    def operation():
        clock[0] = 100
        return {"action": "right"}

    monkeypatch.setattr(game, "Thread", ImmediateThread)
    monkeypatch.setattr(game.time, "perf_counter", lambda: clock[0])
    emulator = Emulator()
    with pytest.raises(game.TimeBudgetReached):
        game.run_with_window_events(emulator, operation, 100, PAUSE, UNPAUSE)
    assert emulator.events[-1] == ("input", UNPAUSE)


def test_result_finishing_during_late_tick_is_not_returned(monkeypatch):
    clock = [0]
    pending = []

    class DeferredThread:
        def __init__(self, *, target, **kwargs):
            pending.append(target)

        def start(self):
            pass

    def on_tick(count):
        if count == 2:
            clock[0] = 100
            pending.pop()()
        return True

    monkeypatch.setattr(game, "Thread", DeferredThread)
    monkeypatch.setattr(game.time, "perf_counter", lambda: clock[0])
    emulator = Emulator(on_tick)
    with pytest.raises(game.TimeBudgetReached):
        game.run_with_window_events(emulator, lambda: {"action": "a"}, 100, PAUSE, UNPAUSE)
    assert emulator.tick_count == 2
    assert emulator.events[-1] == ("input", UNPAUSE)


@pytest.mark.parametrize("close_on_tick", [2, 4])
def test_action_releases_button_when_window_closes_during_hold_or_settle(close_on_tick):
    emulator = Emulator(lambda count: count != close_on_tick)
    with pytest.raises(game.WindowClosed):
        game.advance_action(emulator, "up", hold_frames=3, settle_frames=2)
    assert emulator.events.count(("press", "up")) == 1
    assert emulator.events.count(("release", "up")) == 1
    assert emulator.tick_count == close_on_tick


def test_frame_callback_failure_still_releases_button():
    emulator = Emulator()
    emulator.screen = type("Screen", (), {"ndarray": object()})()
    original_error = RuntimeError("recording failed")

    def callback(frame):
        raise original_error

    with pytest.raises(RuntimeError) as raised:
        game.advance_action(emulator, "a", 3, 2, callback)
    assert raised.value is original_error
    assert emulator.events[-1] == ("release", "a")
