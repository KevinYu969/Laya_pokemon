"""PyBoy 有限步控制與遊戲時間錄影；任務成功評估尚待 ROM 校準。"""
from __future__ import annotations

import json
import time
from concurrent.futures import Future
from pathlib import Path
from threading import Thread

from .core import append_jsonl, parse_rom_header, sha256_file, utc_now, validate_action, write_json


class WindowClosed(RuntimeError):
    """使用者關閉即時視窗，屬正常停止。"""


class TimeBudgetReached(RuntimeError):
    pass


def run_with_window_events(pyboy, operation, deadline: float, pause_event, unpause_event):
    """模型不碰模擬器；主執行緒在暫停遊戲時持續處理 SDL 事件。"""
    if time.perf_counter() >= deadline:
        raise TimeBudgetReached("已達執行時間上限")
    result = Future()

    def worker():
        try:
            result.set_result(operation())
        except BaseException as error:
            result.set_exception(error)

    pyboy.send_input(pause_event)
    try:
        if not pyboy.tick(1, True, False):
            raise WindowClosed("使用者關閉 PyBoy 視窗")
        if time.perf_counter() >= deadline:
            raise TimeBudgetReached("已達執行時間上限")
        # 關閉視窗後不等待正在進行的 CPU 推論；worker 不可操作 PyBoy 或輸出檔案。
        Thread(target=worker, name="laya-inference", daemon=True).start()
        while not result.done():
            if time.perf_counter() >= deadline:
                raise TimeBudgetReached("已達執行時間上限")
            if not pyboy.tick(1, True, False):
                raise WindowClosed("使用者關閉 PyBoy 視窗")
        if time.perf_counter() >= deadline:
            raise TimeBudgetReached("已達執行時間上限")
        return result.result()
    finally:
        pyboy.send_input(unpause_event)


def observe(pyboy, objective: str) -> dict:
    wrapper = pyboy.game_wrapper
    state = {"objective": objective, "phase": "unclassified", "input_method": "emulator_state",
             "observation_profile": "gen1-visible-crop-v0-unvalidated"}
    # 只擷取螢幕中央小範圍；未宣稱這是精確的玩家中心或可用尋路圖。
    if hasattr(wrapper, "game_area_collision"):
        grid = wrapper.game_area_collision()
        state["central_collision_tiles"] = grid[7:12, 6:11].tolist()
    if hasattr(wrapper, "party"):
        state["party_summary"] = [{key: mon[key] for key in ("species", "level", "hp", "max_hp") if key in mon}
                                  for mon in wrapper.party]
    return state


def advance_action(pyboy, action_key: str, hold_frames: int, settle_frames: int, on_frame=None) -> int:
    action = validate_action(action_key)
    if hold_frames < 1 or settle_frames < 0:
        raise ValueError("按住幀數至少 1，等待幀數不能為負")
    frames = 0
    try:
        if action.button:
            pyboy.button_press(action.button)
        for _ in range(hold_frames):
            if not pyboy.tick(1, True, False):
                raise WindowClosed("使用者關閉 PyBoy 視窗")
            frames += 1
            if on_frame:
                on_frame(pyboy.screen.ndarray)
    finally:
        if action.button:
            pyboy.button_release(action.button)
    for _ in range(settle_frames):
        if not pyboy.tick(1, True, False):
            raise WindowClosed("使用者關閉 PyBoy 視窗")
        frames += 1
        if on_frame:
            on_frame(pyboy.screen.ndarray)
    return frames


