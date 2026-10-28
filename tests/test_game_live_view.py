"""Exercise play's live publisher with a synthetic emulator, without ROMs or models."""
import json
import sys
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest

from laya_pokemon import cli, game


@pytest.mark.parametrize("ending,expected", [
    ("complete", "stopped"), ("review", "paused_for_review"),
    ("error", "stopped"), ("interrupt", "stopped"),
])
def test_headless_play_publishes_pixels_allowlisted_state_and_final_status(tmp_path, monkeypatch, ending, expected):
    pixels = np.zeros((144, 160, 4), dtype=np.uint8)
    pixels[4, 8] = [12, 34, 56, 255]
    events = []

    class Emulator:
        frame_count = 0
        screen = SimpleNamespace(ndarray=pixels, image=Image.fromarray(pixels))

        def __init__(self, *args, **kwargs):
            events.append(("window", kwargs["window"]))

        def set_emulation_speed(self, value):
            pass

        def tick(self, *args):
            self.frame_count += 1
            return True

        def save_state(self, stream):
            stream.write(b"synthetic-state")

        def stop(self, save):
            events.append(("stop", save))

    class Policy:
        def choose(self, state):
            if ending == "error":
                raise ValueError("synthetic-model-error")
            if ending == "interrupt":
                raise KeyboardInterrupt()
            return {"action": "wait"}

    monkeypatch.setitem(sys.modules, "pyboy", SimpleNamespace(PyBoy=Emulator))
    monkeypatch.setitem(sys.modules, "pyboy.utils", SimpleNamespace(WindowEvent=object()))
    monkeypatch.setitem(sys.modules, "laya_pokemon.policy", SimpleNamespace(
        LayaPolicy=Policy, RandomPolicy=lambda _: Policy(), SimpleRulePolicy=Policy))
    monkeypatch.setattr(cli, "environment", lambda: {})
    monkeypatch.setattr(game, "parse_rom_header", lambda _: {"sha256": "synthetic"})
    state = {"phase": "strategy_review" if ending == "review" else "overworld",
             "review_reason": "unknown_menu", "screen_sha256": "synthetic", "frame": 1,
             "progress": {"party": [], "badges_raw": 0},
             "credentials": "must-not-publish"}
    monkeypatch.setattr(game, "observe", lambda *args: state.copy())
    rom = tmp_path / "synthetic.gb"
    rom.write_bytes(b"synthetic-not-rom")
    output = tmp_path / "run"
    args = SimpleNamespace(rom=str(rom), state=None, objective="Wait.", policy="rule",
        steps=1, hold_frames=1, settle_frames=0, output=str(output), offline=False,
        video=False, window=False, live_view=True, scale=4, boot_frames=1, threads=4,
        player_name="KEVIN", opening_route=False, strategy_file=None, seed=0)
    if ending == "error":
        with pytest.raises(ValueError, match="synthetic-model-error"):
            game.play_game(args)
    else:
        game.play_game(args)
    payload = (output / "live-frame.json").read_text(encoding="utf-8")
    record = json.loads(payload)
    assert record["status"] == expected
    assert record["phase"] == state["phase"]
    assert record["frame"] >= 1
    assert "must-not-publish" not in payload
    assert set(record) == {"frame", "at", "status", "phase", "review_reason", "location", "party", "badges_raw"}
    with Image.open(output / "live-frame.png") as image:
        assert image.size == (160, 144)
        assert image.getpixel((8, 4)) == (12, 34, 56)
    assert (output / "final.state").read_bytes() == b"synthetic-state"
    assert events == [("window", "null"), ("stop", False)]
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == ("failed" if ending == "error" else "stopped" if ending != "complete" else "completed_demo")


def test_cli_accepts_live_view_without_native_window(monkeypatch):
    received = []
    monkeypatch.setattr(game, "play_game", received.append)
    monkeypatch.setattr(sys, "argv", ["laya-pokemon", "play", "--rom", "synthetic.gb",
        "--objective", "Wait.", "--output", "run", "--live-view"])
    cli.main()
    assert received[0].live_view is True
    assert received[0].window is False
