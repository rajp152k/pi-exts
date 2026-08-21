"""MVP policy behavior: durable retry decisions, backoff, and safe failures."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "scripts" / "task-dispatch.py"


def load():
    spec = importlib.util.spec_from_file_location("policy_dispatch", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = load()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "runs"
        self.db = self.d.db_connect(str(Path(self.temp.name) / "db"))
        self.d.create_workflow(
            self.db,
            {
                "id": "policy",
                "cwd": str(Path.cwd()),
                "tmuxSession": "none",
                "tasks": [
                    {
                        "id": "one",
                        "prompt": "x",
                        "maxRetries": 1,
                        "retryOn": ["transport"],
                        "retryBackoffSeconds": 10,
                    }
                ],
            },
        )
        with self.db:
            self.d.refresh(self.db, "policy")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def seed(self, error):
        run = self.root / "old"
        run.mkdir(parents=True)
        aid = "a1"
        with self.db:
            self.db.execute(
                "UPDATE tasks SET state='in_progress' WHERE workflow_id='policy' AND id='one'"
            )
            self.db.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    aid,
                    "policy",
                    "one",
                    str(run),
                    "in_progress",
                    None,
                    self.d.now(),
                    None,
                    None,
                    None,
                ),
            )
            self.db.execute(
                "INSERT INTO attempt_policies VALUES(?,?,?,?,?,?,?,?)",
                (aid, 1, 0, None, 0, 0, None, "scheduled"),
            )
            self.db.execute(
                "INSERT INTO dispatch_outbox VALUES(?,?,?,?,?,?,?,NULL)",
                (
                    aid,
                    "policy",
                    "one",
                    str(run),
                    "launched",
                    self.d.now(),
                    self.d.now(),
                ),
            )
            self.d.write_json(
                run / "manifest.json", {"state": "failed", "error": error}
            )
        return aid

    def test_safe_transport_retry_waits_for_backoff(self):
        aid = self.seed("transport: disconnected")
        with patch.object(self.d, "policy_clock", return_value=100):
            self.d.refresh(self.db, "policy")
        self.assertEqual(
            "queued",
            self.db.execute("SELECT state FROM tasks WHERE id='one'").fetchone()[0],
        )
        with patch.object(self.d, "policy_clock", return_value=110):
            self.d.refresh(self.db, "policy")
        self.assertEqual(
            "ready",
            self.db.execute("SELECT state FROM tasks WHERE id='one'").fetchone()[0],
        )
        self.assertEqual(
            1,
            self.db.execute(
                "SELECT retry_eligible FROM attempt_policies WHERE attempt_id=?", (aid,)
            ).fetchone()[0],
        )

    def test_unsafe_failure_never_retries(self):
        self.seed("worktree: side effect may have occurred")
        with patch.object(self.d, "policy_clock", return_value=100):
            self.d.refresh(self.db, "policy")
        self.assertEqual(
            "failed",
            self.db.execute("SELECT state FROM tasks WHERE id='one'").fetchone()[0],
        )

    def test_writer_retry_requires_exact_attempt_revision_approval(self):
        aid = self.seed("transport: disconnected")
        with self.db:
            self.db.execute("UPDATE tasks SET access='default-tools' WHERE id='one'")
            self.db.execute(
                "UPDATE task_policies SET policy=? WHERE workflow_id='policy' AND task_id='one'",
                ('{"maxRetries":1,"retryOn":["transport"],"idempotency":true}',),
            )
            self.db.execute(
                "INSERT INTO attempt_snapshots VALUES(?,?,?,?,?,?)",
                (
                    aid,
                    "policy",
                    1,
                    self.d.current_revision_hash(self.db, "policy")[1],
                    "{}",
                    self.d.now(),
                ),
            )
        with patch.object(self.d, "policy_clock", return_value=10):
            self.d.refresh(self.db, "policy")
        self.assertEqual(
            "failed",
            self.db.execute("SELECT state FROM tasks WHERE id='one'").fetchone()[0],
        )

        # Approval is bound to this failed attempt and its pinned revision.
        with self.db:
            self.db.execute(
                "UPDATE attempts SET state='in_progress' WHERE id=?", (aid,)
            )
            self.db.execute("UPDATE tasks SET state='in_progress' WHERE id='one'")
            self.db.execute(
                "INSERT INTO retry_approvals VALUES(?,?,?,?,?,?)",
                ("policy", aid, 1, "approved", "user", self.d.now()),
            )
        with patch.object(self.d, "policy_clock", return_value=20):
            self.d.refresh(self.db, "policy")
        with patch.object(self.d, "policy_clock", return_value=21):
            self.d.refresh(self.db, "policy")
        self.assertEqual(
            "ready",
            self.db.execute("SELECT state FROM tasks WHERE id='one'").fetchone()[0],
        )

    def test_declared_budget_refuses_schedule(self):
        self.db.close()
        self.db = self.d.db_connect(str(Path(self.temp.name) / "budget-db"))
        self.d.create_workflow(
            self.db,
            {
                "id": "budget",
                "cwd": str(Path.cwd()),
                "tmuxSession": "none",
                "tasks": [{"id": "one", "prompt": "x", "tokenBudget": 3}],
            },
        )
        with patch.object(self.d, "launch_worker") as launch:
            self.d.tick(self.db, "budget", self.root)
        launch.assert_not_called()
        self.assertEqual(
            "blocked",
            self.db.execute("SELECT state FROM tasks WHERE id='one'").fetchone()[0],
        )


if __name__ == "__main__":
    unittest.main()
