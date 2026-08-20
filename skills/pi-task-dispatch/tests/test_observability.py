"""Draft/export and fake JSONL-RPC seam tests; no tmux or Pi required."""

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "scripts" / "task-dispatch.py"


def load() -> Any:
    spec = importlib.util.spec_from_file_location("task_dispatch_observe", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ObservabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.d = load()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.d.db_connect(str(self.root / "workflow.db"))
        self.spec = {
            "id": "fixture",
            "cwd": str(self.root),
            "tmuxSession": "unused",
            "maxConcurrency": 2,
            "tasks": [
                {"id": "reader-a", "prompt": "a"},
                {"id": "reader-b", "prompt": "b"},
                {"id": "join", "prompt": "j", "dependsOn": ["reader-a", "reader-b"]},
            ],
        }
        self.d.create_workflow(self.db, self.spec)

    def tearDown(self) -> None:
        self.db.close()
        self.temp.cleanup()

    def test_draft_has_separate_inferred_and_approved_edges(self) -> None:
        draft = self.d.workflow_draft("Map code", ["src", "tests"])
        self.assertEqual([], draft["approvedDependencies"])
        self.assertEqual([], draft["tasks"][-1]["dependsOn"])
        self.assertEqual(2, len(draft["inferredDependencies"]))
        output = io.StringIO()
        with redirect_stdout(output):
            self.d.command_workflow_draft(
                type("Args", (), {"goal": "Map code", "discovery": ["src"]})()
            )
        self.assertEqual("draft", json.loads(output.getvalue())["state"])
        self.assertIsNone(
            self.db.execute("SELECT 1 FROM workflows WHERE id LIKE '%draft'").fetchone()
        )

    def test_acceptance_resource_shapes(self) -> None:
        base = {
            "id": "acceptance",
            "cwd": str(self.root),
            "tmuxSession": "unused",
            "maxConcurrency": 2,
        }
        readers = {
            **base,
            "tasks": [{"id": "a", "prompt": "a"}, {"id": "b", "prompt": "b"}],
        }
        self.assertFalse(
            any(f["severity"] == "error" for f in self.d.validate_spec(readers))
        )
        shared = {
            **base,
            "tasks": [
                {"id": "a", "prompt": "a", "resources": ["repo:shared"]},
                {"id": "b", "prompt": "b", "resources": ["repo:shared"]},
            ],
        }
        self.assertFalse(
            any(f["severity"] == "error" for f in self.d.validate_spec(shared))
        )
        gated_writer = {
            **base,
            "tasks": [
                {
                    "id": "write",
                    "prompt": "w",
                    "access": "default-tools",
                    "resources": ["worktree:isolated"],
                    "writePaths": ["src/x"],
                    "gate": "approval",
                }
            ],
        }
        self.assertFalse(
            any(f["severity"] == "error" for f in self.d.validate_spec(gated_writer))
        )

    def test_projection_and_jsonl_events_are_machine_readable(self) -> None:
        with self.db:
            self.d.event(
                self.db,
                "fixture",
                "task.ready",
                task_id="reader-a",
                detail={"why": "fixture"},
            )
        projection = self.d.workflow_projection(self.db, "fixture")
        self.assertEqual(
            ["join", "reader-a", "reader-b"], [t["id"] for t in projection["tasks"]]
        )
        self.assertTrue(
            next(t for t in projection["tasks"] if t["id"] == "reader-a")[
                "criticalPath"
            ]
        )
        output = io.StringIO()
        with redirect_stdout(output):
            self.d.command_workflow_events(
                type(
                    "Args",
                    (),
                    {
                        "database": str(self.root / "workflow.db"),
                        "id": "fixture",
                        "follow": False,
                        "interval": 0,
                        "jsonl": True,
                    },
                )()
            )
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        row = next(record for record in records if record["type"] == "task.ready")
        self.assertEqual("fixture", row["workflowId"])
        self.assertEqual("task.ready", row["type"])

    def test_watch_layout_is_bordered_wrapped_and_filterable(self) -> None:
        projection = self.d.workflow_projection(self.db, "fixture")
        reader = next(task for task in projection["tasks"] if task["id"] == "reader-a")
        reader.update(
            {
                "state": "failed",
                "phase": "working",
                "resources": ["repo:shared"],
                "currentTool": "very-long-tool-name",
                "tokens": 12,
                "cost": "0.01",
            }
        )
        lines, visible = self.d.watch_board_lines(
            projection,
            80,
            "reader-a",
            {"state": "all", "resource": "all", "agent": "all"},
            set(),
        )
        self.assertEqual("+", lines[0][0])
        self.assertIn("Terminated", lines[1])
        self.assertIn("FAILED", "\n".join(lines))
        self.assertIn("reader-a", visible)
        _, ready = self.d.watch_board_lines(
            projection,
            80,
            None,
            {"state": "terminated", "resource": "all", "agent": "all"},
            set(),
        )
        self.assertEqual(["reader-a"], ready)
        self.assertIn("Gantt", self.d.watch_timeline_lines(projection, 80)[0])

    def test_workflow_workers_use_derived_session_and_one_window_per_attempt(
        self,
    ) -> None:
        calls: list[list[str]] = []

        def fake_tmux(arguments: list[str], **_: Any) -> Any:
            calls.append(arguments)
            return type("Result", (), {"stdout": "@7,%9\n"})()

        with (
            patch.object(self.d, "run_tmux", side_effect=fake_tmux),
            patch.object(self.d, "tmux_session_exists", return_value=False),
        ):
            target = self.d.launch_workflow_rpc_window(
                "pi-exts", "fixture", "reader", ["worker"]
            )
        self.assertEqual(("eph-pi-exts", "@7", "%9"), target)
        self.assertEqual(["new-session"], [c[0] for c in calls])
        self.assertIn("eph-pi-exts", calls[0])
        self.assertNotIn("split-window", calls[0])
        calls.clear()

        with (
            patch.object(self.d, "run_tmux", side_effect=fake_tmux),
            patch.object(self.d, "tmux_session_exists", return_value=True),
        ):
            self.d.launch_workflow_rpc_window(
                "pi-exts", "fixture", "writer", ["worker"]
            )
        self.assertEqual(["new-window"], [c[0] for c in calls])
        self.assertIn("eph-pi-exts:", calls[0])

    def test_uv_script_command_uses_locked_managed_python(self) -> None:
        with patch.object(self.d.shutil, "which", return_value="/usr/local/bin/uv"):
            command = self.d.uv_script_command("worker", "--run-dir", "/tmp/run")
        self.assertEqual(
            ["uv", "run", "--managed-python", "--locked", "--script"],
            command[:5],
        )
        self.assertEqual("task-dispatch.py", Path(command[5]).name)
        self.assertEqual(["worker", "--run-dir", "/tmp/run"], command[6:])

    def test_watch_reexec_uses_uv_script_command(self) -> None:
        calls: list[list[str]] = []

        def fake_tmux(arguments: list[str], **_: Any) -> Any:
            calls.append(arguments)
            return type("Result", (), {"stdout": "@7,%9\\n"})()

        args = type(
            "Args",
            (),
            {
                "database": str(self.root / "workflow.db"),
                "root": str(self.root),
                "id": "fixture",
                "in_tmux": False,
                "drive": True,
            },
        )()
        with (
            patch.object(self.d.shutil, "which", return_value="/usr/local/bin/uv"),
            patch.object(self.d, "run_tmux", side_effect=fake_tmux),
            redirect_stdout(io.StringIO()),
        ):
            self.d.command_workflow_watch(args)
        command = calls[0]
        self.assertIn("uv", command)
        self.assertIn("--managed-python", command)
        self.assertIn("--locked", command)
        self.assertIn("--in-tmux", command)

    def test_read_only_rpc_workers_receive_shell_access(self) -> None:
        command = self.d.rpc_command({"id": "reader", "access": "read-only"})
        self.assertEqual(
            [
                "pi",
                "--mode",
                "rpc",
                "--no-session",
                "--name",
                "reader",
                "--tools",
                "read,grep,find,ls,bash",
            ],
            command,
        )

    def test_fake_rpc_stream_settles_and_malformed_fails(self) -> None:
        for name, lines, expected in [
            (
                "settles",
                [
                    '{"type":"agent_start"}',
                    '{"type":"message_end","message":{"content":[{"type":"text","text":"ok"}]}}',
                    '{"type":"agent_settled"}',
                ],
                "completed",
            ),
            ("malformed", ["not-json"], "failed"),
        ]:
            run = self.root / name
            run.mkdir()
            task = run / "task.md"
            task.write_text("work")
            report = run / "report.md"
            self.d.write_json(
                run / "manifest.json",
                {
                    "id": name,
                    "state": "running",
                    "cwd": str(self.root),
                    "taskPath": str(task),
                    "reportPath": str(report),
                    "access": "read-only",
                    "tmux": {},
                },
            )
            (run / "launch-ready").touch()
            fake = self.root / f"{name}.py"
            fake.write_text(
                "import sys\n_ = sys.stdin.readline()\n"
                + "\n".join(f"print({line!r}, flush=True)" for line in lines)
            )
            with patch.dict(
                os.environ, {"TASK_DISPATCH_RPC_COMMAND": f"{sys.executable} {fake}"}
            ):
                if expected == "failed":
                    with self.assertRaises(RuntimeError):
                        self.d.command_worker(type("Args", (), {"run_dir": str(run)})())
                else:
                    self.d.command_worker(type("Args", (), {"run_dir": str(run)})())
            self.assertEqual(expected, self.d.load_manifest(run)["state"])
            if expected == "completed":
                self.assertEqual("ok\n", report.read_text())


if __name__ == "__main__":
    unittest.main()
