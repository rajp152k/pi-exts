"""Managed-worktree MVP tests; all Git/tmux boundaries are mocked."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "scripts" / "task-dispatch.py"


def load() -> Any:
    spec = importlib.util.spec_from_file_location("task_dispatch_worktrees", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ManagedWorktreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.d = load()

    def test_managed_writer_needs_no_manual_resource(self) -> None:
        spec = {
            "tasks": [
                {
                    "id": "writer",
                    "access": "default-tools",
                    "managedWorktrees": True,
                    "objective": "x",
                    "deliverable": "x",
                    "completionEvidence": "x",
                    "handoff": "x",
                }
            ]
        }
        codes = {x["code"] for x in self.d.validate_spec(spec)}
        self.assertNotIn("missing-worktree-resource", codes)

    def test_dirty_source_fails_closed(self) -> None:
        with patch.object(self.d, "git_value", side_effect=["true", "dirty"]):
            self.assertFalse(self.d.source_is_clean(Path("/source")))

    def test_audit_marks_undeclared_changes_failed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = self.d.db_connect(str(Path(directory) / "db.sqlite"))
            db.execute(
                "INSERT INTO workflows VALUES(?,?,?,?,?,?,?,?)",
                ("flow", "flow", directory, "s", 1, "running", "n", "n"),
            )
            db.execute(
                "INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "flow",
                    "writer",
                    "w",
                    "p",
                    directory,
                    "default-tools",
                    0,
                    "[]",
                    "in_progress",
                    None,
                    "n",
                    "n",
                    1,
                    "clean",
                ),
            )
            db.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    "a",
                    "flow",
                    "writer",
                    directory,
                    "in_progress",
                    None,
                    "n",
                    None,
                    None,
                    None,
                ),
            )
            db.execute(
                "INSERT INTO task_declarations VALUES(?,?,?,?,?,?)",
                ("flow", "writer", "[]", "[]", '["allowed.py"]', ""),
            )
            db.execute(
                "INSERT INTO managed_worktrees VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "a",
                    "flow",
                    "writer",
                    directory,
                    directory,
                    "branch",
                    "base",
                    "owner",
                    "clean",
                    "pending",
                    "[]",
                    None,
                    None,
                ),
            )
            attempt = db.execute("SELECT * FROM attempts WHERE id='a'").fetchone()
            with patch.object(self.d, "git_value", side_effect=["other.py\n", ""]):
                self.assertFalse(self.d.audit_managed_worktree(db, "flow", attempt))
            self.assertEqual(
                "failed",
                db.execute(
                    "SELECT verification_state FROM managed_worktrees WHERE attempt_id='a'"
                ).fetchone()[0],
            )

    def test_audit_accepts_declared_uncommitted_and_untracked_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = self.d.db_connect(str(Path(directory) / "db.sqlite"))
            db.execute(
                "INSERT INTO workflows VALUES(?,?,?,?,?,?,?,?)",
                ("flow", "flow", directory, "s", 1, "running", "n", "n"),
            )
            db.execute(
                "INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "flow",
                    "writer",
                    "w",
                    "p",
                    directory,
                    "default-tools",
                    0,
                    "[]",
                    "in_progress",
                    None,
                    "n",
                    "n",
                    1,
                    "clean",
                ),
            )
            db.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    "a",
                    "flow",
                    "writer",
                    directory,
                    "in_progress",
                    None,
                    "n",
                    None,
                    None,
                    None,
                ),
            )
            db.execute(
                "INSERT INTO task_declarations VALUES(?,?,?,?,?,?)",
                ("flow", "writer", "[]", "[]", '["allowed.py", "new.py"]', ""),
            )
            db.execute(
                "INSERT INTO managed_worktrees VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "a",
                    "flow",
                    "writer",
                    directory,
                    directory,
                    "branch",
                    "base",
                    "owner",
                    "clean",
                    "pending",
                    "[]",
                    None,
                    None,
                ),
            )
            attempt = db.execute("SELECT * FROM attempts WHERE id='a'").fetchone()
            with patch.object(
                self.d, "git_value", side_effect=["allowed.py\n", "new.py\n"]
            ):
                self.assertTrue(self.d.audit_managed_worktree(db, "flow", attempt))
            state, changed = db.execute(
                "SELECT verification_state,changed_paths FROM managed_worktrees WHERE attempt_id='a'"
            ).fetchone()
            self.assertEqual("verified", state)
            self.assertEqual(["allowed.py", "new.py"], self.d.json.loads(changed))


if __name__ == "__main__":
    unittest.main()
