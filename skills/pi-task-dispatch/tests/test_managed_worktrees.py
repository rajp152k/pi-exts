"""Managed-worktree MVP tests, including a real-Git audit regression."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
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

    @unittest.skipUnless(shutil.which("git"), "git is unavailable")
    def test_real_git_audit_persists_declared_and_undeclared_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()

            def git(*arguments: str) -> None:
                subprocess.run(
                    ["git", *arguments], cwd=source, check=True, capture_output=True
                )

            git("init", "-q")
            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "Managed Worktree Test")
            (source / "allowed.py").write_text("original\n")
            git("add", "allowed.py")
            git("commit", "-qm", "initial")

            db = self.d.db_connect(str(root / "db.sqlite"))
            workflow_id = self.d.create_workflow(
                db,
                {
                    "id": "flow",
                    "tmuxSession": "unused",
                    "tasks": [
                        {
                            "id": "writer",
                            "access": "default-tools",
                            "managedWorktrees": True,
                            "objective": "change declared files",
                            "deliverable": "a patch",
                            "completionEvidence": "audit passes",
                            "handoff": "return results",
                            "writePaths": ["allowed.py", "new.py"],
                        }
                    ],
                },
                cwd_override=str(source),
            )
            db.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    "attempt",
                    workflow_id,
                    "writer",
                    str(root),
                    "in_progress",
                    None,
                    "n",
                    None,
                    None,
                    None,
                ),
            )
            task = db.execute(
                "SELECT * FROM tasks WHERE workflow_id=? AND id=?",
                (workflow_id, "writer"),
            ).fetchone()
            attempt = db.execute("SELECT * FROM attempts WHERE id='attempt'").fetchone()
            worktree = self.d.create_managed_worktree(
                db, workflow_id, task, "attempt", root, True, "preserve"
            )

            (worktree / "allowed.py").write_text("modified\n")
            (worktree / "new.py").write_text("new\n")
            self.assertTrue(self.d.audit_managed_worktree(db, workflow_id, attempt))
            state, changed = db.execute(
                "SELECT verification_state,changed_paths FROM managed_worktrees WHERE attempt_id='attempt'"
            ).fetchone()
            self.assertEqual("verified", state)
            self.assertEqual(["allowed.py", "new.py"], self.d.json.loads(changed))

            (worktree / "undeclared.py").write_text("undeclared\n")
            self.assertFalse(self.d.audit_managed_worktree(db, workflow_id, attempt))
            state, changed = db.execute(
                "SELECT verification_state,changed_paths FROM managed_worktrees WHERE attempt_id='attempt'"
            ).fetchone()
            self.assertEqual("failed", state)
            self.assertEqual(
                ["allowed.py", "new.py", "undeclared.py"], self.d.json.loads(changed)
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
