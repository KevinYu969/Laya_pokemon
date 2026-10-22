"""PyBoy 有限步控制與遊戲時間錄影；任務成功評估尚待 ROM 校準。"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .core import append_jsonl, parse_rom_header, sha256_file, utc_now, validate_action, write_json


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
                raise RuntimeError("模擬器已停止")
            frames += 1
            if on_frame:
                on_frame(pyboy.screen.ndarray)
    finally:
        if action.button:
            pyboy.button_release(action.button)
    for _ in range(settle_frames):
        if not pyboy.tick(1, True, False):
            raise RuntimeError("模擬器已停止")
        frames += 1
        if on_frame:
            on_frame(pyboy.screen.ndarray)
    return frames


def play_game(args) -> None:
    from pyboy import PyBoy
    from .cli import environment
    from .policy import LayaPolicy, RandomPolicy, SimpleRulePolicy
    from .video import VideoRecorder

    if args.steps < 1 or args.steps > 300:
        raise ValueError("首輪展示的 steps 必須介於 1 至 300")
    if args.hold_frames < 1 or args.settle_frames < 0:
        raise ValueError("按鍵幀數設定不正確")
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
        "observation_profile": "gen1-visible-crop-v0-unvalidated", "task_success": None,
        "limitation": "Limited button-control demo; no validated navigation/dialogue/battle success evaluator."}
    write_json(output / "metadata.json", metadata)
    emulator = recorder = None
    sampled_frames = total_frames = 0
    started = time.perf_counter()
    try:
        policy = {"laya": LayaPolicy, "random": lambda: RandomPolicy(args.seed), "rule": SimpleRulePolicy}[args.policy]()
        if args.policy == "laya":
            metadata.update(model=policy.model_id, model_revision=policy.revision, device="cpu")
        # 使用者的 ROM 不變更；結束時不自動寫入 cartridge RAM。
        emulator = PyBoy(str(rom), window="SDL2" if args.window else "null", sound_emulated=False)
        emulator.set_emulation_speed(0)
        if saved_state:
            with saved_state.open("rb") as stream:
                emulator.load_state(stream)
        if args.video:
            recorder = VideoRecorder(output / "gameplay.mp4")

        def frame_ready(frame):
            nonlocal sampled_frames
            sampled_frames += 1
            if recorder and sampled_frames % 2 == 0:
                recorder.append(frame)

        for index in range(args.steps):
            if time.perf_counter() - started > 600:
                metadata["stop_reason"] = "wall_clock_limit"
                break
            step_start = time.perf_counter()
            state = observe(emulator, args.objective)
            decision = policy.choose(state)
            frames = advance_action(emulator, decision["action"], args.hold_frames, args.settle_frames, frame_ready)
            total_frames += frames
            append_jsonl(output / "steps.jsonl", {"step": index, "state": state, **decision,
                "emulated_frames": frames, "loop_ms": (time.perf_counter() - step_start) * 1000})
        else:
            metadata["stop_reason"] = "action_budget"
        emulator.screen.image.save(output / "last-frame.png")
        metadata["status"] = "completed_demo"
    except Exception as error:
        metadata.update(status="failed", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        if recorder:
            metadata["video"] = recorder.close()
        if emulator:
            emulator.stop(save=False)
        metadata.update(wall_seconds=time.perf_counter() - started, emulated_frames=total_frames)
        write_json(output / "metadata.json", metadata)
        write_json(output / "summary.json", metadata)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))

