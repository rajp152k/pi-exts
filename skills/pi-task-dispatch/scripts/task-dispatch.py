#!/usr/bin/env python3
"""Dispatch bounded, one-shot Pi workers into tmux and retain their handoffs."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

DEFAULT_ROOT = Path.home() / ".pi" / "agent" / "task-runs"
READ_ONLY_TOOLS = "read,grep,find,ls"
RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
TERMINAL_STATES = {"completed", "failed", "cancelled", "lost"}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def fail(message: str) -> NoReturn:
    raise SystemExit(f"task-dispatch: {message}")


def write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_manifest(run_dir: Path) -> dict[str, Any]:
    try:
        return json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read manifest in {run_dir}: {error}")


def update_manifest(run_dir: Path, **updates: Any) -> dict[str, Any]:
    manifest = load_manifest(run_dir)
    manifest.update(updates)
    manifest["updatedAt"] = now()
    write_json(run_dir / "manifest.json", manifest)
    return manifest


def run_tmux(
    arguments: list[str], *, capture: bool = True
) -> subprocess.CompletedProcess[str]:
    if not shutil.which("tmux"):
        fail("tmux is not installed or not on PATH")
    result = subprocess.run(["tmux", *arguments], text=True, capture_output=capture)
    if result.returncode:
        fail(result.stderr.strip() or result.stdout.strip() or "tmux command failed")
    return result


def run_dir_from(value: str) -> Path:
    run_dir = Path(value).expanduser().resolve()
    if not (run_dir / "manifest.json").is_file():
        fail(f"not a task-run directory: {run_dir}")
    return run_dir


def window_exists(window_id: str) -> bool:
    result = subprocess.run(
        ["tmux", "display-message", "-p", "-t", window_id, "#{window_id}"],
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def describe(run_dir: Path) -> dict[str, Any]:
    manifest = load_manifest(run_dir)
    state = manifest["state"]
    if state not in TERMINAL_STATES and not window_exists(manifest["tmux"]["windowId"]):
        manifest = update_manifest(
            run_dir,
            state="lost",
            finishedAt=now(),
            error="tmux window disappeared before worker reported completion",
        )
    return manifest


def print_status(manifest: dict[str, Any]) -> None:
    tmux = manifest["tmux"]
    print(f"id: {manifest['id']}")
    print(f"state: {manifest['state']}")
    print(f"run: {manifest['runDir']}")
    print(f"target: {tmux['session']}:{tmux['windowId']} ({tmux['paneId']})")
    print(f"report: {manifest['reportPath']}")
    if manifest.get("error"):
        print(f"error: {manifest['error']}")


def command_dispatch(args: argparse.Namespace) -> None:
    if not RUN_ID.fullmatch(args.id):
        fail(
            "--id must contain lowercase letters, digits, and single hyphens (max 48 chars)"
        )
    cwd = Path(args.cwd).expanduser().resolve()
    if not cwd.is_dir():
        fail(f"--cwd is not a directory: {cwd}")
    root = Path(args.root).expanduser().resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    run_dir = root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{args.id}"
    if run_dir.exists():
        fail(f"run directory already exists: {run_dir}")
    run_dir.mkdir(mode=0o700)
    task_path = run_dir / "task.md"
    task_path.write_text(args.task.strip() + "\n", encoding="utf-8")
    os.chmod(task_path, 0o600)

    manifest: dict[str, Any] = {
        "id": args.id,
        "state": "starting",
        "createdAt": now(),
        "updatedAt": now(),
        "runDir": str(run_dir),
        "cwd": str(cwd),
        "taskPath": str(task_path),
        "reportPath": str(run_dir / "report.md"),
        "access": "read-only" if args.read_only else "default-tools",
        "tmux": {"session": args.tmux_session},
    }
    write_json(run_dir / "manifest.json", manifest)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "worker",
        "--run-dir",
        str(run_dir),
    ]
    result = run_tmux(
        [
            "new-window",
            "-d",
            "-P",
            "-F",
            "#{window_id},#{pane_id}",
            "-t",
            f"{args.tmux_session}:",
            "-n",
            args.id,
            *command,
        ]
    )
    try:
        window_id, pane_id = result.stdout.strip().split(",", maxsplit=1)
    except ValueError:
        fail(f"unexpected tmux target response: {result.stdout!r}")
    manifest = update_manifest(
        run_dir,
        state="running",
        startedAt=now(),
        tmux={"session": args.tmux_session, "windowId": window_id, "paneId": pane_id},
    )
    (run_dir / "launch-ready").touch()
    print_status(manifest)
    print("next: task-dispatch status --run " + str(run_dir))


def command_worker(args: argparse.Namespace) -> None:
    run_dir = run_dir_from(args.run_dir)
    manifest = load_manifest(run_dir)
    ready = run_dir / "launch-ready"
    for _ in range(100):
        if ready.exists():
            break
        time.sleep(0.05)
    else:
        update_manifest(
            run_dir,
            state="failed",
            finishedAt=now(),
            error="dispatcher did not finish worker setup",
        )
        return
    manifest = load_manifest(run_dir)
    report = Path(manifest["reportPath"])
    task = Path(manifest["taskPath"]).read_text(encoding="utf-8")
    command = ["pi", "--no-session", "--name", manifest["id"], "-p", task]
    if manifest["access"] == "read-only":
        command.extend(["--tools", READ_ONLY_TOOLS])
    try:
        with report.open("w", encoding="utf-8") as output:
            result = subprocess.run(
                command, cwd=manifest["cwd"], stdout=output, stderr=subprocess.STDOUT
            )
        cancelled = (run_dir / "cancel-requested").exists()
        update_manifest(
            run_dir,
            state="cancelled"
            if cancelled
            else ("completed" if result.returncode == 0 else "failed"),
            finishedAt=now(),
            exitCode=result.returncode,
        )
    except Exception as error:  # preserve failure state for a later collector
        update_manifest(run_dir, state="failed", finishedAt=now(), error=str(error))
        raise


def command_status(args: argparse.Namespace) -> None:
    manifest = describe(run_dir_from(args.run_dir))
    print_status(manifest)
    if args.tail:
        report = Path(manifest["reportPath"])
        if report.exists():
            print("\n--- report tail ---")
            print(report.read_text(encoding="utf-8", errors="replace")[-args.tail :])


def command_wait(args: argparse.Namespace) -> None:
    run_dir = run_dir_from(args.run_dir)
    deadline = time.monotonic() + args.timeout
    previous: tuple[str, int] | None = None
    while True:
        manifest = describe(run_dir)
        report = Path(manifest["reportPath"])
        observation = (
            manifest["state"],
            report.stat().st_size if report.exists() else 0,
        )
        if observation != previous:
            print(f"state={observation[0]} report_bytes={observation[1]}")
            previous = observation
        if manifest["state"] in TERMINAL_STATES:
            print_status(manifest)
            return
        if time.monotonic() >= deadline:
            fail(f"timed out after {args.timeout}s; worker remains {manifest['state']}")
        time.sleep(args.interval)


def command_cancel(args: argparse.Namespace) -> None:
    run_dir = run_dir_from(args.run_dir)
    manifest = describe(run_dir)
    if manifest["state"] in TERMINAL_STATES:
        fail(f"worker is already {manifest['state']}")
    (run_dir / "cancel-requested").touch()
    manifest = update_manifest(run_dir, state="cancelling", cancelRequestedAt=now())
    run_tmux(["send-keys", "-t", manifest["tmux"]["paneId"], "C-c"])
    print_status(manifest)


def command_collect(args: argparse.Namespace) -> None:
    manifest = describe(run_dir_from(args.run_dir))
    report = Path(manifest["reportPath"])
    print_status(manifest)
    if not report.exists():
        return
    content = report.read_text(encoding="utf-8", errors="replace")
    if not args.full:
        content = content[: args.max_chars]
    print("\n--- handoff ---")
    print(content)
    if not args.full and len(content) == args.max_chars:
        print(f"\n[truncated; use collect --full to read {report}]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="task-run root (default: ~/.pi/agent/task-runs)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    dispatch = commands.add_parser(
        "dispatch", help="start a one-shot worker in a detached tmux window"
    )
    dispatch.add_argument("--id", required=True)
    dispatch.add_argument("--tmux-session", required=True)
    dispatch.add_argument("--cwd", required=True)
    dispatch.add_argument("--task", required=True)
    dispatch.add_argument(
        "--read-only", action="store_true", help="allow only read, grep, find, and ls"
    )
    dispatch.set_defaults(handler=command_dispatch)

    for name, handler, help_text in [
        ("status", command_status, "show worker state"),
        ("wait", command_wait, "bounded polling until completion"),
        ("cancel", command_cancel, "send Ctrl-C to a worker"),
        ("collect", command_collect, "print a worker handoff"),
    ]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--run", dest="run_dir", required=True)
        command.set_defaults(handler=handler)
        if name == "status":
            command.add_argument(
                "--tail",
                type=int,
                default=0,
                help="include this many trailing report characters",
            )
        if name == "wait":
            command.add_argument(
                "--interval", type=float, default=5, help="poll interval in seconds"
            )
            command.add_argument(
                "--timeout", type=float, required=True, help="maximum wait in seconds"
            )
        if name == "collect":
            command.add_argument("--max-chars", type=int, default=12000)
            command.add_argument("--full", action="store_true")

    worker = commands.add_parser("worker", help=argparse.SUPPRESS)
    worker.add_argument("--run-dir", required=True)
    worker.set_defaults(handler=command_worker)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
