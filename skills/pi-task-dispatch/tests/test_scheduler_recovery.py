"""Deterministic recovery acceptance tests for the scheduler dispatch outbox."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "scripts" / "task-dispatch.py"


def load_dispatcher() -> Any:
    spec = importlib.util.spec_from_file_location("task_dispatch_recovery", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SchedulerRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dispatcher = load_dispatcher()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "runs"
        self.db = self.dispatcher.db_connect(
            str(Path(self.temporary.name) / "db.sqlite")
        )
        self.workflow_id = "recovery-fixture"
        self.dispatcher.create_workflow(
            self.db,
            {
                "id": self.workflow_id,
                "cwd": str(Path.cwd()),
                "tmuxSession": "recovery-session",
                "maxConcurrency": 1,
                "tasks": [
                    {"id": "one", "prompt": "Recover one worker."},
                    {"id": "two", "prompt": "Unrelated ready worker."},
                ],
            },
        )
        with self.db:
            self.dispatcher.refresh(self.db, self.workflow_id)

    def tearDown(self) -> None:
        self.db.close()
        self.temporary.cleanup()

    def seed_pending_attempt(
        self, name: str, *, pane: str | None = None
    ) -> tuple[str, Path]:
        attempt_id = f"attempt-{name}"
        run_dir = self.root / name
        with self.db:
            self.db.execute(
                "UPDATE tasks SET state='in_progress' WHERE workflow_id=? AND id='one'",
                (self.workflow_id,),
            )
            self.db.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    attempt_id,
                    self.workflow_id,
                    "one",
                    str(run_dir),
                    "in_progress",
                    pane,
                    self.dispatcher.now(),
                    None,
                    None,
                    None,
                ),
            )
            self.db.execute(
                "INSERT INTO dispatch_outbox VALUES(?,?,?,?,?,?,?,NULL)",
                (
                    attempt_id,
                    self.workflow_id,
                    "one",
                    str(run_dir),
                    "pending",
                    self.dispatcher.now(),
                    self.dispatcher.now(),
                ),
            )
        return attempt_id, run_dir

    def attempt_state(self, attempt_id: str) -> str:
        return self.db.execute(
            "SELECT state FROM attempts WHERE id=?", (attempt_id,)
        ).fetchone()[0]

    def outbox_state(self, attempt_id: str) -> str:
        return self.db.execute(
            "SELECT state FROM dispatch_outbox WHERE attempt_id=?", (attempt_id,)
        ).fetchone()[0]

    def test_running_manifest_with_live_target_is_adopted_without_launching(
        self,
    ) -> None:
        attempt_id, run_dir = self.seed_pending_attempt("live-manifest")
        run_dir.mkdir(parents=True)
        self.dispatcher.write_json(
            run_dir / "manifest.json",
            {"state": "running", "tmux": {"windowId": "@live", "paneId": "%live"}},
        )

        with (
            patch.object(self.dispatcher, "window_exists", return_value=True) as exists,
            patch.object(self.dispatcher, "launch_worker") as launch,
        ):
            self.dispatcher.reconcile_dispatch_outbox(
                self.db, self.workflow_id, self.root
            )

        launch.assert_not_called()
        exists.assert_called_once_with("@live")
        self.assertEqual("in_progress", self.attempt_state(attempt_id))
        self.assertEqual("launched", self.outbox_state(attempt_id))
        self.assertEqual(
            "%live",
            self.db.execute(
                "SELECT tmux_pane FROM attempts WHERE id=?", (attempt_id,)
            ).fetchone()[0],
        )

    def test_missing_manifest_with_live_target_becomes_orphan_and_is_not_relaunched(
        self,
    ) -> None:
        attempt_id, _ = self.seed_pending_attempt("orphan", pane="%orphan")
        with self.db:
            self.db.execute(
                "INSERT INTO resource_leases VALUES(?,?,?,?)",
                (self.workflow_id, "repo:orphan", attempt_id, self.dispatcher.now()),
            )
        with (
            patch.object(self.dispatcher, "window_exists", return_value=True) as exists,
            patch.object(self.dispatcher, "launch_worker") as launch,
        ):
            self.dispatcher.reconcile_dispatch_outbox(
                self.db, self.workflow_id, self.root
            )
            self.dispatcher.reconcile_dispatch_outbox(
                self.db, self.workflow_id, self.root
            )

        self.assertEqual(2, exists.call_count)
        exists.assert_called_with("%orphan")
        launch.assert_not_called()
        self.assertEqual("orphaned", self.attempt_state(attempt_id))
        self.assertEqual("orphaned", self.outbox_state(attempt_id))
        self.assertEqual(
            1,
            self.db.execute(
                "SELECT COUNT(*) FROM resource_leases WHERE attempt_id=?", (attempt_id,)
            ).fetchone()[0],
        )
        self.assertEqual(
            "in_progress",
            self.db.execute(
                "SELECT state FROM tasks WHERE workflow_id=? AND id='one'",
                (self.workflow_id,),
            ).fetchone()[0],
        )

    def test_vanished_orphan_is_durably_failed_and_releases_lease_once(
        self,
    ) -> None:
        attempt_id, _ = self.seed_pending_attempt("lost", pane="%gone")
        with self.db:
            self.db.execute(
                "INSERT INTO resource_leases VALUES(?,?,?,?)",
                (self.workflow_id, "repo:recovery", attempt_id, self.dispatcher.now()),
            )

        with patch.object(
            self.dispatcher, "window_exists", side_effect=[True, False]
        ) as exists:
            self.dispatcher.reconcile_dispatch_outbox(
                self.db, self.workflow_id, self.root
            )
            self.assertEqual("orphaned", self.attempt_state(attempt_id))
            self.dispatcher.reconcile_dispatch_outbox(
                self.db, self.workflow_id, self.root
            )
            self.dispatcher.reconcile_dispatch_outbox(
                self.db, self.workflow_id, self.root
            )

        self.assertEqual(2, exists.call_count)
        self.assertEqual("lost", self.attempt_state(attempt_id))
        self.assertEqual("lost", self.outbox_state(attempt_id))
        self.assertEqual(
            "failed",
            self.db.execute(
                "SELECT state FROM tasks WHERE workflow_id=? AND id='one'",
                (self.workflow_id,),
            ).fetchone()[0],
        )
        self.assertEqual(
            0,
            self.db.execute(
                "SELECT COUNT(*) FROM resource_leases WHERE attempt_id=?", (attempt_id,)
            ).fetchone()[0],
        )
        self.assertEqual(
            1,
            self.db.execute(
                "SELECT COUNT(*) FROM events WHERE attempt_id=? AND type='dispatch.failed'",
                (attempt_id,),
            ).fetchone()[0],
        )

    def test_live_orphan_does_not_change_ready_work_capacity_behavior(self) -> None:
        self.seed_pending_attempt("orphan-capacity", pane="%orphan")
        launches: list[str] = []

        def launch(**kwargs: Any) -> Path:
            launches.append(kwargs["task_id"])
            kwargs["run_dir"].mkdir(parents=True)
            self.dispatcher.write_json(
                kwargs["run_dir"] / "manifest.json",
                {"state": "running", "tmux": {"windowId": "@two", "paneId": "%two"}},
            )
            return kwargs["run_dir"]

        with (
            patch.object(self.dispatcher, "window_exists", return_value=True),
            patch.object(self.dispatcher, "launch_worker", side_effect=launch),
        ):
            self.dispatcher.tick(self.db, self.workflow_id, self.root)

        self.assertEqual(["two"], launches)
        self.assertEqual(
            "in_progress",
            self.db.execute(
                "SELECT state FROM tasks WHERE workflow_id=? AND id='two'",
                (self.workflow_id,),
            ).fetchone()[0],
        )

    def test_pending_outbox_without_a_run_directory_launches_once(self) -> None:
        attempt_id, run_dir = self.seed_pending_attempt("not-created")
        launches: list[str] = []

        def launch(**kwargs: Any) -> Path:
            launches.append(kwargs["task_id"])
            kwargs["run_dir"].mkdir(parents=True)
            self.dispatcher.write_json(
                kwargs["run_dir"] / "manifest.json",
                {"state": "running", "tmux": {"windowId": "@new", "paneId": "%new"}},
            )
            return kwargs["run_dir"]

        with patch.object(self.dispatcher, "launch_worker", side_effect=launch):
            self.dispatcher.reconcile_dispatch_outbox(
                self.db, self.workflow_id, self.root
            )
            self.dispatcher.reconcile_dispatch_outbox(
                self.db, self.workflow_id, self.root
            )

        self.assertEqual(["one"], launches)
        self.assertTrue(run_dir.is_dir())
        self.assertEqual("launched", self.outbox_state(attempt_id))
        self.assertEqual(
            "%new",
            self.db.execute(
                "SELECT tmux_pane FROM attempts WHERE id=?", (attempt_id,)
            ).fetchone()[0],
        )


if __name__ == "__main__":
    unittest.main()