def play_game(args) -> None:
    from pyboy import PyBoy
    from pyboy.utils import WindowEvent
    from .cli import environment
    from .policy import LayaPolicy, RandomPolicy, SimpleRulePolicy
    from .video import VideoRecorder

    if args.steps < 1 or args.steps > 300:
        raise ValueError("首輪展示的 steps 必須介於 1 至 300")
    if args.hold_frames < 1 or args.settle_frames < 0:
        raise ValueError("按鍵幀數設定不正確")
    if not 1 <= args.scale <= 8 or not 1 <= args.threads <= 32 or not 0 <= args.boot_frames <= 600:
        raise ValueError("scale 須為 1–8、threads 為 1–32、boot-frames 為 0–600")
    rom = Path(args.rom).resolve(strict=True)
    header = parse_rom_header(rom)
    saved_state = Path(args.state).resolve(strict=True) if args.state else None
    output = Path(args.output)
    if output.exists():
        raise ValueError("輸出目錄已存在，請指定新的 run 目錄")
    output.mkdir(parents=True)
    metadata = {**environment(), "recorded_at": utc_now(), "kind": "pokemon_control_demo",
        "status": "running", "policy": args.policy, "seed": args.seed, "rom": header,
        "state_sha256": sha256_file(saved_state) if saved_state else None,
        "max_steps": args.steps, "hold_frames": args.hold_frames, "settle_frames": args.settle_frames,
        "window": args.window, "scale": args.scale, "boot_frames": args.boot_frames,
        "offline": args.offline, "threads": args.threads,
        "waiting_behavior": "pause emulation and pump SDL events during model loading/inference",
        "desktop_foreground_verified": False,
        "observation_profile": "gen1-visible-crop-v0-unvalidated", "task_success": None,
        "limitation": "Limited button-control demo; no validated navigation/dialogue/battle success evaluator."}
    write_json(output / "metadata.json", metadata)
    emulator = recorder = None
    sampled_frames = 0
    started = time.perf_counter()
    deadline = started + 600

    def stage(name):
        metadata["stage"] = name
        write_json(output / "metadata.json", metadata)
        append_jsonl(output / "events.jsonl", {"at": utc_now(), "stage": name})
        print(f"PyBoy：{name}", flush=True)

    def frame_ready(frame):
        nonlocal sampled_frames
        sampled_frames += 1
        if recorder and sampled_frames % 2 == 0:
            recorder.append(frame)

    def model_task(operation):
        if args.window:
            return run_with_window_events(emulator, operation, deadline, WindowEvent.PAUSE, WindowEvent.UNPAUSE)
        return operation()

    try:
        # 使用者的 ROM 不變更；結束時不自動寫入 cartridge RAM。
        emulator = PyBoy(str(rom), window="SDL2" if args.window else "null", scale=args.scale,
                         sound_emulated=False, title_status=True)
        emulator.set_emulation_speed(1 if args.window else 0)
        stage("視窗已建立；尚未驗證桌面前景")
        if saved_state:
            with saved_state.open("rb") as stream:
                emulator.load_state(stream)
        if args.video:
            recorder = VideoRecorder(output / "gameplay.mp4")
        # 初次觀測前先完成開機幀；有存檔則只渲染一幀。
        advance_action(emulator, "wait", 1 if saved_state else max(1, args.boot_frames), 0, frame_ready)
        stage("載入模型；視窗標示 PAUSED 時為等待推論")
        policy = model_task(lambda: LayaPolicy(revision=args.revision, threads=args.threads, offline=args.offline)) \
            if args.policy == "laya" else {"random": lambda: RandomPolicy(args.seed), "rule": SimpleRulePolicy}[args.policy]()
        if args.policy == "laya":
            metadata.update(model=policy.model_id, model_revision=policy.revision, device="cpu")
        stage("即時按鍵控制；遊戲任務成功尚未校準")
        for index in range(args.steps):
            if time.perf_counter() >= deadline:
                raise TimeBudgetReached("已達執行時間上限")
            step_start = time.perf_counter()
            state = observe(emulator, args.objective)
            decision = model_task(lambda: policy.choose(state))
            frames = advance_action(emulator, decision["action"], args.hold_frames, args.settle_frames, frame_ready)
            append_jsonl(output / "steps.jsonl", {"step": index, "state": state, **decision,
                "emulated_frames": frames, "loop_ms": (time.perf_counter() - step_start) * 1000})
        else:
            metadata["stop_reason"] = "action_budget"
        emulator.screen.image.save(output / "last-frame.png")
        metadata["status"] = "completed_demo"
    except (WindowClosed, TimeBudgetReached, KeyboardInterrupt) as error:
        metadata.update(status="stopped", stop_reason="window_closed" if isinstance(error, WindowClosed)
                        else "wall_clock_limit" if isinstance(error, TimeBudgetReached) else "keyboard_interrupt")
    except Exception as error:
        metadata.update(status="failed", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        cleanup_errors = []
        if recorder:
            try:
                metadata["video"] = recorder.close()
            except Exception as error:
                cleanup_errors.append({"resource": "video", "type": type(error).__name__, "error": str(error)})
        if emulator:
            try:
                emulator.stop(save=False)
            except Exception as error:
                cleanup_errors.append({"resource": "emulator", "type": type(error).__name__, "error": str(error)})
        if cleanup_errors:
            metadata.update(cleanup_errors=cleanup_errors, status="failed")
        metadata.update(wall_seconds=time.perf_counter() - started, emulated_frames=sampled_frames)
        write_json(output / "metadata.json", metadata)
        write_json(output / "summary.json", metadata)
        if cleanup_errors and "error_type" not in metadata:
            raise RuntimeError("清理資源失敗，詳見 summary.json")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))

