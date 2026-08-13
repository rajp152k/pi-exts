#!/usr/bin/env python3
"""Dispatch bounded Pi workers and orchestrate observable tmux-backed workflows."""

from __future__ import annotations

import argparse
import curses
import json
import os
import re
import select
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

DEFAULT_ROOT = Path.home() / ".pi" / "agent" / "task-runs"
DEFAULT_DATABASE = Path.home() / ".pi" / "agent" / "workflows.db"
READ_ONLY_TOOLS = "read,grep,find,ls"
RPC_CANCEL_GRACE = 5.0
SCHEDULER_LEASE_SECONDS = 300.0
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
    print(
        f"id: {manifest['id']}\nstate: {manifest['state']}\nrun: {manifest['runDir']}"
    )
    print(
        f"target: {tmux['session']}:{tmux['windowId']} ({tmux['paneId']})\nreport: {manifest['reportPath']}"
    )
    if manifest.get("error"):
        print(f"error: {manifest['error']}")


def launch_worker(
    *,
    task_id: str,
    session: str,
    cwd: Path,
    task: str,
    read_only: bool,
    root: Path,
    workflow: dict[str, str] | None = None,
    run_dir: Path | None = None,
) -> Path:
    if not RUN_ID.fullmatch(task_id):
        fail(
            "task id must contain lowercase letters, digits, and single hyphens (max 48 chars)"
        )
    if not cwd.is_dir():
        fail(f"cwd is not a directory: {cwd}")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    run_dir = run_dir or (
        root
        / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{task_id}-{uuid.uuid4().hex[:6]}"
    )
    run_dir.mkdir(mode=0o700, exist_ok=True)
    task_path = run_dir / "task.md"
    task_path.write_text(task.strip() + "\n", encoding="utf-8")
    os.chmod(task_path, 0o600)
    manifest: dict[str, Any] = {
        "id": task_id,
        "state": "starting",
        "createdAt": now(),
        "updatedAt": now(),
        "runDir": str(run_dir),
        "cwd": str(cwd),
        "taskPath": str(task_path),
        "reportPath": str(run_dir / "report.md"),
        "access": "read-only" if read_only else "default-tools",
        "tmux": {"session": session},
    }
    if workflow:
        manifest["workflow"] = workflow
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
            f"{session}:",
            "-n",
            task_id,
            *command,
        ]
    )
    try:
        window_id, pane_id = result.stdout.strip().split(",", maxsplit=1)
    except ValueError:
        fail(f"unexpected tmux target response: {result.stdout!r}")
    update_manifest(
        run_dir,
        state="running",
        startedAt=now(),
        tmux={"session": session, "windowId": window_id, "paneId": pane_id},
    )
    (run_dir / "launch-ready").touch()
    return run_dir


# Legacy single-worker interface ------------------------------------------------
def command_dispatch(args: argparse.Namespace) -> None:
    run_dir = launch_worker(
        task_id=args.id,
        session=args.tmux_session,
        cwd=Path(args.cwd).expanduser().resolve(),
        task=args.task,
        read_only=args.read_only,
        root=Path(args.root).expanduser().resolve(),
    )
    print_status(load_manifest(run_dir))
    print("next: task-dispatch status --run " + str(run_dir))


def rpc_write(process: subprocess.Popen[bytes], command: dict[str, Any]) -> None:
    if process.stdin is None:
        raise RuntimeError("RPC stdin is unavailable")
    process.stdin.write((json.dumps(command) + "\n").encode())
    process.stdin.flush()


def assistant_text(event: dict[str, Any]) -> str:
    message = event.get("message", {})
    content = message.get("content", []) if isinstance(message, dict) else []
    if not isinstance(content, list):
        return ""
    return "".join(
        part.get("text", "")
        for part in content
        if isinstance(part, dict) and part.get("type") == "text"
    )


def render_rpc_event(event: dict[str, Any]) -> None:
    """Render useful RPC progress in the worker's tmux window."""
    event_type = event.get("type")
    if event_type == "agent_start":
        print("[agent] started", flush=True)
    elif event_type == "tool_execution_start":
        print(f"\n[tool] {event.get('toolName', 'unknown')}\n", flush=True)
    elif event_type == "tool_execution_end":
        result = "failed" if event.get("isError") else "finished"
        print(f"\n[tool] {event.get('toolName', 'unknown')} {result}\n", flush=True)
    elif event_type == "message_update":
        delta = event.get("assistantMessageEvent", {})
        if isinstance(delta, dict) and delta.get("type") == "text_delta":
            print(delta.get("delta", ""), end="", flush=True)
    elif event_type == "agent_settled":
        print("\n[agent] settled", flush=True)
    elif event_type == "response" and not event.get("success", True):
        print(f"[rpc] rejected: {event.get('error', 'unknown error')}", flush=True)


