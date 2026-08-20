"""Deterministic fencing tests; no tmux or Pi process is started."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "scripts" / "task-dispatch.py"


def load_dispatcher() -> Any:
    spec = importlib.util.spec_from_file_location("task_dispatch_fencing", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SchedulerFencingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dispatcher = load_dispatcher()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.db = self.dispatcher.db_connect(
            str(Path(self.temporary.name) / "db.sqlite")
        )
        self.root = Path(self.temporary.name) / "runs"
        self.workflow_id = "fence-fixture"
        self.dispatcher.create_workflow(
            self.db,
            {
                "id": self.workflow_id,
                "cwd": str(Path.cwd()),
                "tmuxSession": "fence-session",
                "tasks": [{"id": "one", "prompt": "Fence one."}],
            },
        )
        with self.db:
            self.dispatcher.refresh(self.db, self.workflow_id)
            run_dir = self.root / "one"
            self.db.execute(
                "UPDATE tasks SET state='in_progress' WHERE workflow_id=? AND id='one'",
                (self.workflow_id,),
            )
            self.db.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    "attempt",
                    self.workflow_id,
                    "one",
                    str(run_dir),
                    "in_progress",
                    None,
                    self.dispatcher.now(),
                    None,
                    None,
                    None,
                ),
            )
            self.db.execute(
                "INSERT INTO dispatch_outbox VALUES(?,?,?,?,?,?,?,NULL)",
                (
                    "attempt",
                    self.workflow_id,
                    "one",
                    str(run_dir),
                    "pending",
                    self.dispatcher.now(),
                    self.dispatcher.now(),
                ),
            )

    def tearDown(self) -> None:
        self.db.close()
        self.temporary.cleanup()

    def test_expired_takeover_increments_generation_without_deleting_lease(
        self,
    ) -> None:
        first = self.dispatcher.acquire_scheduler_lease(
            self.db, self.workflow_id, owner="first", lease_seconds=0
        )
        self.assertEqual(("first", 1), first)
        second = self.dispatcher.acquire_scheduler_lease(
            self.db, self.workflow_id, owner="second"
        )
        self.assertEqual(("second", 2), second)
        row = self.db.execute(
            "SELECT owner,generation FROM scheduler_leases WHERE workflow_id=?",
            (self.workflow_id,),
        ).fetchone()
        self.assertEqual(("second", 2), tuple(row))

    def test_ambiguous_launching_claim_is_lost_and_never_relaunched(self) -> None:
        fence = self.dispatcher.acquire_scheduler_lease(
            self.db, self.workflow_id, owner="owner"
        )
        assert fence is not None
        with self.db:
            self.db.execute(
                "UPDATE dispatch_outbox SET state='launching' WHERE attempt_id='attempt'"
            )
            self.db.execute(
                "INSERT INTO dispatch_launch_claims VALUES(?,?,?,?)",
                ("attempt", fence[0], fence[1], self.dispatcher.now()),
            )
        with patch.object(self.dispatcher, "launch_worker") as launch:
            self.dispatcher.reconcile_workflow(
                self.db, self.workflow_id, self.root, fence=fence
            )
        launch.assert_not_called()
        self.assertEqual(
            "lost",
            self.db.execute(
                "SELECT state FROM dispatch_outbox WHERE attempt_id='attempt'"
            ).fetchone()[0],
        )
        self.assertEqual(
            "failed",
            self.db.execute(
                "SELECT state FROM tasks WHERE workflow_id=? AND id='one'",
                (self.workflow_id,),
            ).fetchone()[0],
        )


if __name__ == "__main__":
    unittest.main()
