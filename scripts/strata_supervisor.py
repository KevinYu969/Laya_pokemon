"""地端階段監督器；遊戲子程序照常離線，每輪60秒，無Computer Use依賴。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from laya_pokemon.core import append_jsonl, parse_rom_header, sha256_file, write_json, utc_now
from laya_pokemon.local_planner import PlannerConfig, StrataPlanner, PlannerError, planner_snapshot, allowed_stages


ROOT = Path(__file__).resolve().parents[1]


def inside_project(value, *, directory=False):
    path = Path(value).resolve()
    if not path.is_relative_to(ROOT):
        raise PlannerError("只接受本實驗工作目錄內的檔案")
    if directory and path.exists():
        raise PlannerError("輸出目錄已存在，不覆寫既有實驗")
    return path


def snapshot_from_state(rom, state):
    from pyboy import PyBoy
    from laya_pokemon.progress import read_progress
    from laya_pokemon.navigation import read_location
    from laya_pokemon.observation import read_visible_text
    from laya_pokemon.battle import read_battle_state
    emulator = PyBoy(str(rom), window="null", sound_emulated=False)
    try:
        with state.open("rb") as stream:
            emulator.load_state(stream)
        emulator.tick(1, True, False)
        return planner_snapshot(read_progress(emulator), read_location(emulator), read_visible_text(emulator), read_battle_state(emulator))
    finally:
        emulator.stop(save=False)


def game_command(rom, state, strategy, output):
    # 不使用模型文字組 shell；固定可執行檔與允許的CLI參數，按鍵仍由本機Laya選擇。
    return [sys.executable, "-X", "utf8", "-m", "laya_pokemon.cli", "play", "--rom", str(rom),
            "--state", str(state), "--player-name", "KEVIN", "--objective", "Train the team and advance the current verified goal.",
            "--opening-route", "--strategy-file", str(strategy), "--policy", "laya", "--steps", "300",
            "--hold-frames", "8", "--settle-frames", "32", "--window", "--scale", "4", "--offline", "--video", "--output", str(output)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="忽略於Git的私人Strata設定")
    parser.add_argument("--rom", default="roms/pokemon_red.gb")
    parser.add_argument("--state")
    parser.add_argument("--output", required=True, help="全新的outputs子目錄")
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--probe-only", action="store_true", help="只核對模型目錄，不讀ROM／存檔、不傳遊戲資料")
    args = parser.parse_args()
    if not args.probe_only and not args.state:
        parser.error("啟動遊戲須指定--state；--probe-only不需要存檔")
    if not 1 <= args.episodes <= 20:
        parser.error("episodes須為1至20；每個遊戲子程序仍限60秒")
    config_path = inside_project(args.config)
    if not config_path.is_relative_to(ROOT / ".local"):
        parser.error("含端點的設定檔必須放在.local")
    output = inside_project(args.output, directory=True)
    if not output.is_relative_to(ROOT / "outputs"):
        parser.error("監督器輸出只能放在outputs")
    planner = StrataPlanner(PlannerConfig.load(config_path))
    output.mkdir(parents=True)
    report = {"recorded_at": utc_now(), "status": "running", "planner_backend": "configured_private_strata",
              "button_backend": "local_laya_cpu_offline", "computer_use_required": False, "cloud_fallback": False,
              "max_episodes": args.episodes, "game_max_wall_seconds": 60, "episodes": []}
    try:
        report.update(planner.verify_model())
        if args.probe_only:
            report.update(status="catalog_verified", game_data_sent=False)
            return
        rom, state = inside_project(args.rom), inside_project(args.state)
        if parse_rom_header(rom)["sha256"] != "5ca7ba01642a3b27b0cc0b5349b52792795b62d3ed977e98a09390659af96b7b":
            raise PlannerError("只接受已核對的紅版ROM")
        previous_stop = None
        for episode in range(args.episodes):
            snapshot = snapshot_from_state(rom, state)
            choices = allowed_stages(snapshot)
            snapshot["previous_stop_reason"] = previous_stop
            decision = planner.decide(snapshot, choices)
            append_jsonl(output / "decisions.jsonl", {"at": utc_now(), "episode": episode,
                         "state_sha256": sha256_file(state), "snapshot": snapshot, **decision})
            if decision["stage"] in {"review", "stop"}:
                report.update(status="stopped", stop_reason=decision["stage"])
                break
            strategy = output / f"strategy-{episode:02}.json"
            write_json(strategy, {"stage": decision["stage"], "starter": "BULBASAUR"})
            run = output / f"game-{episode:02}"
            with (output / f"game-{episode:02}.log").open("w", encoding="utf-8") as log:
                process = subprocess.run(game_command(rom, state, strategy, run), cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                         encoding="utf-8")
            if not (run / "summary.json").is_file() or not (run / "final.state").is_file():
                raise PlannerError("遊戲未留下完整摘要／存檔，不自動重跑")
            summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
            previous_stop = summary.get("stop_reason")
            report["episodes"].append({"episode": episode, "stage": decision["stage"], "game_directory": run.name,
                                       "stop_reason": previous_stop, "completed_steps": summary.get("completed_steps", 0)})
            state = run / "final.state"
            report["latest_state"] = str(state.relative_to(output))
            write_json(output / "summary.json", report)
            # 關窗、未知選單、模型／遊戲錯誤都交回人工，不把停止意圖變成自動重啟。
            if process.returncode or previous_stop not in {"wall_clock_limit", "action_budget", "capture_milestone", "training_milestone"}:
                report.update(status="stopped", stop_reason=previous_stop or "game_failed")
                break
        else:
            report.update(status="stopped", stop_reason="episode_budget")
    except PlannerError as error:
        report.update(status="stopped", stop_reason="planner_error", error=str(error))
        raise
    except KeyboardInterrupt:
        report.update(status="stopped", stop_reason="keyboard_interrupt")
        raise
    except Exception as error:
        report.update(status="stopped", stop_reason="supervisor_error", error_type=type(error).__name__)
        raise
    finally:
        write_json(output / "summary.json", report)
        print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except PlannerError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
