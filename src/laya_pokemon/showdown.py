"""Laya 真實選招，官方 Showdown 引擎判定，產生可播放回放。"""
from __future__ import annotations

import html
import json
import subprocess
import time
from pathlib import Path

from .core import append_jsonl, sha256_file, utc_now, write_json
from .policy import LayaPolicy, PINNED_REVISION


def replay_page(log: str, summary: dict, decisions: list[dict]) -> str:
    rows = "".join(f"<tr><td>{row['turn']}</td><td>{html.escape(row['move_name'])}</td>"
                   f"<td>{row['model_ms']:.0f} ms</td></tr>" for row in decisions)
    safe_log = log.replace("<", "\\u003c")
    return f'''<!doctype html>
<html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Laya 真實對戰回放｜Pokémon Showdown</title>
<style>body{{font:16px system-ui;background:#edf2f7;color:#172c43;margin:0;padding:24px}}
header,section{{max-width:1180px;margin:0 auto 18px;background:white;padding:20px;box-sizing:border-box;border-radius:12px}}
h1{{font-size:24px;margin:0 0 10px}}p{{line-height:1.7}}td,th{{padding:8px 20px;text-align:left}}.tag{{font-weight:bold;color:#17644e}}</style>
<header><p class="tag">Laya CPU × 官方 Pokémon Showdown 引擎</p><h1>第一場真實選招與對戰回放</h1>
<p>固定入門情境：20 級皮卡丘對 20 級傑尼龜。Laya 選擇招式，Showdown 判定傷害與勝負；對手採固定種子的隨機合法招式。</p>
<p><strong>引擎結果：{html.escape(str(summary.get('winner') or '未結束'))}</strong> · {summary['decisions']} 次模型決策 · seed {summary['seed']}</p>
<p>這是對戰模擬器回放，尚未完成紅／藍版主線冒險；入門情境有電系對水系的屬性優勢，不作通用勝率結論。</p></header>
<div class="wrapper replay-wrapper" style="max-width:1180px;margin:0 auto"><div class="battle"></div><div class="battle-log"></div><div class="replay-controls"></div><div class="replay-controls-2"></div></div>
<script type="text/plain" class="battle-log-data">{safe_log}</script>
<script src="https://play.pokemonshowdown.com/js/replay-embed.js"></script>
<section style="margin-top:24px"><h2>Laya 實際決策</h2><table><thead><tr><th>回合</th><th>選招</th><th>CPU 推論</th></tr></thead><tbody>{rows}</tbody></table>
<p>原始檔：<a href="steps.jsonl">逐回合決策</a> · <a href="battle.log">引擎回放紀錄</a> · <a href="summary.json">結果摘要</a></p></section>
<script>window.addEventListener('load',()=>{{let n=0;const t=setInterval(()=>{{const b=document.querySelector('button[data-action="play"]');if(b){{b.click();clearInterval(t)}}else if(++n>100)clearInterval(t)}},200)}});</script></html>'''


def run_showdown(args) -> None:
    from .cli import environment

    root = Path(__file__).resolve().parents[2]
    output = Path(args.output)
    if output.exists():
        raise ValueError("輸出目錄已存在，請使用新的 run 目錄")
    if not (root / ".local/showdown/node_modules/pokemon-showdown").is_dir():
        raise ValueError("請先安裝 scripts/showdown/package.json 所記錄的 Showdown 引擎")
    output.mkdir(parents=True)
    meta = {**environment(), "recorded_at": utc_now(), "kind": "showdown_real_battle",
            "status": "running", "seed": args.seed, "scenario": "fixed-pikachu-vs-squirtle-level20",
            "limitation": "An introductory fixed 1v1 battle with type advantage, not GB story progress or general win rate.",
            "engine_wrapper_sha256": sha256_file(root / "scripts/showdown/engine.cjs")}
    write_json(output / "metadata.json", meta)
    engine = None
    engine_log = (output / "engine-stderr.log").open("w", encoding="utf-8")
    started = time.perf_counter()
    decisions = []
    try:
        policy = LayaPolicy(revision=PINNED_REVISION, offline=True)
        meta.update(model=policy.model_id, model_revision=policy.revision, device="cpu", offline=True)
        engine = subprocess.Popen(["node", str(root / "scripts/showdown/engine.cjs")],
            cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=engine_log,
            text=True, encoding="utf-8", bufsize=1)

        def rpc(message):
            engine.stdin.write(json.dumps(message) + "\n")
            engine.stdin.flush()
            line = engine.stdout.readline()
            if not line:
                raise RuntimeError("Showdown 引擎中止，請查 engine-stderr.log")
            result = json.loads(line)
            if "error" in result:
                raise RuntimeError(result["error"])
            return result

        state = rpc({"command": "start", "seed": args.seed})
        write_json(output / "initial.json", state)
        meta["showdown_version"] = state["showdown_version"]
        while not state["ended"] and len(decisions) < args.max_turns:
            choices = {move["id"]: f"{move['name']}: {move['type']} type; {move['category']}; power {move['power']}; accuracy {move['accuracy']}; PP {move['pp']}"
                       for move in state["choices"]}
            decision = policy.choose_options(state["observation"],
                "Choose the legal move that best helps win this Pokemon battle. Consider type effectiveness, damage and remaining HP.", choices)
            selected = next(move for move in state["choices"] if move["id"] == decision["action"])
            next_state = rpc({"command": "step", "choice": decision["action"]})
            row = {"turn": state["turn"], "before": state, "after": next_state,
                   "move_name": selected["name"], **decision}
            append_jsonl(output / "steps.jsonl", row)
            decisions.append(row)
            print(f"Laya 回合 {state['turn']}：{selected['name']}，CPU {decision['model_ms']:.0f}ms", flush=True)
            state = next_state
        replay = rpc({"command": "replay"})["log"]
        (output / "battle.log").write_text(replay, encoding="utf-8")
        meta.update(status="completed" if state["ended"] else "turn_limit", winner=state["winner"],
                    decisions=len(decisions), ended=state["ended"], task_success=state["winner"] == "Laya CPU",
                    wall_seconds=time.perf_counter() - started)
        write_json(output / "summary.json", meta)
        (output / "replay.html").write_text(replay_page(replay, meta, decisions), encoding="utf-8")
        print(json.dumps(meta, ensure_ascii=False, indent=2))
    except Exception as error:
        meta.update(status="failed", error_type=type(error).__name__, error=str(error))
        write_json(output / "failure.json", meta)
        raise
    finally:
        if engine:
            engine.stdin.close()
            try:
                engine.wait(timeout=5)
            except subprocess.TimeoutExpired:
                engine.kill()
                engine.wait()
        engine_log.close()
        write_json(output / "metadata.json", meta)
