"""PyBoy 有限步控制與遊戲時間錄影；任務成功評估尚待 ROM 校準。"""
from __future__ import annotations

import json
import hashlib
import time
from concurrent.futures import Future
from pathlib import Path
from threading import Thread

from .core import append_jsonl, parse_rom_header, sha256_file, utc_now, validate_action, write_json


RUN_TIME_LIMIT_SECONDS = 60


class WindowClosed(RuntimeError):
    """使用者關閉即時視窗，屬正常停止。"""


class TimeBudgetReached(RuntimeError):
    pass


class StrategyReviewRequired(RuntimeError):
    pass


class MilestoneReached(RuntimeError):
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


def observe(pyboy, objective: str, player_name: str = "KEVIN", previous_actions=(), opening_route=False, starter="BULBASAUR", route_stage="starter") -> dict:
    from .observation import read_visible_text, opening_context
    from .progress import read_progress

    text = read_visible_text(pyboy)
    state = {"objective": objective, "phase": "unclassified", "input_method": "emulator_state",
             "observation_profile": text["profile"], "visible_text_candidates": text["lines"],
             "observation_warnings": text["warnings"], "frame": pyboy.frame_count}
    state.update(opening_context(text, objective, player_name))
    progress = read_progress(pyboy)
    state["progress"] = progress
    state["party_summary"] = [{key: mon[key] for key in ("species", "level", "hp", "max_hp")}
                              for mon in progress["party"]]
    if opening_route:
        from .navigation import read_location, opening_waypoint, collision_direction, verified_down_ledge
        state["location"] = read_location(pyboy)
        if route_stage in {"lab_rival", "to_parcel", "deliver_parcel", "team_resupply", "team_capture"}:
            from .battle import read_battle_state, battle_context, learning_context
            state["battle_state"] = read_battle_state(pyboy)
            context = learning_context(text, progress["party"])
            if context is None and "NICKNAME" not in " ".join(text["lines"]).upper():
                context = battle_context(text, state["battle_state"], progress["party"], progress["inventory"],
                                         capture_focus=route_stage == "team_capture")
            if context:
                state.update(context)
            elif state["battle_state"]["active"] is None:
                state.update(phase="unknown_battle_state", objective="Wait.", available_actions=["wait", "b"])
        if (route_stage in {"team_resupply", "team_capture"} and state["location"]["map_id"] == 42
                and state.get("battle_state", {}).get("active") is False):
            from .shopping import shopping_context
            context = shopping_context(text, progress["inventory"], progress["money"])
            if context:
                state.update(context)
        if state["phase"] == "unclassified" and progress["player_name_raw"] == player_name:
            waypoint = opening_waypoint(state["location"], previous_actions,
                                        progress["story_event_bits"], bool(progress["party"]), starter, route_stage,
                                        any(mon["hp"] < mon["max_hp"] for mon in progress["party"]))
            if route_stage == "team_capture":
                from .capture_route import team_waypoint, visible_grass_world
                from .shopping import ball_count
                waypoint = team_waypoint(state["location"], progress["story_event_bits"], progress["party"],
                                         ball_count(progress["inventory"]), previous_actions,
                                         visible_grass_world(pyboy, state["location"]) if state["location"]["map_id"] == 33 else ())
            if waypoint:
                state.update(waypoint)
                state["phase"] = "overworld"
                state["phase_source"] = "local opening waypoint planner; not model-discovered navigation"
                if (waypoint["objective"].startswith("Move ") and waypoint["controller_waypoint"]
                        and not waypoint["goal"].startswith("face_")):
                    sprites = [pyboy.get_sprite(index) for index in range(4)]
                    sx, sy = min(s.x for s in sprites), min(s.y for s in sprites)
                    # 本次ROM已以實際(5,6)／四個sprite及碰撞圖校準；人物圖像比站立格高4px。
                    if sx % 16 == 0 and (sy + 4) % 16 == 0:
                        collision = pyboy.game_wrapper.game_area_collision()[::2, ::2].tolist()
                        hint = collision_direction(collision, [sx // 16, (sy + 4) // 16],
                                                   state["location"], waypoint["controller_waypoint"])
                        if hint:
                            state["objective"] = f"Move {hint['direction'].upper()}."
                            state["collision_path_hint"] = hint
                        else:
                            target = waypoint["controller_waypoint"]
                            ledge = None
                            if (route_stage == "deliver_parcel" and state["location"]["map_id"] == 12
                                    and target["y"] > state["location"]["y"]):
                                # PyBoy 的碰撞格不含矮坡方向邊；此私有讀取 helper 與固定 PyBoy 版本一起記錄。
                                tiles = pyboy.game_wrapper._get_screen_background_tilemap()[1::2, ::2]
                                ledge = verified_down_ledge(collision, (tiles % 256).tolist(), [sx // 16, (sy + 4) // 16])
                            distance = abs(state["location"]["x"] - target["x"]) + abs(state["location"]["y"] - target["y"])
                            if ledge:
                                state["objective"] = "Move DOWN."
                                state["ledge_jump_hint"] = ledge
                            elif distance != 1 or waypoint["goal"] not in {"enter_1f_exit", "step_out_house", "reach_2f_stairs_y", "step_out_lab", "leave_pallet_north", "route1_north", "enter_viridian_mart", "enter_viridian_center", "step_out_center", "step_out_mart", "leave_viridian_south", "route1_south", "enter_oaks_lab", "leave_viridian_west", "return_route22_east"}:
                                state["objective"] = "Wait for a verified traversable path."
                                state["available_actions"] = ["wait", "b"]
                                state["navigation_warning"] = "No closer reachable collision-grid waypoint."
    state["screen_sha256"] = hashlib.sha256(pyboy.screen.ndarray.tobytes()).hexdigest()
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
    from .observation import PROFILE
    from .runtime import enable_offline_runtime
    from .progress import FULL_MISSION_OBJECTIVE, FULL_MISSION_MILESTONES

    if args.steps < 1 or args.steps > 300:
        raise ValueError("首輪展示的 steps 必須介於 1 至 300")
    if args.hold_frames < 1 or args.settle_frames < 0:
        raise ValueError("按鍵幀數設定不正確")
    args.player_name = args.player_name.upper()
    if not args.player_name.isascii() or not args.player_name.isalpha() or not 1 <= len(args.player_name) <= 7:
        raise ValueError("玩家姓名須為 1–7 個英文字母")
    if not 1 <= args.scale <= 8 or not 1 <= args.threads <= 32 or not 0 <= args.boot_frames <= 600:
        raise ValueError("scale 須為 1–8、threads 為 1–32、boot-frames 為 0–600")
    rom = Path(args.rom).resolve(strict=True)
    header = parse_rom_header(rom)
    if args.opening_route and header["sha256"] != "5ca7ba01642a3b27b0cc0b5349b52792795b62d3ed977e98a09390659af96b7b":
        raise ValueError("實驗性開局路線目前只接受已核對的紅版 SHA")
    strategy_path = Path(args.strategy_file).resolve(strict=True) if args.strategy_file else None
    saved_state = Path(args.state).resolve(strict=True) if args.state else None
    output = Path(args.output)
    if output.exists():
        raise ValueError("輸出目錄已存在，請指定新的 run 目錄")
    if args.offline:
        enable_offline_runtime()
    output.mkdir(parents=True)
    metadata = {**environment(), "recorded_at": utc_now(), "kind": "pokemon_control_demo",
        "status": "running", "policy": args.policy, "seed": args.seed, "rom": header,
        "state_sha256": sha256_file(saved_state) if saved_state else None,
        "max_steps": args.steps, "hold_frames": args.hold_frames, "settle_frames": args.settle_frames,
        "max_wall_seconds": RUN_TIME_LIMIT_SECONDS,
        "window": args.window, "scale": args.scale, "boot_frames": args.boot_frames,
        "offline": args.offline, "threads": args.threads,
        "waiting_behavior": "pause emulation and pump SDL events during model loading/inference",
        "desktop_foreground_verified": False,
        "observation_profile": PROFILE, "task_success": None,
        "decision_backend": "local_laya_cpu" if args.policy == "laya" else args.policy,
        "cloud_model_fallback": False, "python_network_denied": args.offline,
        "mission_objective": FULL_MISSION_OBJECTIVE, "mission_milestones": FULL_MISSION_MILESTONES,
        "requested_player_name": args.player_name,
        "opening_route": args.opening_route, "strategy_sha256_at_start": sha256_file(strategy_path) if strategy_path else None,
        "phase_hint_source": "local visible text/layout heuristics; not a validated whole-game planner",
        "limitation": "Limited button-control demo; no validated navigation/dialogue/battle success evaluator."}
    write_json(output / "metadata.json", metadata)
    emulator = recorder = None
    sampled_frames = 0
    started = time.perf_counter()
    deadline = started + RUN_TIME_LIMIT_SECONDS

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
        previous_actions = []
        screenshot_dir = output / "frames"
        screenshot_dir.mkdir()
        for index in range(args.steps):
            if time.perf_counter() >= deadline:
                raise TimeBudgetReached("已達執行時間上限")
            step_start = time.perf_counter()
            strategy_bytes = strategy_path.read_bytes() if strategy_path else b"{}"
            strategy = json.loads(strategy_bytes)
            starter = strategy.get("starter", "BULBASAUR")
            if starter not in {"BULBASAUR", "SQUIRTLE", "CHARMANDER"}:
                raise ValueError("策略檔的 starter 不在允許集合")
            route_stage = strategy.get("stage", "starter")
            if route_stage not in {"starter", "lab_rival", "to_parcel", "deliver_parcel", "team_resupply", "team_capture"}:
                raise ValueError("策略檔的 stage 不在允許集合")
            state = observe(emulator, args.objective, args.player_name, previous_actions, args.opening_route, starter, route_stage)
            state["strategy_starter"] = starter
            state["strategy_stage"] = route_stage
            state["strategy_sha256"] = hashlib.sha256(strategy_bytes).hexdigest()
            state["previous_actions"] = previous_actions[-3:]
            emulator.screen.image.save(screenshot_dir / f"{index:04d}-before.png")
            if state["phase"] == "strategy_review":
                write_json(output / "strategy-review.json", state)
                raise StrategyReviewRequired(state.get("review_reason", "unknown_strategy_context"))
            if state.get("goal") == "first_team_capture_complete":
                write_json(output / "capture-milestone.json", state)
                raise MilestoneReached("已驗證首隻目標加入隊伍")
            decision = model_task(lambda: policy.choose(state))
            frames = advance_action(emulator, decision["action"], args.hold_frames, args.settle_frames, frame_ready)
            emulator.screen.image.save(screenshot_dir / f"{index:04d}-after.png")
            previous_actions.append(decision["action"])
            append_jsonl(output / "steps.jsonl", {"step": index, "state": state, **decision,
                "emulated_frames": frames, "decision_backend": metadata["decision_backend"],
                "after_screen_sha256": hashlib.sha256(emulator.screen.ndarray.tobytes()).hexdigest(),
                "loop_ms": (time.perf_counter() - step_start) * 1000})
            append_jsonl(output / "progress.jsonl", {"step": index, "frame": state["frame"],
                         "screen_sha256": state["screen_sha256"], **state["progress"]})
            # 本次 run 的本機 checkpoint；不覆寫來源存檔，不納入 Git。
            temporary_state = output / "checkpoint.state.tmp"
            with temporary_state.open("wb") as stream:
                emulator.save_state(stream)
            temporary_state.replace(output / "checkpoint.state")
            metadata.update(completed_steps=index + 1, last_action=decision["action"],
                            emulated_frames=sampled_frames)
            write_json(output / "metadata.json", metadata)
        else:
            metadata["stop_reason"] = "action_budget"
        emulator.screen.image.save(output / "last-frame.png")
        metadata["status"] = "completed_demo"
    except (WindowClosed, TimeBudgetReached, StrategyReviewRequired, MilestoneReached, KeyboardInterrupt) as error:
        metadata.update(status="stopped", stop_reason="window_closed" if isinstance(error, WindowClosed)
                        else "wall_clock_limit" if isinstance(error, TimeBudgetReached)
                        else "strategy_review_required" if isinstance(error, StrategyReviewRequired)
                        else "capture_milestone" if isinstance(error, MilestoneReached) else "keyboard_interrupt")
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
                emulator.screen.image.save(output / "last-frame.png")
                with (output / "final.state").open("wb") as stream:
                    emulator.save_state(stream)
            except Exception as error:
                cleanup_errors.append({"resource": "checkpoint", "type": type(error).__name__, "error": str(error)})
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

