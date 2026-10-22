"""模型權重固定 revision、CPU 執行與控制動作介面。"""
from __future__ import annotations

import json
import random
import time
from typing import Any

from .core import ACTIONS, validate_action


class LayaPolicy:
    def __init__(self, model: str = "convaiinnovations/laya", revision: str = "main", threads: int = 4):
        import laya
        import torch
        from huggingface_hub import HfApi, snapshot_download

        torch.set_num_threads(threads)
        started = time.perf_counter()
        # 公開模型無須登入，先將可移動的 main 解析成固定 commit。
        info = HfApi().model_info(model, revision=revision, token=False)
        self.revision = info.sha
        self.model_id = model
        local_model = snapshot_download(model, revision=self.revision, token=False,
            allow_patterns=["*.json", "*.safetensors", "tokenizer/*"], ignore_patterns=["*/*/*"])
        self.agent = laya.load(local_model, device="cpu")
        self.load_seconds = time.perf_counter() - started
        self.threads = threads

    def choose(self, state: dict[str, Any]) -> dict[str, Any]:
        questions = {"action": {"type": "choice",
            "instructions": "Choose the next button action that best advances the stated objective. Use the supplied state only.",
            "criteria": {action.key: action.description for action in ACTIONS}}}
        text = json.dumps(state, ensure_ascii=True, separators=(",", ":"))
        started = time.perf_counter()
        result = self.agent.predict(text, questions)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if result.get("usage", {}).get("truncated"):
            raise ValueError("模型輸入遭截斷，停止執行動作；請縮短觀測或調整上下文預算")
        key = result["answers"]["action"]["choice"]
        validate_action(key)
        return {"action": key, "model_ms": elapsed_ms, "raw": result}


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

