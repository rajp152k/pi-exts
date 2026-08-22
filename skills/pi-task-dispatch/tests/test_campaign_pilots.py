"""Deterministic coverage for constrained campaign pilots."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).parents[1] / "scripts" / "task-dispatch.py"


def load() -> Any:
    spec = importlib.util.spec_from_file_location("campaign_pilots", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CampaignPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.d = load()

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = self.d.campaign_connect(str(Path(self.tmp.name) / "ledger.sqlite"))
        self.d.create_campaign(
            self.db,
            {
                "schemaVersion": 2,
                "id": "pilot",
                "approvals": {"default": "user", "delegations": []},
                "phases": [
                    {"id": "one", "dependsOn": [], "gates": [], "childSpecs": []}
                ],
            },
        )

    def tearDown(self) -> None:
        self.db.close()
        self.tmp.cleanup()

    def test_wisdom_retrieval_is_scoped_and_expiry_bound(self) -> None:
        record = {
            "id": "scroll-1",
            "kind": "scroll",
            "status": "reviewed",
            "scopeTags": ["python"],
            "provenance": "git:abc",
            "expiresAt": "2030-01-01T00:00:00Z",
            "owner": "maintainer",
            "reviewer": "reviewer",
        }
        self.d.record_wisdom(self.db, record)
        self.assertEqual(
            [record],
            self.d.retrieve_wisdom(self.db, ["python"], at="2029-01-01T00:00:00Z"),
        )
        self.assertEqual(
            [], self.d.retrieve_wisdom(self.db, ["other"], at="2029-01-01T00:00:00Z")
        )

    def test_attention_coalesces_and_can_resolve(self) -> None:
        event = {
            "kind": "blocked",
            "authority": "Git",
            "impact": "cannot integrate",
            "options": ["review"],
            "recommendation": "review",
            "confidence": "observed",
            "source": "git:abc",
        }
        first = self.d.record_attention(self.db, "pilot", event)
        self.assertTrue(first["created"])
        self.assertFalse(self.d.record_attention(self.db, "pilot", event)["created"])
        self.d.resolve_attention(self.db, "pilot", first["fingerprint"], "user")
        self.assertTrue(self.d.record_attention(self.db, "pilot", event)["created"])

    def test_route_requires_exact_provider_model_and_thinking(self) -> None:
        route = {"provider": "openai", "model": "gpt-x", "thinking": "high"}
        self.assertTrue(
            self.d.preflight_route(
                [{"provider": "openai", "model": "gpt-x", "thinking": ["high"]}], route
            )["valid"]
        )
        self.assertFalse(self.d.preflight_route([], route)["valid"])

    def test_consolidation_is_deterministic_authority_report(self) -> None:
        report = self.d.deterministic_consolidation(self.db, "pilot")
        self.assertEqual("recorded-not-inferred", report["outcome"])
        self.assertEqual(1, report["metrics"]["phases"])


if __name__ == "__main__":
    unittest.main()
