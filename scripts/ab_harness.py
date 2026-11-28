# -*- coding: utf-8 -*-
"""HaijunBot prompt/shell A/B baseline for the same model and same task.

Usage:
    .venv/bin/python scripts/ab_harness.py            # run all tasks x all profiles
    .venv/bin/python scripts/ab_harness.py --only mathx

Behavior: for each task, run the CodeAgent of two profiles (non-interactive) in a temporary git repository,
record the final return, model message count/estimated tokens, and write a JSON report to .ab_harness_out/.

Note: uses the currently configured llm_group; one run actually calls the LLM (has cost).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Per task: starter file (relative to the task repo root) + task description (provides in-repo paths)
STARTER = {
    "mathx.py": "def add(a, b):\n    return a - b  # bug: should add\n",
}
TASKS = {
    "mathx": {
        "files": {"mathx.py": STARTER["mathx.py"]},
        "prompt": (
            "Read mathx.py in the repository root. It should provide an add(a, b) that returns the sum of two numbers,"
            "but the current implementation has a bug (it returns the difference instead of the sum). Fix the function, and write a test using pytest"
            "that verifies add(1,2)==3, add(0,0)==0, add(-1,1)==0, and make pytest pass completely."
            "Do not change anything else; commit when done."
        ),
    },
}

# profile = CodeAgent construction/switch differences (quick vs current default)
PROFILES = {
    # current: use the default shell (classification/rule auto-loading/methodology all per configuration)
    "current": {"quick_mode": False, "disable_review": True},
    # lean: skip the HaijunBot shell's heavy flows such as rules/classification/methodology, as close as possible to a "light shell"
    "lean": {"quick_mode": True, "disable_review": True},
}


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _load_global_config() -> None:
    """Load the user config (~/.haijunbot/config.yaml or $HAIJUNBOT_CONFIG_FILE) into the global config.

    After a direct import, GLOBAL_CONFIG_DATA is empty, so although llm_group is set,
    llms/llm_groups are undefined and the platform falls back to the default api.openai.com/gpt-5.
    Also applies the ENV entries in the config (such as http_proxy) as process environment variables, consistent with haijunbot's own behavior.
    """
    import yaml as _yaml

    from haijunbot.haijunbot_utils.config import set_global_config_data

    path = os.environ.get("HAIJUNBOT_CONFIG_FILE") or str(
        Path.home() / ".haijunbot" / "config.yaml"
    )
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        data = _yaml.safe_load(f) or {}
    set_global_config_data(data)
    for key, value in (data.get("ENV") or {}).items():
        os.environ.setdefault(str(key), str(value))


def _make_repo(task_dir: Path, files: dict) -> None:
    task_dir.mkdir(parents=True, exist_ok=True)
    _git(task_dir, "init", "-q")
    _git(task_dir, "config", "user.email", "haijunbot@ab.local")
    _git(task_dir, "config", "user.name", "HaijunBot AB")
    for name, content in files.items():
        p = task_dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    _git(task_dir, "add", ".")
    _git(task_dir, "commit", "-q", "-m", "init")


def _run_one(
    profile: str, task_key: str, info: dict, out_dir: Path, group: str
) -> dict:
    record = {"profile": profile, "task": task_key, "started": time.time()}
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory(prefix="haijunbot_ab_") as tmp:
        repo = Path(tmp) / "repo"
        _make_repo(repo, info["files"])
        os.chdir(repo)
        try:
            from haijunbot.haijunbot_code_agent.code_agent import CodeAgent
            from haijunbot.haijunbot_utils.config import set_llm_group

            set_llm_group(group)
            kw = dict(PROFILES[profile])
            ag = CodeAgent(
                non_interactive=True,
                need_summary=False,
                **kw,
            )
            # Key: only set_non_interactive(True) also turns on things like auto_complete,
            # ensuring it does not return to "waiting for user input" after finishing, otherwise it would hang waiting on stdin.
            ag.set_non_interactive(True)
            result = ag.run(info["prompt"])
            record["return_type"] = type(result).__name__
            record["return_len"] = len(result) if isinstance(result, str) else -1
            record["result_head"] = (
                (result[:500] + "...") if isinstance(result, str) and len(result) > 500 else result
            )
            try:
                msgs = ag.model.get_messages()
                record["message_count"] = len(msgs)
                chars = sum(
                    len(str(m.get("content", ""))) if isinstance(m, dict) else 0
                    for m in msgs
                )
                record["history_chars"] = chars
            except Exception as e:
                record["history_err"] = str(e)
            try:
                out = subprocess.run(
                    ["git", "-C", str(repo), "log", "--oneline", "-n", "5"],
                    capture_output=True, text=True,
                )
                record["commits"] = out.stdout.strip()
            except Exception as e:
                record["git_err"] = str(e)
        except Exception as e:
            import traceback
            record["error"] = f"{type(e).__name__}: {e}"
            record["traceback"] = traceback.format_exc().splitlines()[-15:]
        finally:
            os.chdir(cwd)
    record["elapsed_s"] = round(time.time() - record.pop("started"), 1)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{task_key}__{profile}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="run only a specific task key")
    ap.add_argument("--profile", default=None, help="run only a specific profile (current/lean)")
    ap.add_argument("--group", default="ds_zn", help="llm_group (must be reachable), defaults to ds_zn=scnet")
    args = ap.parse_args()
    _load_global_config()
    out_dir = ROOT / ".ab_harness_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for task_key, info in TASKS.items():
        if args.only and task_key != args.only:
            continue
        for profile in PROFILES:
            if args.profile and profile != args.profile:
                continue
            r = _run_one(profile, task_key, info, out_dir, group=args.group)
            summary.append(r)
            print(
                f"[{profile}] {task_key}: "
                f"len={r.get('return_len')} msgs={r.get('message_count')} "
                f"err={'YES' if r.get('error') else 'NO'} ({r.get('elapsed_s')}s)"
            )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("wrote .ab_harness_out/summary.json")


if __name__ == "__main__":
    main()
