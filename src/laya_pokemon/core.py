"""不依賴模型／模擬器的控制與紀錄邏輯。"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Action:
    key: str
    description: str
    button: str | None


ACTIONS = (
    Action("up", "Press UP to move north or move the menu cursor up.", "up"),
    Action("down", "Press DOWN to move south or move the menu cursor down.", "down"),
    Action("left", "Press LEFT to move west or move the menu cursor left.", "left"),
    Action("right", "Press RIGHT to move east or move the menu cursor right.", "right"),
    Action("a", "Press A to confirm a selection, interact, or advance dialogue.", "a"),
    Action("b", "Press B to cancel or close a menu.", "b"),
    Action("start", "Press START to enter the title menu or open the game menu.", "start"),
    Action("wait", "Wait without pressing a button while an animation completes.", None),
)
ACTION_BY_KEY = {action.key: action for action in ACTIONS}


def validate_action(key: str) -> Action:
    if key not in ACTION_BY_KEY:
        raise ValueError(f"模型回傳未定義動作：{key!r}")
    return ACTION_BY_KEY[key]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")
        stream.flush()


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def parse_rom_header(path: Path) -> dict[str, Any]:
    """驗證卡匣檔案結構；不以標頭或校驗碼證明遊戲真偽與授權來源。"""
    data = path.read_bytes()
    if len(data) < 0x150:
        raise ValueError("ROM 檔案太短，無法讀取 Game Boy 標頭")
    # Pan Docs: https://gbdev.io/pandocs/The_Cartridge_Header.html
    logo = bytes.fromhex(
        "CE ED 66 66 CC 0D 00 0B 03 73 00 83 00 0C 00 0D "
        "00 08 11 1F 88 89 00 0E DC CC 6E E6 DD DD D9 99 "
        "BB BB 67 63 6E 0E EC CC DD DC 99 9F BB B9 33 3E"
    )
    if data[0x104:0x134] != logo:
        raise ValueError("ROM Nintendo logo 校驗失敗")
    size_code = data[0x148]
    if size_code > 8:
        raise ValueError(f"ROM 宣告了不支援的容量代碼：0x{size_code:02X}")
    declared_bytes = 0x8000 << size_code
    if len(data) != declared_bytes:
        raise ValueError(f"ROM 長度不符：標頭宣告 {declared_bytes} bytes，實際 {len(data)} bytes")
    title = data[0x134:0x144].split(b"\0", 1)[0].decode("ascii", errors="replace")
    if title not in {"POKEMON RED", "POKEMON BLUE"}:
        raise ValueError(f"目前只接受標頭為 POKEMON RED／BLUE 的 ROM，收到：{title!r}")
    checksum = 0
    for byte in data[0x134:0x14D]:
        checksum = (checksum - byte - 1) & 0xFF
    if checksum != data[0x14D]:
        raise ValueError("ROM 標頭校驗失敗")
    global_checksum = (sum(data[:0x14E]) + sum(data[0x150:])) & 0xFFFF
    if global_checksum != int.from_bytes(data[0x14E:0x150], "big"):
        raise ValueError("ROM 全檔校驗失敗（global checksum）")
    if data[0x14A] != 1:
        raise ValueError("此初版介面只接受非日本區 ROM；語言仍須人工確認為英文")
    return {"title": title, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "declared_bytes": declared_bytes, "nintendo_logo_valid": True,
            "header_checksum_valid": True, "global_checksum_valid": True,
            "validation_scope": "cartridge_structure_only", "revision": data[0x14C],
            "language_verified": False, "authenticity_verified": False, "source_verified": False}

