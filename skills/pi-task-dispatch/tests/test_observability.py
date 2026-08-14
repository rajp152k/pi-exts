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
