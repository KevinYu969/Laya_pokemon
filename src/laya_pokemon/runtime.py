"""單一遊戲程序的離線限制，不修改作業系統或其他應用程式。"""
import os
import sys


def enable_offline_runtime() -> None:
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")

    def deny_network(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            raise RuntimeError("本機離線模式禁止 Python 網路連線；不使用雲端模型備援")

    sys.addaudithook(deny_network)
