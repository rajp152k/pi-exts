"""Deterministic SQLite/filesystem tests for the explicit campaign ledger."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).parents[1] / "scripts" / "task-dispatch.py"


def load() -> Any:
    spec = importlib.util.spec_from_file_location("campaign_ledger", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CampaignLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.d = load()

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger = self.d.campaign_connect(str(self.root / "ledger.sqlite"))

    def tearDown(self) -> None:
        self.ledger.close()
        self.tmp.cleanup()

    def plan(self) -> dict[str, Any]:
        return {
            "schemaVersion": 2,
            "id": "ledger-fixture",
            "approvals": {"default": "user", "delegations": []},
            "phases": [
                {
                    "id": "build",
                    "dependsOn": [],
                    "gates": [
                        {"id": "review", "decision": "advance"},
                        {"id": "integrate", "decision": "integrate"},
                    ],
                    "childSpecs": [],
                }
            ],
        }

    def test_append_only_create_gate_and_inspect(self) -> None:
        self.d.create_campaign(self.ledger, self.plan())
        self.d.record_campaign_gate(
            self.ledger,
            "ledger-fixture",
            "build",
            "review",
            "approved",
            "user",
            "ready",
        )
        view = self.d.inspect_campaign(self.ledger, "ledger-fixture")
        self.assertEqual(1, view["revision"])
        self.assertEqual("approved", view["gates"][0]["decision"])
        self.assertEqual(
            2, self.ledger.execute("SELECT count(*) FROM campaign_events").fetchone()[0]
        )

    def test_observation_fails_closed_on_revision_mismatch(self) -> None:
        child = self.root / "child.sqlite"
        db = sqlite3.connect(child)
        db.executescript(
            "CREATE TABLE workflow_current_revisions(workflow_id TEXT,revision INTEGER); CREATE TABLE workflow_revisions(workflow_id TEXT,revision INTEGER,content_hash TEXT);"
        )
        db.execute("INSERT INTO workflow_current_revisions VALUES('child',2)")
        db.execute("INSERT INTO workflow_revisions VALUES('child',2,?)", ("a" * 64,))
        db.commit()
        db.close()
        self.d.create_campaign(self.ledger, self.plan())
        observed = self.d.observe_campaign_child(
            self.ledger,
            "ledger-fixture",
            "build",
            "child",
            str(child),
            str(self.root / "artifacts"),
            1,
            "b" * 64,
            300,
        )
        self.assertFalse(observed["valid"])
        self.assertEqual("revision-mismatch", observed["status"])

    def test_integration_requires_observation_gate_approval_and_evidence(self) -> None:
        self.d.create_campaign(self.ledger, self.plan())
        proposal = self.d.propose_campaign_integration(
            self.ledger,
            "ledger-fixture",
            "build",
            "child",
            "writer",
            "a" * 40,
            "owner",
            "integrator",
        )
        self.d.approve_campaign_integration(self.ledger, proposal, "user")
        with self.assertRaises(SystemExit):
            self.d.record_campaign_integration(
                self.ledger, proposal, "b" * 40, [], "integrator", "user"
            )


if __name__ == "__main__":
    unittest.main()
