"""模型權重固定 revision、CPU 執行與控制動作介面。"""
from __future__ import annotations

import json
import random
import time
from typing import Any

from .core import ACTIONS, validate_action

PINNED_REVISION = "7b928d828b7b0e022f929d9bd2e44165aa270148"


class LayaPolicy:
    def __init__(self, model: str = "convaiinnovations/laya", revision: str = "main", threads: int = 4, offline: bool = False):
        import laya
        import torch
        from huggingface_hub import HfApi, snapshot_download

        torch.set_num_threads(threads)
        started = time.perf_counter()
        # 公開模型無須登入，先將可移動的 main 解析成固定 commit。
        if offline and revision == "main":
            raise ValueError("離線模式須指定固定的模型 revision")
        self.revision = revision if offline else HfApi().model_info(model, revision=revision, token=False).sha
        self.model_id = model
        local_model = snapshot_download(model, revision=self.revision, token=False,
            allow_patterns=["*.json", "*.safetensors", "tokenizer/*"], ignore_patterns=["*/*/*"], local_files_only=offline)
        self.agent = laya.load(local_model, device="cpu")
        self.load_seconds = time.perf_counter() - started
        self.threads = threads

    def choose_options(self, state: dict[str, Any], instructions: str, criteria: dict[str, str]) -> dict[str, Any]:
        if not criteria:
            raise ValueError("候選動作不能為空")
        questions = {"action": {"type": "choice",
            "instructions": instructions, "criteria": criteria}}
        text = json.dumps(state, ensure_ascii=True, separators=(",", ":"))
        started = time.perf_counter()
        result = self.agent.predict(text, questions)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if result.get("usage", {}).get("truncated"):
            raise ValueError("模型輸入遭截斷，停止執行動作；請縮短觀測或調整上下文預算")
        key = result["answers"]["action"]["choice"]
        if key not in criteria:
            raise ValueError("模型回傳不在候選集合內的動作")
        return {"action": key, "model_ms": elapsed_ms, "raw": result}

    def choose(self, state: dict[str, Any]) -> dict[str, Any]:
        decision = self.choose_options(state,
            "Choose the next button action that best advances the stated objective. Use the supplied state only.",
            {action.key: action.description for action in ACTIONS})
        validate_action(decision["action"])
        return decision


class RandomPolicy:
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def choose(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"action": self.rng.choice(ACTIONS).key, "model_ms": 0.0}


class SimpleRulePolicy:
    """明示的控制基線，不宣稱具備遊戲解題能力。"""
    def choose(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("control_hint") in {action.key for action in ACTIONS}:
            key = state["control_hint"]
        elif state.get("phase") == "animation":
            key = "wait"
        elif state.get("phase") in {"dialogue", "battle"}:
            key = "a"
        else:
            key = "up"
        return {"action": key, "model_ms": 0.0}

