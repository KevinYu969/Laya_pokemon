from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from .core import append_jsonl, percentile, sha256_file, utc_now, write_json


def environment() -> dict:
    packages = {}
    for name in ("laya", "torch", "transformers", "pyboy", "psutil", "imageio", "imageio-ffmpeg", "Pillow"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    changes = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    source = {path.as_posix(): sha256_file(path) for path in sorted(Path("src").rglob("*.py"))}
    return {"recorded_at": utc_now(), "python": platform.python_version(), "os": platform.system(),
            "packages": packages, "code_commit": commit.stdout.strip() if commit.returncode == 0 else None,
            "code_dirty": bool(changes.stdout.strip()), "source_sha256": source}


def model_smoke(args) -> None:
    import psutil
    from .policy import LayaPolicy
    output = Path(args.output)
    if output.exists():
        raise ValueError("輸出目錄已存在；請指定新的 run 目錄，避免覆蓋證據")
    output.mkdir(parents=True)
    started = time.perf_counter()
    write_json(output / "metadata.json", {**environment(), "status": "running", "kind": "synthetic_control_smoke"})
    cases = [
        ({"phase": "overworld", "objective": "Move one tile east. The tile east is clear."}, "right"),
        ({"phase": "overworld", "objective": "Move one tile west. The tile west is clear."}, "left"),
        ({"phase": "overworld", "objective": "Move one tile north. The tile north is clear."}, "up"),
        ({"phase": "overworld", "objective": "Move one tile south. The tile south is clear."}, "down"),
        ({"phase": "dialogue", "objective": "Advance the visible dialogue with the confirm button."}, "a"),
        ({"phase": "menu", "objective": "Cancel and close this menu."}, "b"),
        ({"phase": "animation", "objective": "Do not press buttons until the animation finishes."}, "wait"),
    ]
    try:
        policy = LayaPolicy(revision=args.revision, threads=args.threads)
        warmup = policy.choose(cases[0][0])
        for index, (state, expected) in enumerate(cases):
            decision = policy.choose(state)
            append_jsonl(output / "steps.jsonl", {"case": index, "state": state, "expected": expected,
                "matches_expected": decision["action"] == expected, **decision})
        rows = [json.loads(line) for line in (output / "steps.jsonl").read_text(encoding="utf-8").splitlines()]
        timing = [row["model_ms"] for row in rows]
        summary = {**environment(), "status": "completed", "kind": "synthetic_control_smoke_not_gameplay",
            "model": policy.model_id, "model_revision": policy.revision, "device": "cpu", "threads": args.threads,
            "cases": len(rows), "matches_expected": sum(row["matches_expected"] for row in rows),
            "model_p50_ms": percentile(timing, .5), "model_p95_ms": percentile(timing, .95),
            "download_and_load_seconds": policy.load_seconds, "warmup_ms": warmup["model_ms"],
            "wall_seconds": time.perf_counter() - started, "rss_after_bytes": psutil.Process().memory_info().rss,
            "limitation": "Seven synthetic control cases; not Pokemon task success or a general benchmark."}
        write_json(output / "summary.json", summary)
        write_json(output / "metadata.json", summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except Exception as error:
        failure = {"status": "failed", "type": type(error).__name__, "error": str(error), "recorded_at": utc_now()}
        write_json(output / "failure.json", failure)
        write_json(output / "metadata.json", {**environment(), **failure, "kind": "synthetic_control_smoke"})
        raise


def main() -> None:
    os.environ.setdefault("HF_HOME", str(Path.cwd() / ".cache" / "huggingface"))
    parser = argparse.ArgumentParser(description="Laya × 寶可夢實驗工具")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="列出專案環境，不下載權重")
    doctor.add_argument("--output")
    smoke = commands.add_parser("model-smoke", help="以真實 Laya 權重測試合成控制情境")
    smoke.add_argument("--output", required=True)
    smoke.add_argument("--revision", default="main")
    smoke.add_argument("--threads", type=int, default=4)
    record = commands.add_parser("recording-smoke", help="產生清楚標示為非遊戲畫面的錄影管線測試")
    record.add_argument("--output", required=True)
    play = commands.add_parser("play", help="執行使用者自行提供 ROM 的限步控制展示")
    play.add_argument("--rom", required=True)
    play.add_argument("--state")
    play.add_argument("--objective", required=True)
    play.add_argument("--policy", choices=["laya", "random", "rule"], default="laya")
    play.add_argument("--steps", type=int, default=100)
    play.add_argument("--seed", type=int, default=0)
    play.add_argument("--hold-frames", type=int, default=8)
    play.add_argument("--settle-frames", type=int, default=16)
    play.add_argument("--output", required=True)
    play.add_argument("--video", action="store_true")
    play.add_argument("--window", action="store_true")
    args = parser.parse_args()
    if args.command == "doctor":
        result = environment()
        result["project_venv"] = sys.prefix != sys.base_prefix
        if args.output:
            write_json(Path(args.output), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "model-smoke":
        model_smoke(args)
    elif args.command == "recording-smoke":
        from .video import recording_smoke
        path = Path(args.output)
        if path.exists():
            raise ValueError("影片已存在，請使用新檔名")
        result = recording_smoke(path)
        write_json(path.with_suffix(".json"), result)
        print(json.dumps(result, indent=2))
    elif args.command == "play":
        from .game import play_game
        play_game(args)


if __name__ == "__main__":
    main()
