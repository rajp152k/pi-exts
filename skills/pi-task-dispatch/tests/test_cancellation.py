"""Deterministic cancellation intent/reconciliation tests; no tmux or Pi needed."""

import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "scripts" / "task-dispatch.py"


def load():
    spec = importlib.util.spec_from_file_location("cancellation_dispatch", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CancellationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = load()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "runs"
        self.database = str(Path(self.temp.name) / "workflow.db")
        self.db = self.d.db_connect(self.database)
        self.d.create_workflow(
            self.db,
            {
                "id": "cancel-fixture",
                "cwd": str(Path.cwd()),
                "tmuxSession": "unused",
                "tasks": [{"id": "one", "prompt": "one"}],
            },
        )
        with self.db:
            self.d.refresh(self.db, "cancel-fixture")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def seed_attempt(self, name="attempt"):
        run_dir = self.root / name
        with self.db:
            self.db.execute("UPDATE tasks SET state='in_progress' WHERE id='one'")
            self.db.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    name,
                    "cancel-fixture",
                    "one",
                    str(run_dir),
                    "in_progress",
                    None,
                    self.d.now(),
                    None,
                    None,
                    None,
                ),
            )
            self.db.execute(
                "INSERT INTO dispatch_outbox VALUES(?,?,?,?,?,?,?,NULL)",
                (
                    name,
                    "cancel-fixture",
                    "one",
                    str(run_dir),
                    "pending",
                    self.d.now(),
                    self.d.now(),
                ),
            )
            self.db.execute(
                "INSERT INTO resource_leases VALUES(?,?,?,?)",
                ("cancel-fixture", "repo:test", name, self.d.now()),
            )
        return name, run_dir

    def command_cancel(self):
        self.d.command_workflow_cancel(
            type(
                "Args",
                (),
                {"database": self.database, "id": "cancel-fixture", "task": "one"},
            )()
        )

    def test_cancel_is_durable_then_acknowledged_then_observed_terminal(self):
        attempt, run_dir = self.seed_attempt()
        run_dir.mkdir(parents=True)
        self.d.write_json(
            run_dir / "manifest.json",
            {"state": "cancelling", "tmux": {"windowId": "@live"}},
        )
        self.command_cancel()
        self.assertTrue((run_dir / "cancel-requested").exists())
        self.assertEqual(
            "delivered",
            self.db.execute(
                "SELECT state FROM attempt_cancellations WHERE attempt_id=?", (attempt,)
            ).fetchone()[0],
        )
        with patch.object(self.d, "window_exists", return_value=True), self.db:
            self.d.refresh(self.db, "cancel-fixture")
        self.assertEqual(
            "acknowledged",
            self.db.execute(
                "SELECT state FROM attempt_cancellations WHERE attempt_id=?", (attempt,)
            ).fetchone()[0],
        )
        self.d.write_json(run_dir / "manifest.json", {"state": "cancelled", "tmux": {}})
        with self.db:
            self.d.refresh(self.db, "cancel-fixture")
        self.assertEqual(
            "observed-terminal",
            self.db.execute(
                "SELECT state FROM attempt_cancellations WHERE attempt_id=?", (attempt,)
            ).fetchone()[0],
        )
        self.assertEqual(
            "cancelled",
            self.db.execute("SELECT state FROM tasks WHERE id='one'").fetchone()[0],
        )
        self.assertEqual(
            0, self.db.execute("SELECT COUNT(*) FROM resource_leases").fetchone()[0]
        )

    def test_completed_terminal_wins_racing_cancel_request(self):
        attempt, run_dir = self.seed_attempt()
        run_dir.mkdir(parents=True)
        self.d.write_json(run_dir / "manifest.json", {"state": "completed", "tmux": {}})
        self.command_cancel()
        self.assertEqual(
            "done",
            self.db.execute("SELECT state FROM tasks WHERE id='one'").fetchone()[0],
        )
        self.assertIsNone(
            self.db.execute(
                "SELECT 1 FROM attempt_cancellations WHERE attempt_id=?", (attempt,)
            ).fetchone()
        )

    def test_cancellation_never_launches_a_pending_attempt_and_ambiguity_fails_closed(
        self,
    ):
        attempt, _ = self.seed_attempt()
        self.command_cancel()
        with patch.object(self.d, "launch_worker") as launch, self.db:
            self.d.reconcile_dispatch_outbox(self.db, "cancel-fixture", self.root)
        launch.assert_not_called()
        self.assertEqual(
            "lost",
            self.db.execute(
                "SELECT state FROM attempts WHERE id=?", (attempt,)
            ).fetchone()[0],
        )
        self.assertEqual(
            0, self.db.execute("SELECT COUNT(*) FROM resource_leases").fetchone()[0]
        )

    def test_pause_blocks_new_dispatch_and_resume_restores_desired_running(self):
        self.d.command_workflow_pause(
            type("Args", (), {"database": self.database, "id": "cancel-fixture"})()
        )
        with patch.object(self.d, "launch_worker") as launch:
            self.d.tick(self.db, "cancel-fixture", self.root)
        launch.assert_not_called()
        self.d.command_workflow_resume(
            type("Args", (), {"database": self.database, "id": "cancel-fixture"})()
        )
        self.assertEqual(
            "running", self.d.workflow_desired_state(self.db, "cancel-fixture")
        )

    def test_legacy_workflow_state_migrates_without_rewrite(self):
        path = Path(self.temp.name) / "legacy.db"
        legacy = sqlite3.connect(path)
        legacy.execute(
            "CREATE TABLE workflows (id TEXT PRIMARY KEY, name TEXT NOT NULL, cwd TEXT NOT NULL, tmux_session TEXT NOT NULL, max_concurrency INTEGER NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        legacy.execute(
            "INSERT INTO workflows VALUES ('old','old','/tmp','s',1,'cancelled','then','now')"
        )
        legacy.commit()
        legacy.close()
        migrated = self.d.db_connect(str(path))
        self.assertEqual("cancelled", self.d.workflow_desired_state(migrated, "old"))
        self.assertEqual(
            "cancelled",
            migrated.execute("SELECT state FROM workflows WHERE id='old'").fetchone()[
                0
            ],
        )
        migrated.close()


if __name__ == "__main__":
    unittest.main()
