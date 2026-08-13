"""Deterministic revision persistence and human-gate scheduler tests."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "scripts" / "task-dispatch.py"


def load() -> Any:
    spec = importlib.util.spec_from_file_location("task_dispatch_revisions", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WorkflowRevisionGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.d = load()

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = self.d.db_connect(str(Path(self.tmp.name) / "workflow.sqlite"))
        self.root = Path(self.tmp.name) / "runs"
        self.spec = {
            "id": "revision-gate-fixture",
            "cwd": str(Path.cwd()),
            "tmuxSession": "fixture",
            "maxConcurrency": 1,
            "tasks": [
                {
                    "id": "review-write",
                    "kind": "gate",
                    "gateType": "write_dispatch",
                    "prompt": "Approve writer",
                    "objective": "Review write scope.",
                    "deliverable": "Approval decision.",
                    "completionEvidence": "Decision recorded.",
                    "handoff": "status",
                },
                {
                    "id": "writer",
                    "prompt": "Write",
                    "access": "default-tools",
                    "resources": ["worktree:writer"],
                    "dependsOn": ["review-write"],
                    "objective": "Make bounded change.",
                    "deliverable": "Change.",
                    "completionEvidence": "Tests.",
                    "handoff": "status",
                },
            ],
        }
        self.d.create_workflow(self.db, self.spec)

    def tearDown(self) -> None:
        self.db.close()
        self.tmp.cleanup()

    def state(self, task: str) -> str:
        return self.db.execute(
            "SELECT state FROM tasks WHERE workflow_id=? AND id=?",
            (self.spec["id"], task),
        ).fetchone()[0]

    def test_initial_revision_is_immutable_and_hash_stable(self) -> None:
        row = self.db.execute(
            "SELECT revision, spec, content_hash FROM workflow_revisions"
        ).fetchone()
        self.assertEqual(1, row["revision"])
        self.assertEqual(
            self.d.canonical_spec(self.spec), (row["spec"], row["content_hash"])
        )
        self.assertEqual([], self.d.revision_findings(self.db, self.spec["id"]))

    def test_gate_never_creates_attempt_and_approval_releases_writer(self) -> None:
        with self.db:
            self.d.refresh(self.db, self.spec["id"])
        self.assertEqual("queued", self.state("review-write"))
        self.assertEqual(
            0, self.db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        )
        with self.db:
            self.db.execute(
                "INSERT INTO gate_approvals VALUES(?,?,?,?,?,?,?)",
                (
                    self.spec["id"],
                    "review-write",
                    1,
                    "approved",
                    "alice",
                    "checked",
                    self.d.now(),
                ),
            )
            self.d.refresh(self.db, self.spec["id"])
        self.assertEqual("done", self.state("review-write"))
        self.assertEqual("ready", self.state("writer"))

        def launch(**kwargs: Any) -> Path:
            run_dir = kwargs["run_dir"]
            run_dir.mkdir(parents=True)
            self.d.write_json(
                run_dir / "manifest.json",
                {
                    "state": "running",
                    "tmux": {"paneId": "%fixture", "windowId": "@fixture"},
                },
            )
            return run_dir

        with (
            patch.object(self.d, "launch_worker", side_effect=launch) as launch_mock,
            patch.object(self.d, "window_exists", return_value=True),
        ):
            self.d.tick(self.db, self.spec["id"], self.root)
        self.assertEqual(1, launch_mock.call_count)
        self.assertEqual("writer", launch_mock.call_args.kwargs["task_id"])

    def test_revise_invalidates_approval_and_refining_refuses_scheduler(self) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO gate_approvals VALUES(?,?,?,?,?,?,?)",
                (
                    self.spec["id"],
                    "review-write",
                    1,
                    "approved",
                    "alice",
                    "checked",
                    self.d.now(),
                ),
            )
            revised = json.loads(json.dumps(self.spec))
            revised["name"] = "changed"
            revision = self.d.persist_revision(
                self.db, self.spec["id"], revised, rationale="scope changed"
            )
            self.db.execute(
                "UPDATE workflows SET state='refining' WHERE id=?", (self.spec["id"],)
            )
        self.assertEqual(2, revision)
        self.assertIsNone(
            self.d.gate_decision(self.db, self.spec["id"], "review-write")
        )
        with patch.object(self.d, "launch_worker") as launch:
            self.d.tick(self.db, self.spec["id"], self.root)
        launch.assert_not_called()
        self.assertEqual(
            0, self.db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        )

    def test_validation_errors_are_persisted_and_block_scheduler(self) -> None:
        invalid = json.loads(json.dumps(self.spec))
        invalid["tasks"][1]["dependsOn"] = ["missing"]
        with self.db:
            revision = self.d.persist_revision(
                self.db, self.spec["id"], invalid, rationale="bad revision"
            )
        self.assertEqual(
            ["missing-dependency"],
            [
                x["code"]
                for x in self.d.revision_findings(self.db, self.spec["id"], revision)
            ],
        )
        with patch.object(self.d, "launch_worker") as launch:
            self.d.tick(self.db, self.spec["id"], self.root)
        launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
