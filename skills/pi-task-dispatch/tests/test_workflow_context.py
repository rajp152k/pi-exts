"""Workflow attempt context and bounded direct-parent report injection tests."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "task-dispatch.py"


def load_dispatcher() -> Any:
    spec = importlib.util.spec_from_file_location("task_dispatch_context", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WorkflowContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dispatcher = load_dispatcher()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "runs"
        self.db = self.dispatcher.db_connect(str(self.base / "workflow.sqlite"))
        self.workflow_id = "context-fixture"
        self.dispatcher.create_workflow(
            self.db,
            {
                "id": self.workflow_id,
                "cwd": str(Path.cwd()),
                "tmuxSession": "context-session",
                "maxConcurrency": 1,
                "tasks": [
                    {"id": "parent", "prompt": "Parent work."},
                    {
                        "id": "child",
                        "prompt": "Child work.",
                        "dependsOn": ["parent"],
                        "inputs": ["parent report"],
                        "outputs": ["result.md"],
                        "writePaths": ["result.md"],
                        "handoff": "Return the decision and tests.",
                    },
                ],
            },
        )

    def tearDown(self) -> None:
        self.db.close()
        self.temporary.cleanup()

    def complete_parent(self, report: bytes = b"parent decision") -> Path:
        run_dir = self.root / "parent-attempt"
        run_dir.mkdir(parents=True)
        report_path = run_dir / "report.md"
        report_path.write_bytes(report)
        self.dispatcher.write_json(
            run_dir / "manifest.json",
            {"state": "completed", "reportPath": str(report_path)},
        )
        with self.db:
            self.db.execute(
                "UPDATE tasks SET state='done' WHERE workflow_id=? AND id='parent'",
                (self.workflow_id,),
            )
            self.db.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    "parent-attempt",
                    self.workflow_id,
                    "parent",
                    str(run_dir),
                    "done",
                    None,
                    self.dispatcher.now(),
                    self.dispatcher.now(),
                    0,
                    None,
                ),
            )
        return run_dir

    def test_child_launch_gets_persisted_declarations_and_hashed_parent_report(
        self,
    ) -> None:
        self.complete_parent(b"x" * (self.dispatcher.REPORT_BYTES_LIMIT + 10))
        captured: dict[str, Any] = {}

        def launch(**kwargs: Any) -> Path:
            captured.update(kwargs)
            run_dir = kwargs["run_dir"]
            run_dir.mkdir(parents=True)
            self.dispatcher.write_json(
                run_dir / "manifest.json",
                {
                    "state": "running",
                    "tmux": {"windowId": "@child", "paneId": "%child"},
                },
            )
            return run_dir

        with patch.object(self.dispatcher, "launch_worker", side_effect=launch):
            self.dispatcher.tick(self.db, self.workflow_id, self.root)

        context = captured["context"]
        self.assertEqual(self.workflow_id, context["workflowId"])
        self.assertEqual("child", context["taskId"])
        self.assertEqual(str(self.root), context["artifactRoot"])
        self.assertEqual(["parent report"], context["declarations"]["inputs"])
        self.assertEqual("Return the decision and tests.", context["handoff"])
        artifact = context["injectedArtifacts"][0]
        self.assertEqual("parent", artifact["taskId"])
        self.assertEqual(
            self.dispatcher.REPORT_BYTES_LIMIT, len(artifact["content"].encode())
        )
        self.assertTrue(artifact["truncated"])

    def test_absent_parent_report_blocks_child_without_launching(self) -> None:
        run_dir = self.complete_parent()
        (run_dir / "report.md").unlink()

        with patch.object(self.dispatcher, "launch_worker") as launch:
            self.dispatcher.tick(self.db, self.workflow_id, self.root)

        launch.assert_not_called()
        self.assertEqual(
            "blocked",
            self.db.execute(
                "SELECT state FROM tasks WHERE workflow_id=? AND id='child'",
                (self.workflow_id,),
            ).fetchone()[0],
        )


if __name__ == "__main__":
    unittest.main()
