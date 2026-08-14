"""Deterministic scheduler lease and dispatch-outbox tests."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "task-dispatch.py"


def load_dispatcher() -> Any:
    spec = importlib.util.spec_from_file_location("task_dispatch_scheduler", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SchedulerSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dispatcher = load_dispatcher()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "runs"
        self.db = self.dispatcher.db_connect(
            str(Path(self.temporary.name) / "db.sqlite")
        )
        self.spec = {
            "id": "scheduler-fixture",
            "cwd": str(Path.cwd()),
            "tmuxSession": "fixture-session",
            "maxConcurrency": 1,
            "tasks": [{"id": "one", "prompt": "Do one bounded thing."}],
        }
        self.dispatcher.create_workflow(self.db, self.spec)
        with self.db:
            self.dispatcher.refresh(self.db, self.spec["id"])

    def tearDown(self) -> None:
        self.db.close()
        self.temporary.cleanup()

    def test_scheduler_lease_excludes_second_owner_and_can_be_released(self) -> None:
        workflow_id = self.spec["id"]
        self.assertEqual(
            "owner-one",
            self.dispatcher.acquire_scheduler_lease(
                self.db, workflow_id, owner="owner-one"
            ),
        )
        self.assertIsNone(
            self.dispatcher.acquire_scheduler_lease(
                self.db, workflow_id, owner="owner-two"
            )
        )
        self.dispatcher.release_scheduler_lease(self.db, workflow_id, "owner-one")
        self.assertEqual(
            "owner-two",
            self.dispatcher.acquire_scheduler_lease(
                self.db, workflow_id, owner="owner-two"
            ),
        )

    def test_expired_scheduler_lease_is_reclaimed(self) -> None:
        workflow_id = self.spec["id"]
        with self.db:
            self.db.execute(
                "INSERT INTO scheduler_leases VALUES(?,?,?)", (workflow_id, "old", 0.0)
            )
        self.assertEqual(
            "new",
            self.dispatcher.acquire_scheduler_lease(self.db, workflow_id, owner="new"),
        )

    def test_tick_records_one_attempt_and_does_not_duplicate_dispatch(self) -> None:
        launches: list[str] = []

        def launch(**kwargs: Any) -> Path:
            launches.append(kwargs["task_id"])
            run_dir = kwargs["run_dir"]
            run_dir.mkdir(parents=True, exist_ok=True)
            self.dispatcher.write_json(
                run_dir / "manifest.json",
                {
                    "state": "running",
                    "tmux": {"paneId": "%test", "windowId": "@test"},
                },
            )
            return run_dir

        with (
            patch.object(self.dispatcher, "launch_worker", side_effect=launch),
            patch.object(self.dispatcher, "window_exists", return_value=True),
        ):
            self.dispatcher.tick(self.db, self.spec["id"], self.root)
            self.dispatcher.tick(self.db, self.spec["id"], self.root)
        self.assertEqual(["one"], launches)
        self.assertEqual(
            1,
            self.db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],
        )
        self.assertEqual(
            1,
            self.db.execute(
                "SELECT COUNT(*) FROM dispatch_outbox WHERE state='launched'"
            ).fetchone()[0],
        )

    def test_read_leases_share_and_writer_waits_for_their_release(self) -> None:
        spec = {
            "id": "rw-fixture",
            "cwd": str(Path.cwd()),
            "tmuxSession": "fixture-session",
            "maxConcurrency": 3,
            "tasks": [
                {"id": "reader-one", "prompt": "Read one.", "resources": ["read:repo"]},
                {"id": "reader-two", "prompt": "Read two.", "resources": ["read:repo"]},
                {"id": "writer", "prompt": "Write.", "resources": ["write:repo"]},
            ],
        }
        self.dispatcher.create_workflow(self.db, spec)
        with self.db:
            self.dispatcher.refresh(self.db, spec["id"])
        launches: list[str] = []

        def launch(**kwargs: Any) -> Path:
            launches.append(kwargs["task_id"])
            run_dir = kwargs["run_dir"]
            run_dir.mkdir(parents=True, exist_ok=True)
            self.dispatcher.write_json(
                run_dir / "manifest.json",
                {"state": "running", "tmux": {"paneId": "%rw", "windowId": "@rw"}},
            )
            return run_dir

        with (
            patch.object(self.dispatcher, "launch_worker", side_effect=launch),
            patch.object(self.dispatcher, "window_exists", return_value=True),
        ):
            self.dispatcher.tick(self.db, spec["id"], self.root)
            self.assertEqual(["reader-one", "reader-two"], launches)
            leases = [
                row[0]
                for row in self.db.execute(
                    "SELECT resource FROM resource_leases WHERE workflow_id=? ORDER BY resource",
                    (spec["id"],),
                )
            ]
            self.assertEqual(["read:repo", "read:repo"], leases)
            deferred = self.db.execute(
                "SELECT detail FROM events WHERE workflow_id=? AND type='scheduler.deferred'",
                (spec["id"],),
            ).fetchone()[0]
            detail = self.dispatcher.json.loads(deferred)
            self.assertEqual(["write:repo"], detail["requestedLeases"])
            self.assertEqual(["read:repo"], detail["heldLeases"])
            for (run_dir,) in self.db.execute(
                "SELECT run_dir FROM attempts WHERE workflow_id=?", (spec["id"],)
            ):
                self.dispatcher.write_json(
                    Path(run_dir) / "manifest.json",
                    {
                        "state": "completed",
                        "finishedAt": self.dispatcher.now(),
                        "tmux": {},
                    },
                )
            self.dispatcher.tick(self.db, spec["id"], self.root)
        self.assertEqual(["reader-one", "reader-two", "writer"], launches)

    def test_resource_mode_validation_and_legacy_exclusivity(self) -> None:
        base = {
            "id": "invalid-resources",
            "cwd": str(Path.cwd()),
            "tmuxSession": "fixture-session",
            "tasks": [{"id": "one", "prompt": "Test.", "resources": ["read:"]}],
        }
        malformed = [
            item
            for item in self.dispatcher.validate_spec(base)
            if item["severity"] == "error"
        ]
        self.assertTrue(
            any(item["code"] == "invalid-resource-lease" for item in malformed)
        )
        base["tasks"][0]["resources"] = ["read:repo", "write:repo"]
        conflicting = [
            item
            for item in self.dispatcher.validate_spec(base)
            if item["severity"] == "error"
        ]
        self.assertTrue(
            any(item["code"] == "invalid-resource-lease" for item in conflicting)
        )
        with self.assertRaises(ValueError):
            self.dispatcher.normalize_resource(":repo")
        self.assertFalse(self.dispatcher.leases_conflict("read:repo", "read:repo"))
        self.assertTrue(self.dispatcher.leases_conflict("write:repo", "read:repo"))
        self.assertTrue(self.dispatcher.leases_conflict("read:repo", "write:repo"))
        self.assertTrue(
            self.dispatcher.leases_conflict("read:worktree:one", "worktree:one")
        )

    def test_reconciliation_marks_failed_launch_and_releases_resources(self) -> None:
        with self.db:
            self.db.execute(
                "UPDATE tasks SET state='in_progress' WHERE workflow_id=? AND id='one'",
                (self.spec["id"],),
            )
            self.db.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    "attempt",
                    self.spec["id"],
                    "one",
                    str(self.root / "missing"),
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
                    self.spec["id"],
                    "one",
                    str(self.root / "missing"),
                    "pending",
                    self.dispatcher.now(),
                    self.dispatcher.now(),
                ),
            )
            self.db.execute(
                "INSERT INTO resource_leases VALUES(?,?,?,?)",
                (self.spec["id"], "repo:fixture", "attempt", self.dispatcher.now()),
            )
        with (
            self.db,
            patch.object(
                self.dispatcher,
                "launch_worker",
                side_effect=SystemExit("tmux unavailable"),
            ),
        ):
            self.dispatcher.reconcile_dispatch_outbox(
                self.db, self.spec["id"], self.root
            )
        self.assertEqual(
            "failed",
            self.db.execute("SELECT state FROM attempts WHERE id='attempt'").fetchone()[
                0
            ],
        )
        self.assertEqual(
            0,
            self.db.execute(
                "SELECT COUNT(*) FROM resource_leases WHERE attempt_id='attempt'"
            ).fetchone()[0],
        )
        self.assertEqual(
            "failed",
            self.db.execute(
                "SELECT state FROM dispatch_outbox WHERE attempt_id='attempt'"
            ).fetchone()[0],
        )

    def test_authoritative_completion_releases_resource_lease(self) -> None:
        run_dir = self.root / "completed"
        run_dir.mkdir(parents=True)
        self.dispatcher.write_json(
            run_dir / "manifest.json",
            {
                "state": "completed",
                "finishedAt": self.dispatcher.now(),
                "tmux": {"windowId": "%none"},
            },
        )
        with self.db:
            self.db.execute(
                "UPDATE tasks SET state='in_progress' WHERE workflow_id=? AND id='one'",
                (self.spec["id"],),
            )
            self.db.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    "completed-attempt",
                    self.spec["id"],
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
                "INSERT INTO resource_leases VALUES(?,?,?,?)",
                (
                    self.spec["id"],
                    "repo:fixture",
                    "completed-attempt",
                    self.dispatcher.now(),
                ),
            )
            self.dispatcher.refresh(self.db, self.spec["id"])
        self.assertEqual(
            0,
            self.db.execute(
                "SELECT COUNT(*) FROM resource_leases WHERE attempt_id='completed-attempt'"
            ).fetchone()[0],
        )


if __name__ == "__main__":
    unittest.main()
