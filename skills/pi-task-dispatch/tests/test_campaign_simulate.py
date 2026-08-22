"""Deterministic acceptance tests for the pure ``campaign simulate`` command."""

from __future__ import annotations

import hashlib
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
    spec = importlib.util.spec_from_file_location("task_dispatch_campaign", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CampaignSimulateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dispatcher = load_dispatcher()

    @staticmethod
    def workflow(writer: bool = False) -> dict[str, Any]:
        task: dict[str, Any] = {
            "id": "inspect",
            "objective": "Inspect the bounded target.",
            "deliverable": "A reviewable result.",
            "completionEvidence": "Run the stated check.",
            "handoff": "status; tests; next action",
            "access": "read-only",
        }
        if writer:
            task.update(
                {
                    "id": "write-result",
                    "access": "default-tools",
                    "resources": ["worktree:writer"],
                    "writePaths": ["result.txt"],
                }
            )
        return {
            "id": "child",
            "cwd": ".",
            "tmuxSession": "unused",
            "maxConcurrency": 1,
            "tasks": [task],
        }

    def campaign(
        self,
        child: Path,
        digest: str,
        *,
        integrations: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "id": "fixture",
            "approvals": {"default": "user", "delegations": []},
            "phases": [
                {
                    "id": "prepare",
                    "dependsOn": [],
                    "gates": ["review"],
                    "childSpecs": [
                        {
                            "ref": child.name,
                            "sha256": digest,
                            "integrations": integrations or [],
                        }
                    ],
                }
            ],
        }

    @staticmethod
    def write_json(path: Path, value: Any) -> str:
        raw = json.dumps(value, indent=2).encode()
        path.write_bytes(raw)
        return hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()

    def test_canonical_projection_and_cli_output_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child = root / "child.json"
            digest = self.write_json(child, self.workflow())
            campaign = root / "campaign.json"
            self.write_json(campaign, self.campaign(child, digest))
            first = self.dispatcher.simulate_campaign(str(campaign))
            second = self.dispatcher.simulate_campaign(str(campaign))
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "campaign",
                    "simulate",
                    "--file",
                    str(campaign),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertTrue(first["valid"], first)
        self.assertEqual(first, second)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(first, json.loads(result.stdout))
        self.assertEqual(
            ["prepare"], [phase["id"] for phase in first["predictedPhases"]]
        )

    def test_invalid_graph_child_spec_and_duplicate_reference_are_reported(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child = root / "child.json"
            digest = self.write_json(child, self.workflow())
            campaign = self.campaign(child, "0" * 64)
            campaign["phases"].append(
                {
                    "id": "finish",
                    "dependsOn": ["prepare"],
                    "gates": ["review"],
                    "childSpecs": [
                        {"ref": child.name, "sha256": digest, "integrations": []}
                    ],
                }
            )
            campaign["phases"][0]["dependsOn"] = ["finish"]
            path = root / "campaign.json"
            self.write_json(path, campaign)
            codes = {
                item["code"]
                for item in self.dispatcher.simulate_campaign(str(path))["findings"]
            }
        self.assertTrue(
            {
                "phase-cycle",
                "unordered-phase-dependency",
                "child-spec-hash-mismatch",
                "duplicate-child-spec-reference",
            }
            <= codes,
            codes,
        )

    def test_missing_writer_integration_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child = root / "writer.json"
            digest = self.write_json(child, self.workflow(writer=True))
            path = root / "campaign.json"
            self.write_json(path, self.campaign(child, digest))
            codes = {
                item["code"]
                for item in self.dispatcher.simulate_campaign(str(path))["findings"]
            }
        self.assertIn("missing-writer-integration", codes)

    def test_simulation_creates_no_runtime_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child = root / "child.json"
            digest = self.write_json(child, self.workflow())
            campaign = root / "campaign.json"
            self.write_json(campaign, self.campaign(child, digest))
            before = sorted(
                path.relative_to(root).as_posix() for path in root.rglob("*")
            )
            projection = self.dispatcher.simulate_campaign(str(campaign))
            after = sorted(
                path.relative_to(root).as_posix() for path in root.rglob("*")
            )
        self.assertTrue(projection["valid"], projection)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
