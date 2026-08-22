"""Deterministic read-only tests for the campaign status/watch overview."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).parents[1] / "scripts" / "task-dispatch.py"
HASH = "a" * 64
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def load() -> Any:
    spec = importlib.util.spec_from_file_location("campaign_overview", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CampaignOverviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.d = load()

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger = self.d.campaign_connect(str(self.root / "ledger.sqlite"))
        self.d.create_campaign(self.ledger, self.plan())

    def tearDown(self) -> None:
        self.ledger.close()
        self.tmp.cleanup()

    @staticmethod
    def plan() -> dict[str, Any]:
        return {
            "schemaVersion": 2,
            "id": "overview-fixture",
            "approvals": {"default": "user", "delegations": []},
            "phases": [
                {
                    "id": "build",
                    "dependsOn": [],
                    "gates": [{"id": "review", "decision": "advance"}],
                    "childSpecs": [],
                }
            ],
        }

    def child_database(self, state: str = "running") -> Path:
        path = self.root / "child.sqlite"
        child = sqlite3.connect(path)
        child.executescript(
            "CREATE TABLE workflow_current_revisions(workflow_id TEXT, revision INTEGER);"
            "CREATE TABLE workflow_revisions(workflow_id TEXT, revision INTEGER, content_hash TEXT);"
            "CREATE TABLE workflows(id TEXT, state TEXT);"
        )
        child.execute("INSERT INTO workflow_current_revisions VALUES('child', 1)")
        child.execute("INSERT INTO workflow_revisions VALUES('child', 1, ?)", (HASH,))
        child.execute("INSERT INTO workflows VALUES('child', ?)", (state,))
        child.commit()
        child.close()
        return path

    def authority(self, path: Path, *, observed_at: str, status: str = "fresh") -> None:
        self.ledger.execute(
            "INSERT INTO child_authorities("
            "campaign_id,revision,phase_id,workflow_id,database_path,artifact_root,"
            "expected_revision,expected_hash,observed_revision,observed_hash,status,observed_at,max_age_seconds"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "overview-fixture",
                1,
                "build",
                "child",
                str(path),
                str(self.root / "artifacts"),
                1,
                HASH,
                1,
                HASH,
                status,
                observed_at,
                300,
            ),
        )
        self.ledger.commit()

    def test_overview_reads_matching_authority_without_writing_ledger(self) -> None:
        child = self.child_database()
        self.authority(child, observed_at="2026-01-01T00:00:00+00:00")
        before = self.ledger.total_changes
        overview = self.d.campaign_overview(
            self.ledger, "overview-fixture", reference_time=NOW
        )
        self.assertEqual(before, self.ledger.total_changes)
        self.assertTrue(overview["displayOnly"])
        self.assertFalse(overview["blocked"])
        phase = overview["phases"][0]
        self.assertEqual("build", phase["desiredPhase"])
        self.assertEqual("authority-observed", phase["observedPhase"])
        authority = phase["children"][0]
        self.assertEqual("fresh", authority["status"])
        self.assertEqual("running", authority["observed"]["workflowState"])
        self.assertIn("workflow watch child --no-drive", authority["links"]["board"])
        self.assertEqual(str(self.root / "artifacts"), authority["links"]["artifacts"])
        readonly = self.d.campaign_readonly_connect(str(self.root / "ledger.sqlite"))
        try:
            with self.assertRaises(sqlite3.OperationalError):
                readonly.execute("INSERT INTO campaigns VALUES('forbidden', 'never')")
        finally:
            readonly.close()

    def test_stale_missing_and_mismatched_authorities_are_labeled_blockers(
        self,
    ) -> None:
        child = self.child_database()
        self.authority(child, observed_at="2025-12-31T23:54:59+00:00")
        stale = self.d.campaign_overview(
            self.ledger, "overview-fixture", reference_time=NOW
        )
        self.assertTrue(stale["blocked"])
        self.assertEqual("stale", stale["phases"][0]["children"][0]["status"])
        self.assertIn("blocked", stale["nextAction"].lower())

        self.ledger.execute("DELETE FROM child_authorities")
        missing = self.d.campaign_overview(
            self.ledger, "overview-fixture", reference_time=NOW
        )
        self.assertEqual(
            [{"phase": "build", "kind": "missing-authority"}],
            missing["authorityBlockers"],
        )

        self.authority(child, observed_at="2026-01-01T00:00:00+00:00")
        child = sqlite3.connect(child)
        child.execute("UPDATE workflow_revisions SET content_hash=?", ("b" * 64,))
        child.commit()
        child.close()
        mismatched = self.d.campaign_overview(
            self.ledger, "overview-fixture", reference_time=NOW
        )
        self.assertEqual(
            "revision-mismatch", mismatched["phases"][0]["children"][0]["status"]
        )


if __name__ == "__main__":
    unittest.main()
