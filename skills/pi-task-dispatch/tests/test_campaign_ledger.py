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

    def test_scout_evidence_is_bound_to_implementation_child_and_required_at_start(
        self,
    ) -> None:
        plan = self.plan()
        plan["phases"] = [
            {
                "id": "scout",
                "dependsOn": [],
                "gates": [{"id": "scout-review", "decision": "advance"}],
                "childSpecs": [],
            },
            {
                "id": "implement",
                "dependsOn": ["scout"],
                "gates": [{"id": "implement-integrate", "decision": "integrate"}],
                "childSpecs": [],
            },
        ]
        self.d.create_campaign(self.ledger, plan)
        artifact_root = self.root / "scout-artifacts"
        artifact_root.mkdir()
        report = artifact_root / "report.md"
        report.write_text("observed interface: stable\n", encoding="utf-8")
        report_hash = self.d.hashlib.sha256(report.read_bytes()).hexdigest()
        scout_db = self.root / "scout.sqlite"
        scout = sqlite3.connect(scout_db)
        scout.executescript(
            "CREATE TABLE workflow_current_revisions(workflow_id TEXT,revision INTEGER); CREATE TABLE workflow_revisions(workflow_id TEXT,revision INTEGER,content_hash TEXT);"
        )
        scout.execute("INSERT INTO workflow_current_revisions VALUES('scout-child',1)")
        scout.execute(
            "INSERT INTO workflow_revisions VALUES('scout-child',1,?)", ("a" * 64,)
        )
        scout.commit()
        scout.close()
        self.d.observe_campaign_child(
            self.ledger,
            "ledger-fixture",
            "scout",
            "scout-child",
            str(scout_db),
            str(artifact_root),
            1,
            "a" * 64,
            300,
        )
        self.d.record_campaign_gate(
            self.ledger,
            "ledger-fixture",
            "scout",
            "scout-review",
            "approved",
            "user",
            "reviewed scout",
        )
        child_spec = {
            "id": "implement-child",
            "cwd": str(self.root),
            "tmuxSession": "test",
            "tasks": [
                {
                    "id": "implement",
                    "prompt": "use scoped evidence",
                    "access": "read-only",
                }
            ],
        }
        _, child_hash = self.d.canonical_spec(child_spec)
        context = self.d.prepare_campaign_child_context(
            self.ledger,
            "ledger-fixture",
            "implement",
            "implement-child",
            1,
            child_hash,
            [
                {
                    "phase": "scout",
                    "workflowId": "scout-child",
                    "reference": "report.md",
                    "sha256": report_hash,
                }
            ],
            "campaign:ledger-fixture/phase:implement",
            "implement-integrate",
        )
        self.assertEqual("scout-child", context["artifacts"][0]["workflowId"])
        child_db = self.d.db_connect(str(self.root / "implementation.sqlite"))
        self.d.create_workflow(child_db, child_spec, campaign_context=context)
        # The former gap: no campaign evidence was supplied when implementation began.
        self.d.tick(child_db, "implement-child", self.root / "runs")
        self.assertEqual(
            "blocked",
            child_db.execute(
                "SELECT state FROM workflows WHERE id='implement-child'"
            ).fetchone()[0],
        )
        self.assertEqual(
            0, child_db.execute("SELECT count(*) FROM attempts").fetchone()[0]
        )
        self.assertIsNotNone(
            self.d.validate_bound_campaign_context(child_db, "implement-child", context)
        )
        child_db.close()

    def test_bound_context_fails_closed_when_stale_or_child_revision_changes(
        self,
    ) -> None:
        spec = {
            "id": "bound-child",
            "cwd": str(self.root),
            "tmuxSession": "test",
            "tasks": [{"id": "work", "prompt": "work"}],
        }
        _, content_hash = self.d.canonical_spec(spec)

        def context(expires_at: str) -> dict[str, Any]:
            value: dict[str, Any] = {
                "schemaVersion": 1,
                "campaign": {
                    "id": "ledger-fixture",
                    "phase": "build",
                    "revision": 1,
                    "planHash": "a" * 64,
                },
                "child": {
                    "workflowId": "bound-child",
                    "workflowRevision": 1,
                    "workflowContentHash": content_hash,
                },
                "approvedGates": [],
                "artifacts": [],
                "delegationScope": "campaign:ledger-fixture",
                "integrationCheckpoint": "integrate",
                "expiresAt": expires_at,
            }
            value["contextHash"] = self.d.campaign_context_hash(value)
            return value

        stale_db = self.d.db_connect(str(self.root / "stale.sqlite"))
        stale = context("2000-01-01T00:00:00+00:00")
        self.d.create_workflow(stale_db, spec, campaign_context=stale)
        with self.assertRaises(self.d.AttemptContextError):
            self.d.validate_bound_campaign_context(stale_db, "bound-child", stale)
        stale_db.close()
        fresh_db = self.d.db_connect(str(self.root / "revision.sqlite"))
        fresh = context("2999-01-01T00:00:00+00:00")
        self.d.create_workflow(fresh_db, spec, campaign_context=fresh)
        changed = {**spec, "name": "revised"}
        self.d.persist_revision(
            fresh_db, "bound-child", changed, rationale="test revision"
        )
        with self.assertRaises(self.d.AttemptContextError):
            self.d.validate_bound_campaign_context(fresh_db, "bound-child", fresh)
        fresh_db.close()

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
