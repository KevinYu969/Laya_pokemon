import json
from pathlib import Path

import pytest

from laya_pokemon.core import append_jsonl, parse_rom_header, percentile, validate_action, write_json
from laya_pokemon.game import advance_action
from laya_pokemon.policy import RandomPolicy


def test_write_json_retries_transient_replace_lock_without_rewriting_payload(tmp_path, monkeypatch):
    import laya_pokemon.core as core
    path = tmp_path / 'summary.json'
    path.write_text('{"old": true}\n', encoding='utf-8')
    payload = {'status': 'running', 'party': [{'species_name': 'EEVEE', 'level': 32}], 'text': '補練'}
    original_replace = Path.replace
    original_write = Path.write_text
    attempts, writes, sleeps = [], [], []
    def write(temporary, data, *args, **kwargs):
        writes.append(data)
        return original_write(temporary, data, *args, **kwargs)
    def replace(temporary, target):
        attempts.append(temporary.read_bytes())
        assert json.loads(path.read_text(encoding='utf-8')) == {'old': True}
        if len(attempts) <= 2:
            raise PermissionError('sharing lock')
        return original_replace(temporary, target)
    monkeypatch.setattr(Path, 'write_text', write)
    monkeypatch.setattr(Path, 'replace', replace)
    monkeypatch.setattr(core.time, 'sleep', sleeps.append)
    write_json(path, payload)
    assert len(attempts) == 3 and len(writes) == 1 and len(set(attempts)) == 1
    assert sleeps == [.025, .025]
    assert json.loads(path.read_text(encoding='utf-8')) == payload
    assert not path.with_suffix('.json.tmp').exists()


def test_write_json_persistent_lock_is_bounded_and_keeps_original(tmp_path, monkeypatch):
    import laya_pokemon.core as core
    path = tmp_path / 'summary.json'
    original = b'{"old": true}\n'
    path.write_bytes(original)
    attempts, sleeps = [], []
    error = PermissionError('persistent sharing lock')
    def replace(temporary, target):
        attempts.append(temporary.read_bytes())
        raise error
    monkeypatch.setattr(Path, 'replace', replace)
    monkeypatch.setattr(core.time, 'sleep', sleeps.append)
    with pytest.raises(PermissionError) as caught:
        write_json(path, {'new': True})
    assert caught.value is error
    assert len(attempts) == 10 and sleeps == [.025] * 9
    assert len(set(attempts)) == 1 and path.read_bytes() == original
    assert json.loads(path.with_suffix('.json.tmp').read_text(encoding='utf-8')) == {'new': True}


def test_write_json_other_replace_errors_are_not_retried(tmp_path, monkeypatch):
    import laya_pokemon.core as core
    path = tmp_path / 'summary.json'
    path.write_text('{"old": true}', encoding='utf-8')
    attempts, sleeps = [], []
    error = OSError('disk error')
    def replace(temporary, target):
        attempts.append(temporary)
        raise error
    monkeypatch.setattr(Path, 'replace', replace)
    monkeypatch.setattr(core.time, 'sleep', sleeps.append)
    with pytest.raises(OSError) as caught:
        write_json(path, {'new': True})
    assert caught.value is error and len(attempts) == 1 and sleeps == []
    assert json.loads(path.read_text(encoding='utf-8')) == {'old': True}


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


def _update_synthetic_checksums(data):
    checksum = 0
    for byte in data[0x134:0x14D]:
        checksum = (checksum - byte - 1) & 255
    data[0x14D] = checksum
    total = (sum(data[:0x14E]) + sum(data[0x150:])) & 0xFFFF
    data[0x14E:0x150] = total.to_bytes(2, "big")


def _synthetic_cartridge_structure(title=b"POKEMON RED"):
    """僅供結構測試的零填充資料，不含遊戲程式、素材或實際 ROM。"""
    data = bytearray(0x8000)
    data[0x104:0x134] = bytes.fromhex(
        "CE ED 66 66 CC 0D 00 0B 03 73 00 83 00 0C 00 0D "
        "00 08 11 1F 88 89 00 0E DC CC 6E E6 DD DD D9 99 "
        "BB BB 67 63 6E 0E EC CC DD DC 99 9F BB B9 33 3E"
    )
    data[0x134:0x134 + len(title)] = title
    data[0x14A] = 1
    _update_synthetic_checksums(data)
    return data


@pytest.mark.parametrize("title", [b"POKEMON RED", b"POKEMON BLUE"])
def test_synthetic_rom_validates_structure_without_authenticating_game(tmp_path, title):
    path = tmp_path / "synthetic-structure.gb"
    path.write_bytes(_synthetic_cartridge_structure(title))
    result = parse_rom_header(path)
    assert result["title"] == title.decode("ascii")
    assert result["bytes"] == result["declared_bytes"] == 0x8000
    assert result["nintendo_logo_valid"]
    assert result["header_checksum_valid"] and result["global_checksum_valid"]
    assert result["validation_scope"] == "cartridge_structure_only"
    assert result["language_verified"] is False
    assert result["authenticity_verified"] is False
    assert result["source_verified"] is False


def test_short_and_header_only_rom_rejected(tmp_path):
    path = tmp_path / "synthetic-structure.gb"
    path.write_bytes(b"not a rom")
    with pytest.raises(ValueError, match="太短"):
        parse_rom_header(path)
    # 即使有正確 logo、標頭和校驗值，336 bytes 也不是完整卡匣檔案。
    path.write_bytes(_synthetic_cartridge_structure()[:0x150])
    with pytest.raises(ValueError, match="長度不符"):
        parse_rom_header(path)


@pytest.mark.parametrize("corruption, error", [
    ("logo", "logo"),
    ("declared_size", "長度不符"),
    ("unsupported_size", "容量代碼"),
    ("truncated", "長度不符"),
    ("trailing_data", "長度不符"),
    ("header_checksum", "標頭校驗"),
    ("global_checksum", "全檔校驗"),
    ("game_content", "全檔校驗"),
    ("unrelated_title", "POKEMON RED／BLUE"),
    ("destination", "非日本區"),
])
def test_corrupt_or_unrelated_rom_rejected(tmp_path, corruption, error):
    path = tmp_path / "synthetic-structure.gb"
    data = _synthetic_cartridge_structure()
    if corruption == "logo":
        data[0x133] ^= 1  # 也檢查 logo 的後半段。
        _update_synthetic_checksums(data)
    elif corruption == "declared_size":
        data[0x148] = 1
        _update_synthetic_checksums(data)
    elif corruption == "unsupported_size":
        data[0x148] = 0xFF
        _update_synthetic_checksums(data)
    elif corruption == "truncated":
        data = data[:-1]
    elif corruption == "trailing_data":
        data += b"\0"
    elif corruption == "header_checksum":
        data[0x14D] ^= 1
        total = (sum(data[:0x14E]) + sum(data[0x150:])) & 0xFFFF
        data[0x14E:0x150] = total.to_bytes(2, "big")
    elif corruption == "global_checksum":
        data[0x14F] ^= 1
    elif corruption == "game_content":
        data[-1] ^= 1
    elif corruption == "unrelated_title":
        data[0x134:0x144] = b"OTHER GAME".ljust(16, b"\0")
        _update_synthetic_checksums(data)
    elif corruption == "destination":
        data[0x14A] = 0
        _update_synthetic_checksums(data)
    path.write_bytes(data)
    with pytest.raises(ValueError, match=error):
        parse_rom_header(path)


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

