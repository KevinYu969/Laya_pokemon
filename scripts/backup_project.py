"""將指定筆記匯出為公開備份，再以一般 fast-forward push 同步專案。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "https://github.com/KevinYu969/Laya_pokemon"
TOP_FILES = {"README.md", "pyproject.toml", "requirements-lock.txt", ".gitignore", ".gitattributes"}
TOP_DIRS = {"src", "scripts", "tests", "docs", "results", ".github"}
EXTENSIONS = {".md", ".py", ".ps1", ".toml", ".json", ".jsonl", ".csv", ".txt", ".yml", ".yaml", ".svg"}
SECRET = re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|hf_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9_-]{25,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)")
USER_PATH = re.compile(r"[A-Za-z]:(?:\\{1,2}|/)Users(?:\\{1,2}|/)[^\\/\s`\"'<>]+", re.IGNORECASE)


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if check and result.returncode:
        raise RuntimeError(f"git {args[0]} 失敗；請檢查認證、分支或遠端是否已有更新。")
    return result


def sanitize(text: str, redactions: dict[str, str] | None = None) -> str:
    for original, replacement in sorted((redactions or {}).items(), key=lambda pair: len(pair[0]), reverse=True):
        text = text.replace(original, replacement).replace(original.replace("\\", "/"), replacement)
    text = USER_PATH.sub("<USER_HOME>", text)
    links = {"laya-pokemon-plan-and-log": "experiment-plan-and-log.md", "laya-pokemon-experiment": "preparation.md"}
    def wiki(match):
        target, _, label = match.group(1).partition("|")
        return f"[{label or target}]({links[target]})" if target in links else (label or target)
    text = re.sub(r"\[\[([^\]]+)\]\]", wiki, text)
    return text


def validate_file(relative: str, data: bytes) -> None:
    path = Path(relative)
    if relative not in TOP_FILES and (not path.parts or path.parts[0] not in TOP_DIRS):
        raise ValueError(f"公開備份白名單外的檔案：{relative}")
    if path.suffix.lower() not in EXTENSIONS and relative not in TOP_FILES:
        raise ValueError(f"公開備份不接受此檔案類型：{relative}")
    if path.name.lower().startswith(".env") or any(part.lower() in {"roms", "saves", "models", "private", ".local"} for part in path.parts):
        raise ValueError(f"私人資料不得納入公開備份：{relative}")
    if len(data) > 5 * 1024 * 1024:
        raise ValueError(f"檔案超過 5MiB，請另行審查：{relative}")
    text = data.decode("utf-8-sig")
    if SECRET.search(text):
        raise ValueError(f"疑似憑證，停止備份：{relative}")
    if USER_PATH.search(text):
        raise ValueError(f"含個人完整路徑，停止備份：{relative}")
    machine = os.environ.get("COMPUTERNAME", "")
    if machine and machine in text:
        raise ValueError(f"含本機識別，停止備份：{relative}")


def export_notes() -> None:
    config_path = ROOT / ".local" / "backup-config.json"
    if not config_path.exists():
        return
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    machine = os.environ.get("COMPUTERNAME", "")
    if not machine or machine not in config.get("allowed_machines", []):
        raise RuntimeError("無法確認為設定允許的私人設備，停止讀取筆記")
    allowed_sources = {"laya-pokemon-plan-and-log.md", "laya-pokemon-experiment.md"}
    allowed_destinations = {"docs/experiment-plan-and-log.md", "docs/preparation.md"}
    for item in config["notes"]:
        source = Path(item["source"]).resolve(strict=True)
        destination = item["destination"]
        if source.name not in allowed_sources or destination not in allowed_destinations:
            raise ValueError("筆記來源或目的地不在固定白名單")
        raw = source.read_text(encoding="utf-8-sig")
        generated = sanitize(raw, config.get("redactions", {}))
        content = "<!-- 自動匯出的公開備份；請於私人主檔更新，再重新匯出。 -->\n" + generated
        validate_file(destination, content.encode("utf-8"))
        target = ROOT / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")


def validate_tree() -> list[str]:
    files = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").stdout.split("\0")
    names = sorted(set(name for name in files if name))
    for name in names:
        path = ROOT / name
        if path.is_file():
            validate_file(name, path.read_bytes())
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description="Laya 專案公開備份")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--export-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        print(json.dumps({"validated_files": len(validate_tree())}))
        return
    lock_dir = ROOT / ".local"
    lock_dir.mkdir(exist_ok=True)
    lock = lock_dir / "backup.lock"
    # 排程與手動執行不可同時匯出／提交。
    with lock.open("x", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))
    try:
        branch = git("branch", "--show-current").stdout.strip()
        remote = git("remote", "get-url", "origin").stdout.strip().removesuffix(".git").rstrip("/")
        if branch != "main" or remote != REMOTE:
            raise RuntimeError("備份分支或遠端與設定不符，停止執行")
        export_notes()
        names = validate_tree()
        if not args.export_only:
            git("add", "--", *names)
            changed = git("diff", "--cached", "--quiet", check=False)
            if changed.returncode == 1:
                git("commit", "-m", "codex: back up Laya Pokemon project and experiment records")
            elif changed.returncode:
                raise RuntimeError("無法檢查暫存變更")
            if args.push:
                git("push", "origin", "HEAD:refs/heads/main")
                local = git("rev-parse", "HEAD").stdout.strip()
                remote_head = git("ls-remote", "origin", "refs/heads/main").stdout.split()[0]
                if local != remote_head:
                    raise RuntimeError("遠端提交驗證未通過")
        print(json.dumps({"validated_files": len(names), "pushed": args.push and not args.export_only,
                          "head": git("rev-parse", "HEAD").stdout.strip()}))
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
