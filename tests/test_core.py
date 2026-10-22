import json

import pytest

from laya_pokemon.core import append_jsonl, parse_rom_header, percentile, validate_action, write_json
from laya_pokemon.game import advance_action
from laya_pokemon.policy import RandomPolicy


def test_unknown_action_cannot_be_executed():
    with pytest.raises(ValueError):
        validate_action("shell_command")


def test_action_releases_button_even_when_emulator_fails():
    class Emulator:
        pressed = released = False
        def button_press(self, key): self.pressed = True
        def button_release(self, key): self.released = True
        def tick(self, *args): raise RuntimeError("emulator failure")
    emulator = Emulator()
    with pytest.raises(RuntimeError):
        advance_action(emulator, "a", 8, 16)
    assert emulator.pressed and emulator.released


def test_wait_and_movement_use_same_frame_budget():
    class Emulator:
        events = []
        def button_press(self, key): self.events.append(("press", key))
        def button_release(self, key): self.events.append(("release", key))
        def tick(self, *args): return True
    emulator = Emulator()
    assert advance_action(emulator, "up", 8, 16) == 24
    assert advance_action(emulator, "wait", 8, 16) == 24
    assert emulator.events == [("press", "up"), ("release", "up")]


def test_corrupt_or_unrelated_rom_rejected(tmp_path):
    path = tmp_path / "fixture.gb"
    path.write_bytes(b"not a rom")
    with pytest.raises(ValueError): parse_rom_header(path)
    data = bytearray(0x150)
    data[0x134:0x13F] = b"POKEMON RED"
    data[0x14A] = 1
    path.write_bytes(data)
    with pytest.raises(ValueError): parse_rom_header(path)
    checksum = 0
    for byte in data[0x134:0x14D]: checksum = (checksum - byte - 1) & 255
    data[0x14D] = checksum
    path.write_bytes(data)
    assert parse_rom_header(path)["title"] == "POKEMON RED"


def test_seeded_random_baseline_reproducible():
    a, b = RandomPolicy(42), RandomPolicy(42)
    assert [a.choose({}) for _ in range(30)] == [b.choose({}) for _ in range(30)]


def test_result_files_preserve_rows(tmp_path):
    path = tmp_path / "steps.jsonl"
    append_jsonl(path, {"step": 0})
    append_jsonl(path, {"step": 1})
    assert [json.loads(row)["step"] for row in path.read_text().splitlines()] == [0, 1]
    write_json(tmp_path / "summary.json", {"success": None})
    assert percentile([10, 20, 30], .5) == 20
    assert percentile([], .95) is None

