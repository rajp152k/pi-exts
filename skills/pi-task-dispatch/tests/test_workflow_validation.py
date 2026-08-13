"""Acceptance tests for workflow-spec validation and ``workflow validate``.

The runtime contract under test is deliberately pure:

``validate_workflow_spec(spec)`` returns a JSON-serializable list of findings,
where every finding has at least ``code``, ``severity``, ``message``, and
``taskIds``.  An empty list means that the spec is valid.  The CLI emits the
same findings as JSON and exits 0 only when no error-severity finding exists.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).parents[1] / "scripts" / "task-dispatch.py"


def load_dispatcher() -> Any:
    spec = importlib.util.spec_from_file_location("task_dispatch", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WorkflowValidationTests(unittest.TestCase):
    """Validation rules that must run before workflow persistence or dispatch."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.dispatcher = load_dispatcher()

    def spec(self, *tasks: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": "validation-fixture",
            "cwd": str(Path.cwd()),
            "tmuxSession": "validation-session",
            "maxConcurrency": 2,
            "tasks": list(tasks),
        }

    @staticmethod
    def task(task_id: str, **changes: Any) -> dict[str, Any]:
        task = {
            "id": task_id,
            "objective": "Produce one bounded, reviewable result.",
            "deliverable": "A concise report.",
            "completionEvidence": "Run the stated check and include its result.",
            "handoff": "status; summary; files changed; tests; risks; next action",
            "access": "read-only",
            "state": "queued",
        }
        task.update(changes)
        return task

    def findings(self, spec: dict[str, Any]) -> list[dict[str, Any]]:
        findings = self.dispatcher.validate_workflow_spec(spec)
        self.assertIsInstance(findings, list)
        for finding in findings:
            self.assertIsInstance(finding, dict)
            self.assertTrue(
                {"code", "severity", "message", "taskIds"} <= finding.keys(),
                finding,
            )
        return findings

    def assert_codes(self, spec: dict[str, Any], *expected: str) -> None:
        codes = {finding["code"] for finding in self.findings(spec)}
        self.assertTrue(set(expected) <= codes, codes)

    def test_valid_minimal_graph_has_no_findings(self) -> None:
        self.assertEqual([], self.findings(self.spec(self.task("inspect"))))

    def test_duplicate_and_malformed_task_ids_are_reported(self) -> None:
        spec = self.spec(
            self.task("inspect"), self.task("inspect"), self.task("Bad_ID")
        )
        self.assert_codes(spec, "duplicate-task-id", "invalid-task-id")

    def test_missing_and_self_dependencies_are_reported(self) -> None:
        spec = self.spec(
            self.task("inspect", dependsOn=["absent"]),
            self.task("implement", dependsOn=["implement"]),
        )
        self.assert_codes(spec, "missing-dependency", "self-dependency")

    def test_cycles_and_graphs_without_roots_are_reported(self) -> None:
        spec = self.spec(
            self.task("first", dependsOn=["second"]),
            self.task("second", dependsOn=["first"]),
        )
        self.assert_codes(spec, "dependency-cycle", "no-root-task")

    def test_invalid_access_and_state_are_reported(self) -> None:
        spec = self.spec(self.task("inspect", access="admin", state="running-forever"))
        self.assert_codes(spec, "invalid-access", "invalid-state")

    def test_required_task_contract_is_enforced(self) -> None:
        incomplete = self.task("inspect")
        for field in ("objective", "deliverable", "completionEvidence", "handoff"):
            incomplete.pop(field)
        self.assert_codes(self.spec(incomplete), "missing-task-contract")

    def test_concurrently_eligible_writers_cannot_share_a_write_path(self) -> None:
        spec = self.spec(
            self.task(
                "writer-one",
                access="default-tools",
                resources=["worktree:writer-one"],
                writePaths=["src/shared.py"],
            ),
            self.task(
                "writer-two",
                access="default-tools",
                resources=["worktree:writer-two"],
                writePaths=["src/shared.py"],
            ),
        )
        self.assert_codes(spec, "write-path-conflict")

    def test_serial_writers_may_transfer_write_path_ownership(self) -> None:
        spec = self.spec(
            self.task(
                "writer-one",
                access="default-tools",
                resources=["worktree:writer-one"],
                writePaths=["src/shared.py"],
            ),
            self.task(
                "writer-two",
                access="default-tools",
                resources=["worktree:writer-two"],
                writePaths=["src/shared.py"],
                dependsOn=["writer-one"],
            ),
        )
        self.assertNotIn(
            "write-path-conflict", {finding["code"] for finding in self.findings(spec)}
        )

    def test_validate_cli_reports_machine_readable_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spec_path = Path(directory) / "workflow.json"
            spec_path.write_text(
                json.dumps(self.spec(self.task("inspect"))), encoding="utf-8"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "workflow",
                    "validate",
                    "--file",
                    str(spec_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"valid": True, "findings": []}, json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