def command_worker(args: argparse.Namespace) -> None:
    run_dir = run_dir_from(args.run_dir)
    for _ in range(100):
        if (run_dir / "launch-ready").exists():
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
    event_log = run_dir / "events.jsonl"
    command = ["pi", "--mode", "rpc", "--no-session", "--name", manifest["id"]]
    if manifest["access"] == "read-only":
        command.extend(["--tools", READ_ONLY_TOOLS])
    try:
        process = subprocess.Popen(
            command,
            cwd=manifest["cwd"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        rpc_write(
            process,
            {
                "id": "task",
                "type": "prompt",
                "message": Path(manifest["taskPath"]).read_text(encoding="utf-8"),
            },
        )
        if process.stdout is None or process.stderr is None:
            raise RuntimeError("RPC streams are unavailable")
        settled = False
        abort_sent_at: float | None = None
        with (
            report.open("w", encoding="utf-8") as output,
            event_log.open("wb") as events,
        ):
            while True:
                if (run_dir / "cancel-requested").exists() and abort_sent_at is None:
                    rpc_write(process, {"type": "abort"})
                    abort_sent_at = time.monotonic()
                    update_manifest(run_dir, state="cancelling", phase="cancelling")
                if (
                    abort_sent_at
                    and time.monotonic() - abort_sent_at >= RPC_CANCEL_GRACE
                ):
                    process.terminate()
                ready, _, _ = select.select([process.stdout], [], [], 0.2)
                if not ready:
                    if process.poll() is not None:
                        break
                    continue
                line = process.stdout.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    continue
                events.write(line)
                event = json.loads(line)
                render_rpc_event(event)
                event_type = event.get("type")
                phase = {
                    "agent_start": "discovering",
                    "tool_execution_start": "working",
                    "compaction_start": "compacting",
                    "auto_retry_start": "retrying",
                }.get(event_type)
                if phase:
                    update_manifest(run_dir, phase=phase)
                if event_type == "message_end":
                    text = assistant_text(event)
                    if text:
                        output.write(text + "\n")
                        output.flush()
                if event_type == "agent_settled":
                    settled = True
                    break
        if settled and process.poll() is None and process.stdin is not None:
            # RPC is intentionally persistent; EOF requests a clean exit after its
            # terminal agent_settled event rather than treating process exit as done.
            process.stdin.close()
        deadline = time.monotonic() + RPC_CANCEL_GRACE
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        if process.poll() is None:
            process.kill()
        exit_code = process.wait()
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        if stderr:
            (run_dir / "stderr.log").write_text(stderr, encoding="utf-8")
        cancelled = (run_dir / "cancel-requested").exists()
        update_manifest(
            run_dir,
            state="cancelled" if cancelled else ("completed" if settled else "failed"),
            finishedAt=now(),
            exitCode=exit_code,
            phase=None,
            error=None
            if settled or cancelled
            else (stderr[-1000:] or "RPC process exited before agent_settled"),
        )
    except Exception as error:
        update_manifest(
            run_dir, state="failed", finishedAt=now(), phase=None, error=str(error)
        )
        raise


def command_status(args: argparse.Namespace) -> None:
    manifest = describe(run_dir_from(args.run_dir))
    print_status(manifest)
    if args.tail and Path(manifest["reportPath"]).exists():
        print(
            "\n--- report tail ---\n"
            + Path(manifest["reportPath"]).read_text(
                encoding="utf-8", errors="replace"
            )[-args.tail :]
        )


def command_wait(args: argparse.Namespace) -> None:
    run_dir, deadline, previous = (
        run_dir_from(args.run_dir),
        time.monotonic() + args.timeout,
        None,
    )
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
    if report.exists():
        content = report.read_text(encoding="utf-8", errors="replace")
        content = content if args.full else content[: args.max_chars]
        print("\n--- handoff ---\n" + content)


# Workflow persistence and projections -----------------------------------------
def db_connect(value: str) -> sqlite3.Connection:
    path = Path(value).expanduser()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS workflows (id TEXT PRIMARY KEY, name TEXT NOT NULL, cwd TEXT NOT NULL, tmux_session TEXT NOT NULL, max_concurrency INTEGER NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS tasks (workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE, id TEXT NOT NULL, title TEXT NOT NULL, prompt TEXT NOT NULL, cwd TEXT NOT NULL, access TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 0, resources TEXT NOT NULL DEFAULT '[]', state TEXT NOT NULL, phase TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(workflow_id,id));
    CREATE TABLE IF NOT EXISTS dependencies (workflow_id TEXT NOT NULL, task_id TEXT NOT NULL, depends_on TEXT NOT NULL, PRIMARY KEY(workflow_id,task_id,depends_on), FOREIGN KEY(workflow_id,task_id) REFERENCES tasks(workflow_id,id) ON DELETE CASCADE, FOREIGN KEY(workflow_id,depends_on) REFERENCES tasks(workflow_id,id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, task_id TEXT NOT NULL, run_dir TEXT NOT NULL, state TEXT NOT NULL, tmux_pane TEXT, started_at TEXT NOT NULL, finished_at TEXT, exit_code INTEGER, error TEXT);
    CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, workflow_id TEXT NOT NULL, task_id TEXT, attempt_id TEXT, type TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS resource_leases (workflow_id TEXT NOT NULL, resource TEXT NOT NULL, attempt_id TEXT NOT NULL, acquired_at TEXT NOT NULL, PRIMARY KEY(workflow_id,resource));
    CREATE TABLE IF NOT EXISTS scheduler_leases (workflow_id TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS dispatch_outbox (attempt_id TEXT PRIMARY KEY REFERENCES attempts(id) ON DELETE CASCADE, workflow_id TEXT NOT NULL, task_id TEXT NOT NULL, run_dir TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT);
    CREATE TABLE IF NOT EXISTS workflow_specs (workflow_id TEXT PRIMARY KEY REFERENCES workflows(id) ON DELETE CASCADE, spec TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS events_workflow_id ON events(workflow_id,id); CREATE INDEX IF NOT EXISTS attempts_task ON attempts(workflow_id,task_id); CREATE INDEX IF NOT EXISTS dispatch_outbox_workflow ON dispatch_outbox(workflow_id,state);
    """)
    return db


def event(
    db: sqlite3.Connection,
    workflow_id: str,
    kind: str,
    *,
    task_id: str | None = None,
    attempt_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    db.execute(
        "INSERT INTO events(workflow_id,task_id,attempt_id,type,detail,created_at) VALUES(?,?,?,?,?,?)",
        (workflow_id, task_id, attempt_id, kind, json.dumps(detail or {}), now()),
    )


def valid_task_id(value: Any) -> str:
    if not isinstance(value, str) or not RUN_ID.fullmatch(value):
        fail(
            "task ids must be lowercase letters, digits, and single hyphens (max 48 chars)"
        )
    return value


def finding(
    code: str,
    severity: str,
    message: str,
    *,
    task_ids: list[str] | None = None,
    edge: tuple[str, str] | None = None,
    remediation: str,
) -> dict[str, Any]:
    """Build a stable, JSON-serializable validation finding."""
    result: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "message": message,
        "taskIds": task_ids or [],
        "remediation": remediation,
    }
    if task_ids:
        result["task"] = task_ids[0]
    if edge:
        result["edge"] = {"task": edge[0], "dependsOn": edge[1]}
    return result


def validate_workflow_spec(spec: Any) -> list[dict[str, Any]]:
    """Pure, conservative validation of an authoring workflow specification."""
    findings: list[dict[str, Any]] = []
    if not isinstance(spec, dict):
        return [
            finding(
                "invalid-spec",
                "error",
                "workflow spec must be an object",
                remediation="Provide a JSON object with a tasks array.",
            )
        ]
    tasks = spec.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return [
            finding(
                "invalid-tasks",
                "error",
                "workflow needs a non-empty tasks array",
                remediation="Add at least one task object.",
            )
        ]
    seen: set[str] = set()
    valid: dict[str, dict[str, Any]] = {}
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            findings.append(
                finding(
                    "invalid-task",
                    "error",
                    f"task {index} must be an object",
                    remediation="Replace it with a task object.",
                )
            )
            continue
        task_id = task.get("id")
        display_id = task_id if isinstance(task_id, str) else f"task-{index}"
        if not isinstance(task_id, str) or not RUN_ID.fullmatch(task_id):
            findings.append(
                finding(
                    "invalid-task-id",
                    "error",
                    f"task id {task_id!r} is invalid",
                    task_ids=[display_id],
                    remediation="Use lowercase letters, digits, and single hyphens (max 48 characters).",
                )
            )
            continue
        if task_id in seen:
            findings.append(
                finding(
                    "duplicate-task-id",
                    "error",
                    f"task id {task_id!r} is duplicated",
                    task_ids=[task_id],
                    remediation="Give every task a unique id.",
                )
            )
            continue
        seen.add(task_id)
        valid[task_id] = task
        access = task.get("access", "read-only")
        if access not in {"read-only", "default-tools"}:
            findings.append(
                finding(
                    "invalid-access",
                    "error",
                    f"task {task_id} has invalid access {access!r}",
                    task_ids=[task_id],
                    remediation="Use read-only or default-tools.",
                )
            )
        state = task.get("state", "queued")
        if state not in {
            "queued",
            "ready",
            "in_progress",
            "done",
            "failed",
            "blocked",
            "cancelled",
        }:
            findings.append(
                finding(
                    "invalid-state",
                    "error",
                    f"task {task_id} has invalid state {state!r}",
                    task_ids=[task_id],
                    remediation="Use a supported workflow task state.",
                )
            )
        missing = [
            field
            for field in ("objective", "deliverable", "completionEvidence", "handoff")
            if not isinstance(task.get(field), str) or not task[field].strip()
        ]
        if missing:
            findings.append(
                finding(
                    "missing-task-contract",
                    "warning",
                    f"task {task_id} lacks {', '.join(missing)}",
                    task_ids=[task_id],
                    remediation="Add bounded objective, deliverable, completionEvidence, and handoff fields.",
                )
            )
        if not isinstance(
            task.get("prompt", task.get("title", "")), str
        ) and not isinstance(task.get("objective"), str):
            findings.append(
                finding(
                    "missing-task-prompt",
                    "error",
                    f"task {task_id} lacks prompt, title, and objective",
                    task_ids=[task_id],
                    remediation="Add a prompt or a bounded objective.",
                )
            )
        for field in ("dependsOn", "resources", "inputs", "outputs", "writePaths"):
            value = task.get(field, [])
            if not isinstance(value, list) or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                findings.append(
                    finding(
                        "invalid-task-metadata",
                        "error",
                        f"task {task_id} {field} must be a list of non-empty strings",
                        task_ids=[task_id],
                        remediation=f"Provide {field} as a string list.",
                    )
                )
        if access == "default-tools" and not any(
            isinstance(r, str) and r.startswith("worktree:")
            for r in task.get("resources", [])
        ):
            findings.append(
                finding(
                    "missing-worktree-resource",
                    "error",
                    f"writer task {task_id} lacks a worktree resource",
                    task_ids=[task_id],
                    remediation="Declare a unique worktree:<name> resource.",
                )
            )
    dependencies: dict[str, set[str]] = {task_id: set() for task_id in valid}
    for task_id, task in valid.items():
        depends_on = task.get("dependsOn", [])
        if not isinstance(depends_on, list):
            continue
        for parent in depends_on:
            if not isinstance(parent, str) or parent not in valid:
                findings.append(
                    finding(
                        "missing-dependency",
                        "error",
                        f"task {task_id} depends on unknown task {parent!r}",
                        task_ids=[task_id],
                        edge=(task_id, str(parent)),
                        remediation="Reference an existing task id or remove the dependency.",
                    )
                )
            elif parent == task_id:
                findings.append(
                    finding(
                        "self-dependency",
                        "error",
                        f"task {task_id} depends on itself",
                        task_ids=[task_id],
                        edge=(task_id, parent),
                        remediation="Remove the self dependency.",
                    )
                )
            else:
                dependencies[task_id].add(parent)
    roots = [task_id for task_id, parents in dependencies.items() if not parents]
    if valid and not roots:
        findings.append(
            finding(
                "no-root-task",
                "error",
                "workflow graph has no root task",
                task_ids=sorted(valid),
                remediation="Remove a cyclic dependency or add a task without dependencies.",
            )
        )
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            findings.append(
                finding(
                    "dependency-cycle",
                    "error",
                    f"dependency cycle includes {task_id}",
                    task_ids=[task_id],
                    remediation="Remove an edge so dependencies form a DAG.",
                )
            )
            return
        if task_id in visited:
            return
        visiting.add(task_id)
        for parent in dependencies[task_id]:
            visit(parent)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in valid:
        visit(task_id)

    def ordered(left: str, right: str) -> bool:
        stack = list(dependencies[left])
        walked: set[str] = set()
        while stack:
            node = stack.pop()
            if node == right:
                return True
            if node not in walked:
                walked.add(node)
                stack.extend(dependencies[node])
        return False

    writers = [
        (task_id, task)
        for task_id, task in valid.items()
        if task.get("access", "read-only") == "default-tools"
    ]
    for index, (left_id, left) in enumerate(writers):
        for right_id, right in writers[index + 1 :]:
            if ordered(left_id, right_id) or ordered(right_id, left_id):
                continue
            for left_path in left.get("writePaths", []) + left.get("outputs", []):
                for right_path in right.get("writePaths", []) + right.get(
                    "outputs", []
                ):
                    if (
                        isinstance(left_path, str)
                        and isinstance(right_path, str)
                        and (
                            left_path == right_path
                            or left_path.rstrip("/").startswith(
                                right_path.rstrip("/") + "/"
                            )
                            or right_path.rstrip("/").startswith(
                                left_path.rstrip("/") + "/"
                            )
                        )
                    ):
                        findings.append(
                            finding(
                                "write-path-conflict",
                                "error",
                                f"writers {left_id} and {right_id} can concurrently claim {left_path!r}",
                                task_ids=[left_id, right_id],
                                remediation="Assign one owner or add an explicit dependency between the writers.",
                            )
                        )
                        break
                else:
                    continue
                break
    return findings


# Short public alias for callers that do not need the legacy name.
validate_spec = validate_workflow_spec


def load_spec(path: str) -> dict[str, Any]:
    try:
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read JSON workflow spec: {error}")
    if not isinstance(spec, dict) or not isinstance(spec.get("tasks"), list):
        fail("workflow spec must be an object with a tasks array")
    return spec


def create_workflow(
    db: sqlite3.Connection,
    spec: dict[str, Any],
    *,
    session_override: str | None = None,
    cwd_override: str | None = None,
) -> str:
    errors = [item for item in validate_spec(spec) if item["severity"] == "error"]
    if errors:
        fail(
            "workflow validation failed: "
            + "; ".join(item["message"] for item in errors)
        )
    workflow_id = valid_task_id(spec.get("id") or f"workflow-{uuid.uuid4().hex[:12]}")
    name = str(spec.get("name") or workflow_id)
    cwd = Path(cwd_override or spec.get("cwd") or ".").expanduser().resolve()
    if not cwd.is_dir():
        fail(f"workflow cwd is not a directory: {cwd}")
    session = session_override or spec.get("tmuxSession")
    if not isinstance(session, str) or not session:
        fail("workflow needs tmuxSession (or --tmux-session)")
    limit = spec.get("maxConcurrency", 2)
    if not isinstance(limit, int) or limit < 1:
        fail("maxConcurrency must be a positive integer")
    try:
        with db:
            db.execute(
                "INSERT INTO workflows VALUES(?,?,?,?,?,?,?,?)",
                (workflow_id, name, str(cwd), session, limit, "draft", now(), now()),
            )
            seen: set[str] = set()
            for item in spec["tasks"]:
                if not isinstance(item, dict):
                    fail("each task must be an object")
                task_id = valid_task_id(item.get("id"))
                if task_id in seen:
                    fail(f"duplicate task id: {task_id}")
                seen.add(task_id)
                prompt = (
                    item.get("prompt") or item.get("title") or item.get("objective")
                )
                if not isinstance(prompt, str) or not prompt.strip():
                    fail(f"task {task_id} needs prompt, title, or objective")
                access = item.get("access", "read-only")
                if access not in {"read-only", "default-tools"}:
                    fail(f"task {task_id}: access must be read-only or default-tools")
                resources = item.get("resources", [])
                if not isinstance(resources, list) or not all(
                    isinstance(x, str) and x for x in resources
                ):
                    fail(f"task {task_id}: resources must be strings")
                task_cwd = Path(item.get("cwd") or cwd).expanduser().resolve()
                if not task_cwd.is_dir():
                    fail(f"task {task_id}: cwd is not a directory: {task_cwd}")
                db.execute(
                    "INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        workflow_id,
                        task_id,
                        str(item.get("title") or task_id),
                        prompt,
                        str(task_cwd),
                        access,
                        int(item.get("priority", 0)),
                        json.dumps(resources),
                        "queued",
                        None,
                        now(),
                        now(),
                    ),
                )
            for item in spec["tasks"]:
                for parent in item.get("dependsOn", []):
                    if parent not in seen:
                        fail(f"task {item['id']} depends on unknown task {parent}")
                    db.execute(
                        "INSERT INTO dependencies VALUES(?,?,?)",
                        (workflow_id, item["id"], parent),
                    )
            db.execute(
                "INSERT INTO workflow_specs VALUES(?,?,?)",
                (workflow_id, json.dumps(spec), now()),
            )
            event(db, workflow_id, "workflow.created", detail={"name": name})
    except sqlite3.IntegrityError as error:
        if "workflows.id" in str(error):
            fail(f"workflow already exists: {workflow_id}")
        fail(f"invalid workflow specification: {error}")
    return workflow_id


def parse_resources(value: str) -> list[str]:
    """Read the validated resource list persisted with a task."""
    try:
        result = json.loads(value)
    except json.JSONDecodeError as error:
        fail(f"invalid persisted resource list: {error}")
    if not isinstance(result, list) or not all(
        isinstance(item, str) for item in result
    ):
        fail("invalid persisted resource list")
    return result


def acquire_scheduler_lease(
    db: sqlite3.Connection,
    workflow_id: str,
    *,
    owner: str | None = None,
    lease_seconds: float = SCHEDULER_LEASE_SECONDS,
) -> str | None:
    """Acquire the workflow scheduler lease, reclaiming only an expired owner."""
    owner = owner or uuid.uuid4().hex
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "DELETE FROM scheduler_leases WHERE workflow_id=? AND expires_at<=?",
            (workflow_id, time.time()),
        )
        acquired = db.execute(
            "INSERT OR IGNORE INTO scheduler_leases VALUES(?,?,?)",
            (workflow_id, owner, time.time() + lease_seconds),
        ).rowcount
        if acquired:
            event(db, workflow_id, "scheduler.lease-acquired", detail={"owner": owner})
            db.commit()
            return owner
        db.rollback()
        return None
    except sqlite3.OperationalError:
        if db.in_transaction:
            db.rollback()
        return None


def release_scheduler_lease(
    db: sqlite3.Connection, workflow_id: str, owner: str
) -> None:
    with db:
        if db.execute(
            "DELETE FROM scheduler_leases WHERE workflow_id=? AND owner=?",
            (workflow_id, owner),
        ).rowcount:
            event(db, workflow_id, "scheduler.lease-released", detail={"owner": owner})


def workflow_row(db: sqlite3.Connection, workflow_id: str) -> sqlite3.Row:
    row = db.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
    if not row:
        fail(f"unknown workflow: {workflow_id}")
    return row


def project_terminal_manifest(
    db: sqlite3.Connection,
    workflow_id: str,
    attempt: sqlite3.Row,
    manifest: dict[str, Any],
) -> None:
    """Project an authoritative terminal manifest exactly once."""
    state = manifest["state"]
    task_state = {
        "completed": "done",
        "cancelled": "cancelled",
        "failed": "failed",
        "lost": "failed",
    }[state]
    db.execute(
        "UPDATE attempts SET state=?, finished_at=?, exit_code=?, error=? WHERE id=?",
        (
            task_state,
            manifest.get("finishedAt", now()),
            manifest.get("exitCode"),
            manifest.get("error"),
            attempt["id"],
        ),
    )
    db.execute(
        "UPDATE tasks SET state=?, phase=?, updated_at=? WHERE workflow_id=? AND id=?",
        (task_state, None, now(), workflow_id, attempt["task_id"]),
    )
    db.execute(
        "UPDATE dispatch_outbox SET state=?,updated_at=? WHERE attempt_id=?",
        (state, now(), attempt["id"]),
    )
    db.execute(
        "DELETE FROM resource_leases WHERE workflow_id=? AND attempt_id=?",
        (workflow_id, attempt["id"]),
    )
    event(
        db,
        workflow_id,
        "attempt.finished",
        task_id=attempt["task_id"],
        attempt_id=attempt["id"],
        detail={"state": task_state},
    )


def refresh(db: sqlite3.Connection, workflow_id: str) -> None:
    """Project authoritative terminal worker manifests and resolve dependencies."""
    for attempt in db.execute(
        "SELECT * FROM attempts WHERE workflow_id=? AND state IN ('in_progress','orphaned')",
        (workflow_id,),
    ):
        manifest_path = Path(attempt["run_dir"]) / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = describe(Path(attempt["run_dir"]))
        if manifest["state"] in TERMINAL_STATES:
            project_terminal_manifest(db, workflow_id, attempt, manifest)
    queued = db.execute(
        "SELECT id FROM tasks WHERE workflow_id=? AND state='queued'", (workflow_id,)
    ).fetchall()
    for row in queued:
        parents = db.execute(
            "SELECT t.state FROM dependencies d JOIN tasks t ON t.workflow_id=d.workflow_id AND t.id=d.depends_on WHERE d.workflow_id=? AND d.task_id=?",
            (workflow_id, row["id"]),
        ).fetchall()
        states = {p["state"] for p in parents}
        if states & {"failed", "blocked", "cancelled"}:
            db.execute(
                "UPDATE tasks SET state='blocked', updated_at=? WHERE workflow_id=? AND id=?",
                (now(), workflow_id, row["id"]),
            )
            event(
                db,
                workflow_id,
                "task.blocked",
                task_id=row["id"],
                detail={"dependencyStates": sorted(states)},
            )
        elif all(p == "done" for p in states):
            db.execute(
                "UPDATE tasks SET state='ready', updated_at=? WHERE workflow_id=? AND id=?",
                (now(), workflow_id, row["id"]),
            )
            event(db, workflow_id, "task.ready", task_id=row["id"])


def reconcile_dispatch_outbox(
    db: sqlite3.Connection, workflow_id: str, root: Path
) -> None:
    """Recover every nonterminal attempt without duplicating an ambiguous launch."""
    items = db.execute(
        "SELECT a.*, o.state AS outbox_state, t.prompt, t.cwd, t.access FROM attempts a "
        "LEFT JOIN dispatch_outbox o ON o.attempt_id=a.id "
        "JOIN tasks t ON t.workflow_id=a.workflow_id AND t.id=a.task_id "
        "WHERE a.workflow_id=? AND a.state='in_progress' "
        "ORDER BY a.started_at",
        (workflow_id,),
    ).fetchall()
    workflow = workflow_row(db, workflow_id)
    for item in items:
        outcome = "lost"
        run_dir = Path(item["run_dir"])
        manifest_path = run_dir / "manifest.json"
        if manifest_path.exists():
            manifest = load_manifest(run_dir)
            if manifest.get("state") in TERMINAL_STATES:
                project_terminal_manifest(db, workflow_id, item, manifest)
                continue
            target = manifest.get("tmux", {}).get("windowId") or item["tmux_pane"]
            if target and window_exists(target):
                db.execute(
                    "UPDATE attempts SET tmux_pane=? WHERE id=?",
                    (manifest.get("tmux", {}).get("paneId"), item["id"]),
                )
                if item["outbox_state"] == "pending":
                    db.execute(
                        "UPDATE dispatch_outbox SET state='launched',updated_at=? WHERE attempt_id=?",
                        (now(), item["id"]),
                    )
                continue
            error = "tmux target disappeared before worker reported completion"
        else:
            target = item["tmux_pane"]
            if target and window_exists(target):
                if item["state"] != "orphaned":
                    error = "worker target exists but manifest is missing"
                    db.execute(
                        "UPDATE attempts SET state='orphaned',error=? WHERE id=?",
                        (error, item["id"]),
                    )
                    db.execute(
                        "UPDATE dispatch_outbox SET state='orphaned',updated_at=?,error=? WHERE attempt_id=?",
                        (now(), error, item["id"]),
                    )
                    event(
                        db,
                        workflow_id,
                        "attempt.orphaned",
                        task_id=item["task_id"],
                        attempt_id=item["id"],
                        detail={"target": target},
                    )
                continue
            if item["outbox_state"] == "pending" and not run_dir.exists():
                try:
                    launch_worker(
                        task_id=item["task_id"],
                        session=workflow["tmux_session"],
                        cwd=Path(item["cwd"]),
                        task=item["prompt"],
                        read_only=item["access"] == "read-only",
                        root=root,
                        workflow={"id": workflow_id, "attemptId": item["id"]},
                        run_dir=run_dir,
                    )
                    manifest = load_manifest(run_dir)
                    db.execute(
                        "UPDATE attempts SET tmux_pane=? WHERE id=?",
                        (manifest["tmux"]["paneId"], item["id"]),
                    )
                    db.execute(
                        "UPDATE dispatch_outbox SET state='launched',updated_at=? WHERE attempt_id=?",
                        (now(), item["id"]),
                    )
                    event(
                        db,
                        workflow_id,
                        "attempt.dispatched",
                        task_id=item["task_id"],
                        attempt_id=item["id"],
                        detail={
                            "runDir": str(run_dir),
                            "pane": manifest["tmux"]["paneId"],
                        },
                    )
                    continue
                except SystemExit as launch_error:
                    outcome = "failed"
                    error = str(launch_error)
            else:
                error = "worker manifest and tmux target are missing"
        db.execute(
            "UPDATE dispatch_outbox SET state=?,updated_at=?,error=? WHERE attempt_id=?",
            (outcome, now(), error, item["id"]),
        )
        db.execute(
            "UPDATE attempts SET state=?,finished_at=?,error=? WHERE id=?",
            (outcome, now(), error, item["id"]),
        )
        db.execute(
            "UPDATE tasks SET state='failed',phase=NULL,updated_at=? WHERE workflow_id=? AND id=?",
            (now(), workflow_id, item["task_id"]),
        )
        db.execute(
            "DELETE FROM resource_leases WHERE workflow_id=? AND attempt_id=?",
            (workflow_id, item["id"]),
        )
        event(
            db,
            workflow_id,
            "dispatch.failed",
            task_id=item["task_id"],
            attempt_id=item["id"],
            detail={"outcome": outcome, "reason": error},
        )


def reconcile_workflow(db: sqlite3.Connection, workflow_id: str, root: Path) -> None:
    """Run the idempotent recovery pass without scheduling new work."""
    with db:
        refresh(db, workflow_id)
        reconcile_dispatch_outbox(db, workflow_id, root)
        refresh(db, workflow_id)


def tick(db: sqlite3.Connection, workflow_id: str, root: Path) -> None:
    """Schedule under a SQLite lease and launch only durable dispatch intents."""
    owner = acquire_scheduler_lease(db, workflow_id)
    if owner is None:
        return
    try:
        with db:
            workflow = workflow_row(db, workflow_id)
            reconcile_workflow(db, workflow_id, root)
            if workflow["state"] == "draft":
                db.execute(
                    "UPDATE workflows SET state='running',updated_at=? WHERE id=?",
                    (now(), workflow_id),
                )
                event(db, workflow_id, "workflow.started")
            reconcile_dispatch_outbox(db, workflow_id, root)
            active = db.execute(
                "SELECT COUNT(*) FROM attempts WHERE workflow_id=? AND state='in_progress'",
                (workflow_id,),
            ).fetchone()[0]
            slots = workflow["max_concurrency"] - active
            ready = db.execute(
                "SELECT * FROM tasks WHERE workflow_id=? AND state='ready' ORDER BY priority DESC, created_at",
                (workflow_id,),
            ).fetchall()
            for task in ready:
                if slots <= 0:
                    break
                resources = parse_resources(task["resources"])
                held = {
                    row[0]
                    for row in db.execute(
                        "SELECT resource FROM resource_leases WHERE workflow_id=?",
                        (workflow_id,),
                    )
                }
                if held.intersection(resources):
                    event(
                        db,
                        workflow_id,
                        "scheduler.deferred",
                        task_id=task["id"],
                        detail={"reason": "resource-held", "resources": resources},
                    )
                    continue
                if task["access"] != "read-only" and not any(
                    r.startswith("worktree:") for r in resources
                ):
                    db.execute(
                        "UPDATE tasks SET state='blocked',updated_at=? WHERE workflow_id=? AND id=?",
                        (now(), workflow_id, task["id"]),
                    )
                    event(
                        db,
                        workflow_id,
                        "task.blocked",
                        task_id=task["id"],
                        detail={"reason": "write task requires a worktree:* resource"},
                    )
                    continue
                attempt_id = uuid.uuid4().hex
                run_dir = (
                    root
                    / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{task['id']}-{uuid.uuid4().hex[:6]}"
                )
                db.execute(
                    "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        attempt_id,
                        workflow_id,
                        task["id"],
                        str(run_dir),
                        "in_progress",
                        None,
                        now(),
                        None,
                        None,
                        None,
                    ),
                )
                db.execute(
                    "UPDATE tasks SET state='in_progress',phase='starting',updated_at=? WHERE workflow_id=? AND id=?",
                    (now(), workflow_id, task["id"]),
                )
                for resource in resources:
                    db.execute(
                        "INSERT INTO resource_leases VALUES(?,?,?,?)",
                        (workflow_id, resource, attempt_id, now()),
                    )
                db.execute(
                    "INSERT INTO dispatch_outbox VALUES(?,?,?,?,?,?,?,NULL)",
                    (
                        attempt_id,
                        workflow_id,
                        task["id"],
                        str(run_dir),
                        "pending",
                        now(),
                        now(),
                    ),
                )
                event(
                    db,
                    workflow_id,
                    "dispatch.intent-recorded",
                    task_id=task["id"],
                    attempt_id=attempt_id,
                    detail={"runDir": str(run_dir)},
                )
                slots -= 1
        # tmux is external: its outcome is reconciled from the durable intent.
        with db:
            reconcile_workflow(db, workflow_id, root)
            remaining = db.execute(
                "SELECT COUNT(*) FROM tasks WHERE workflow_id=? AND state NOT IN ('done','failed','blocked','cancelled')",
                (workflow_id,),
            ).fetchone()[0]
            if remaining == 0:
                states = {
                    row[0]
                    for row in db.execute(
                        "SELECT state FROM tasks WHERE workflow_id=?", (workflow_id,)
                    )
                }
                final = "completed" if states == {"done"} else "failed"
                db.execute(
                    "UPDATE workflows SET state=?,updated_at=? WHERE id=?",
                    (final, now(), workflow_id),
                )
                event(db, workflow_id, f"workflow.{final}")
    finally:
        release_scheduler_lease(db, workflow_id, owner)


def print_workflow(
    db: sqlite3.Connection, workflow_id: str, verbose: bool = True
) -> None:
    workflow = workflow_row(db, workflow_id)
    tasks = db.execute(
        "SELECT * FROM tasks WHERE workflow_id=? ORDER BY state, priority DESC, id",
        (workflow_id,),
    ).fetchall()
    counts = dict.fromkeys(
        ("queued", "ready", "in_progress", "done", "failed", "blocked", "cancelled"),
        0,
    )
    for task in tasks:
        counts[task["state"]] += 1
    print(
        f"workflow: {workflow['id']} ({workflow['state']})  "
        + " ".join(f"{k}={v}" for k, v in counts.items() if v)
    )
    if verbose:
        for task in tasks:
            print(
                f"{task['state']:12} {task['id']:24} {task['phase'] or '-':12} {task['title']}"
            )


def stored_spec(db: sqlite3.Connection, workflow_id: str) -> dict[str, Any]:
    row = db.execute(
        "SELECT spec FROM workflow_specs WHERE workflow_id=?", (workflow_id,)
    ).fetchone()
    if row:
        try:
            value = json.loads(row["spec"])
        except ValueError as error:
            fail(f"stored workflow spec is invalid: {workflow_id}: {error}")
        if isinstance(value, dict):
            return value
    workflow = workflow_row(db, workflow_id)
    tasks = db.execute(
        "SELECT * FROM tasks WHERE workflow_id=? ORDER BY id", (workflow_id,)
    ).fetchall()
    dependencies = db.execute(
        "SELECT task_id, depends_on FROM dependencies WHERE workflow_id=?",
        (workflow_id,),
    ).fetchall()
    parents: dict[str, list[str]] = {task["id"]: [] for task in tasks}
    for dependency in dependencies:
        parents[dependency["task_id"]].append(dependency["depends_on"])
    return {
        "id": workflow["id"],
        "name": workflow["name"],
        "cwd": workflow["cwd"],
        "tmuxSession": workflow["tmux_session"],
        "maxConcurrency": workflow["max_concurrency"],
        "tasks": [
            {
                "id": task["id"],
                "title": task["title"],
                "prompt": task["prompt"],
                "access": task["access"],
                "state": task["state"],
                "resources": parse_resources(task["resources"]),
                "dependsOn": parents[task["id"]],
            }
            for task in tasks
        ],
    }


def command_workflow_validate(args: argparse.Namespace) -> None:
    spec = (
        load_spec(args.file)
        if args.file
        else stored_spec(db_connect(args.database), args.id)
    )
    findings = validate_spec(spec)
    print(
        json.dumps(
            {
                "valid": not any(item["severity"] == "error" for item in findings),
                "findings": findings,
            },
            indent=2,
        )
    )
    if any(item["severity"] == "error" for item in findings):
        raise SystemExit(1)


def command_workflow_create(args: argparse.Namespace) -> None:
    db = db_connect(args.database)
    workflow_id = create_workflow(
        db,
        load_spec(args.file),
        session_override=args.tmux_session,
        cwd_override=args.cwd,
    )
    print(workflow_id)


def markdown_spec(
    path: str, workflow_id: str | None, session: str | None, cwd: str | None
) -> dict[str, Any]:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as error:
        fail(f"cannot read markdown: {error}")
    tasks: list[dict[str, Any]] = []
    used: set[str] = set()
    for line in lines:
        match = re.match(r"^\s*[-*+]\s+\[\s*\]\s+(.+?)\s*$", line)
        if not match:
            continue
        text = match.group(1)
        deps = re.search(r"\s*<!--\s*depends:\s*([a-z0-9, -]+)\s*-->\s*$", text)
        depends = [x.strip() for x in deps.group(1).split(",")] if deps else []
        title = text[: deps.start()].strip() if deps else text
        base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "task"
        task_id = base
        index = 2
        while task_id in used:
            task_id = f"{base[:43]}-{index}"
            index += 1
        used.add(task_id)
        tasks.append(
            {
                "id": task_id,
                "title": title,
                "prompt": title,
                "dependsOn": depends,
                "access": "read-only",
            }
        )
    if not tasks:
        fail("markdown has no unchecked list items (- [ ])")
    return {
        "id": workflow_id or f"workflow-{uuid.uuid4().hex[:12]}",
        "name": Path(path).stem,
        "cwd": cwd or str(Path.cwd()),
        "tmuxSession": session or "REPLACE_ME",
        "maxConcurrency": 2,
        "tasks": tasks,
    }


def command_workflow_import(args: argparse.Namespace) -> None:
    spec = markdown_spec(args.markdown, args.id, args.tmux_session, args.cwd)
    output = Path(args.output).expanduser()
    output.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print(output)


def command_workflow_tick(args: argparse.Namespace) -> None:
    db = db_connect(args.database)
    tick(db, args.id, Path(args.root).expanduser())
    print_workflow(db, args.id)


def command_workflow_reconcile(args: argparse.Namespace) -> None:
    db = db_connect(args.database)
    reconcile_workflow(db, args.id, Path(args.root).expanduser())
    print_workflow(db, args.id)


def command_workflow_status(args: argparse.Namespace) -> None:
    db = db_connect(args.database)
    if args.refresh:
        with db:
            refresh(db, args.id)
    print_workflow(db, args.id)


def command_workflow_events(args: argparse.Namespace) -> None:
    db = db_connect(args.database)
    last = 0
    while True:
        rows = db.execute(
            "SELECT * FROM events WHERE workflow_id=? AND id>? ORDER BY id",
            (args.id, last),
        ).fetchall()
        for row in rows:
            print(
                f"{row['created_at']} {row['type']:24} {row['task_id'] or '-':24} {row['detail']}"
            )
            last = row["id"]
        if not args.follow:
            return
        time.sleep(args.interval)


def command_workflow_inspect(args: argparse.Namespace) -> None:
    db = db_connect(args.database)
    task = db.execute(
        "SELECT * FROM tasks WHERE workflow_id=? AND id=?", (args.id, args.task)
    ).fetchone()
    if not task:
        fail(f"unknown task {args.task}")
    print(json.dumps(dict(task), indent=2))
    parents = db.execute(
        "SELECT depends_on FROM dependencies WHERE workflow_id=? AND task_id=?",
        (args.id, args.task),
    ).fetchall()
    print("dependsOn:", ", ".join(r[0] for r in parents) or "none")
    attempt = db.execute(
        "SELECT * FROM attempts WHERE workflow_id=? AND task_id=? ORDER BY started_at DESC LIMIT 1",
        (args.id, args.task),
    ).fetchone()
    if attempt:
        print("attempt:", json.dumps(dict(attempt), indent=2))


def command_workflow_cancel(args: argparse.Namespace) -> None:
    db = db_connect(args.database)
    with db:
        if args.task:
            tasks = db.execute(
                "SELECT * FROM tasks WHERE workflow_id=? AND id=?", (args.id, args.task)
            ).fetchall()
        else:
            tasks = db.execute(
                "SELECT * FROM tasks WHERE workflow_id=? AND state NOT IN ('done','failed','blocked','cancelled')",
                (args.id,),
            ).fetchall()
        if not tasks:
            fail("no cancellable tasks")
        for task in tasks:
            attempt = db.execute(
                "SELECT * FROM attempts WHERE workflow_id=? AND task_id=? AND state='in_progress'",
                (args.id, task["id"]),
            ).fetchone()
            if attempt:
                run_dir = Path(attempt["run_dir"])
                manifest = describe(run_dir)
                if manifest["state"] not in TERMINAL_STATES:
                    # The RPC worker sees this within 200ms and sends `abort` before
                    # escalating. Do not kill its wrapper with terminal Ctrl-C.
                    (run_dir / "cancel-requested").touch()
            db.execute(
                "UPDATE tasks SET state='cancelled',phase=NULL,updated_at=? WHERE workflow_id=? AND id=?",
                (now(), args.id, task["id"]),
            )
            event(db, args.id, "task.cancelled", task_id=task["id"])
        if not args.task:
            db.execute(
                "UPDATE workflows SET state='cancelled',updated_at=? WHERE id=?",
                (now(), args.id),
            )


def draw_watch(
    screen: Any,
    db: sqlite3.Connection,
    workflow_id: str,
    root: Path,
    drive: bool,
) -> None:
    screen.nodelay(True)
    screen.timeout(500)
    last_tick = 0.0
    columns = [
        ("queued", "Queued"),
        ("ready", "Ready"),
        ("in_progress", "In progress"),
        ("done", "Done"),
        ("failed", "Failed"),
        ("blocked", "Blocked"),
        ("cancelled", "Cancelled"),
    ]
    while True:
        if drive and time.monotonic() - last_tick >= 1:
            with db:
                tick(db, workflow_id, root)
            last_tick = time.monotonic()
        screen.erase()
        height, width = screen.getmaxyx()
        workflow = workflow_row(db, workflow_id)
        screen.addnstr(
            0,
            0,
            f"{workflow['id']} [{workflow['state']}]  q: quit  r: refresh/tick",
            width - 1,
        )
        tasks = db.execute(
            "SELECT * FROM tasks WHERE workflow_id=? ORDER BY priority DESC,id",
            (workflow_id,),
        ).fetchall()
        col_width = max(16, width // len(columns))
        for i, (_, title) in enumerate(columns):
            screen.addnstr(2, i * col_width, title, col_width - 1)
        positions = {state: 3 for state, _ in columns}
        for task in tasks:
            state = task["state"]
            x = [s for s, _ in columns].index(state) * col_width
            y = positions[state]
            if y < height - 1:
                screen.addnstr(
                    y, x, f"{task['id']} ({task['phase'] or '-'})", col_width - 1
                )
            positions[state] += 1
        screen.addnstr(
            height - 2,
            0,
            "Gantt (attempt timing): "
            + " | ".join(
                f"{a['task_id']}:{a['started_at'][11:19]}-{(a['finished_at'] or 'now')[11:19]}"
                for a in db.execute(
                    "SELECT * FROM attempts WHERE workflow_id=? ORDER BY started_at DESC LIMIT 5",
                    (workflow_id,),
                )
            ),
            width - 1,
        )
        screen.refresh()
        key = screen.getch()
        if key in (ord("q"), 27):
            return
        if key == ord("r"):
            with db:
                tick(db, workflow_id, root)
            last_tick = time.monotonic()


def command_workflow_watch(args: argparse.Namespace) -> None:
    db = db_connect(args.database)
    workflow = workflow_row(db, args.id)
    if not args.in_tmux:
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--database",
            args.database,
            "--root",
            args.root,
            "workflow",
            "watch",
            args.id,
            "--in-tmux",
        ]
        if args.drive:
            command.append("--drive")
        result = run_tmux(
            [
                "new-window",
                "-d",
                "-P",
                "-F",
                "#{window_id},#{pane_id}",
                "-t",
                f"{workflow['tmux_session']}:",
                "-n",
                f"workflow-{args.id}"[:40],
                *command,
            ]
        )
        try:
            window_id, pane_id = result.stdout.strip().split(",", maxsplit=1)
        except ValueError:
            fail(f"unexpected tmux target response: {result.stdout!r}")
        print(f"watch: {workflow['tmux_session']}:{window_id} ({pane_id})")
        print(f"attach: tmux select-window -t '{workflow['tmux_session']}:{window_id}'")
        return
    curses.wrapper(draw_watch, db, args.id, Path(args.root).expanduser(), args.drive)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="task-run root (default: ~/.pi/agent/task-runs)",
    )
    parser.add_argument(
        "--database", default=str(DEFAULT_DATABASE), help="workflow SQLite database"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    dispatch = commands.add_parser(
        "dispatch", help="start one worker in a detached tmux window"
    )
    dispatch.add_argument("--id", required=True)
    dispatch.add_argument("--tmux-session", required=True)
    dispatch.add_argument("--cwd", required=True)
    dispatch.add_argument("--task", required=True)
    dispatch.add_argument("--read-only", action="store_true")
    dispatch.set_defaults(handler=command_dispatch)
    for name, handler, help_text in [
        ("status", command_status, "show worker state"),
        ("wait", command_wait, "bounded polling until completion"),
        ("cancel", command_cancel, "send Ctrl-C to worker"),
        ("collect", command_collect, "print worker handoff"),
    ]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--run", dest="run_dir", required=True)
        command.set_defaults(handler=handler)
        if name == "status":
            command.add_argument("--tail", type=int, default=0)
        if name == "wait":
            command.add_argument("--interval", type=float, default=5)
            command.add_argument("--timeout", type=float, required=True)
        if name == "collect":
            command.add_argument("--max-chars", type=int, default=12000)
            command.add_argument("--full", action="store_true")
    worker = commands.add_parser("worker", help=argparse.SUPPRESS)
    worker.add_argument("--run-dir", required=True)
    worker.set_defaults(handler=command_worker)
    workflow = commands.add_parser(
        "workflow", help="create, schedule, and observe workflows"
    )
    wf = workflow.add_subparsers(dest="workflow_command", required=True)
    validate = wf.add_parser(
        "validate", help="validate a workflow spec or stored workflow"
    )
    source = validate.add_mutually_exclusive_group(required=True)
    source.add_argument("--file")
    source.add_argument("id", nargs="?")
    validate.set_defaults(handler=command_workflow_validate)
    create = wf.add_parser("create", help="create a draft workflow from JSON")
    create.add_argument("--file", required=True)
    create.add_argument("--tmux-session")
    create.add_argument("--cwd")
    create.set_defaults(handler=command_workflow_create)
    imported = wf.add_parser(
        "import", help="turn Markdown unchecked todos into an editable JSON spec"
    )
    imported.add_argument("--markdown", required=True)
    imported.add_argument("--output", required=True)
    imported.add_argument("--id")
    imported.add_argument("--tmux-session")
    imported.add_argument("--cwd")
    imported.set_defaults(handler=command_workflow_import)
    for name, handler, help_text in [
        ("start", command_workflow_tick, "start and schedule eligible work"),
        ("tick", command_workflow_tick, "reconcile and schedule once"),
        ("reconcile", command_workflow_reconcile, "recover durable workflow state"),
    ]:
        item = wf.add_parser(name, help=help_text)
        item.add_argument("id")
        item.set_defaults(handler=handler)
    status = wf.add_parser("status", help="show workflow board")
    status.add_argument("id")
    status.add_argument("--refresh", action="store_true")
    status.set_defaults(handler=command_workflow_status)
    events = wf.add_parser("events", help="print append-only event history")
    events.add_argument("id")
    events.add_argument("--follow", action="store_true")
    events.add_argument("--interval", type=float, default=1)
    events.set_defaults(handler=command_workflow_events)
    inspect = wf.add_parser(
        "inspect", help="show task, dependencies, and latest attempt"
    )
    inspect.add_argument("id")
    inspect.add_argument("task")
    inspect.set_defaults(handler=command_workflow_inspect)
    cancel = wf.add_parser("cancel", help="cancel a task or whole workflow")
    cancel.add_argument("id")
    cancel.add_argument("task", nargs="?")
    cancel.set_defaults(handler=command_workflow_cancel)
    watch = wf.add_parser(
        "watch", help="open a live Kanban/Gantt board in a tmux window"
    )
    watch.add_argument("id")
    watch.add_argument("--drive", action="store_true", default=True)
    watch.add_argument("--no-drive", dest="drive", action="store_false")
    watch.add_argument("--in-tmux", action="store_true", help=argparse.SUPPRESS)
    watch.set_defaults(handler=command_workflow_watch)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
