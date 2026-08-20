#!/usr/bin/env python3
"""Validate the capability manifest against package/bundle metadata and its docs table."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "capabilities.json"
DOCS_PATH = ROOT / "docs" / "capabilities.md"
REQUIRED = {
    "id",
    "state",
    "maturity",
    "owner",
    "bundle",
    "resources",
    "prerequisites",
    "authority",
    "offlineValidation",
    "liveValidation",
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def package_resources(package: dict[str, Any]) -> set[str]:
    pi = package.get("pi", {})
    patterns = [*pi.get("extensions", []), *pi.get("skills", [])]
    return {
        path.relative_to(ROOT).as_posix()
        for pattern in patterns
        for path in ROOT.glob(pattern)
        if path.is_file()
    }


def render_table(manifest: dict[str, Any]) -> str:
    rows = [
        "# Capability truth table",
        "",
        "This generated table is checked by `just check`. `capabilities.json` is the capability metadata authority; `resources.json` remains authoritative for install bundles.",
        "",
        "| ID | State | Maturity | Owner | Bundle | Prerequisites | Offline validation | Live / opt-in validation |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for capability in manifest["capabilities"]:
        rows.append(
            "| {id} | {state} | {maturity} | {owner} | {bundle} | {prerequisites} | `{offlineValidation}` | `{liveValidation}` |".format(
                **{
                    **capability,
                    "prerequisites": "; ".join(capability["prerequisites"]),
                }
            )
        )
    rows.extend(
        [
            "",
            "State is the user-facing truth claim. Maturity describes support posture: `personal` is maintained for this collection, `supported-local` has a local compatibility commitment, and `experimental` may change without compatibility guarantees.",
            "",
        ]
    )
    return "\n".join(rows)


def validate(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schemaVersion") != 1:
        fail(errors, "schemaVersion must be 1")
    states = set(manifest.get("states", []))
    maturities = set(manifest.get("maturities", []))
    capabilities = manifest.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        return [*errors, "capabilities must be a non-empty list"]

    bundles = load_json(ROOT / "resources.json")
    package = load_json(ROOT / "package.json")
    seen_ids: set[str] = set()
    owned: dict[str, str] = {}
    aggregate: dict[str, set[str]] = {bundle: set() for bundle in bundles}
    for item in capabilities:
        if not isinstance(item, dict):
            fail(errors, "each capability must be an object")
            continue
        missing = REQUIRED - item.keys()
        if missing:
            fail(errors, f"{item.get('id', '<unknown>')}: missing {sorted(missing)}")
            continue
        capability_id = item["id"]
        if not isinstance(capability_id, str) or not capability_id:
            fail(errors, "capability id must be a non-empty string")
            continue
        if capability_id in seen_ids:
            fail(errors, f"duplicate capability id: {capability_id}")
        seen_ids.add(capability_id)
        if item["state"] not in states:
            fail(errors, f"{capability_id}: unknown state {item['state']!r}")
        if item["maturity"] not in maturities:
            fail(errors, f"{capability_id}: unknown maturity {item['maturity']!r}")
        bundle = item["bundle"]
        if bundle not in bundles:
            fail(errors, f"{capability_id}: unknown bundle {bundle!r}")
            continue
        if not isinstance(item["resources"], list) or not item["resources"]:
            fail(errors, f"{capability_id}: resources must be a non-empty list")
            continue
        for resource in item["resources"]:
            if not isinstance(resource, str) or not (ROOT / resource).is_file():
                fail(errors, f"{capability_id}: missing resource {resource!r}")
                continue
            if resource in owned:
                fail(errors, f"{resource}: owned by both {owned[resource]} and {capability_id}")
            owned[resource] = capability_id
            aggregate[bundle].add(resource)

    exposed = package_resources(package)
    if exposed != set(owned):
        fail(errors, f"package resources and capability ownership differ: exposed-only={sorted(exposed - set(owned))}; manifest-only={sorted(set(owned) - exposed)}")
    for bundle, config in bundles.items():
        declared = set(config.get("extensions", []) + config.get("skills", []))
        if aggregate[bundle] != declared:
            fail(errors, f"bundle {bundle}: manifest={sorted(aggregate[bundle])}; resources.json={sorted(declared)}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-docs", action="store_true")
    args = parser.parse_args()
    manifest = load_json(MANIFEST_PATH)
    errors = validate(manifest)
    if errors:
        print("capability check failed:", *[f"- {error}" for error in errors], sep="\n", file=sys.stderr)
        raise SystemExit(1)
    rendered = render_table(manifest)
    if args.write_docs:
        DOCS_PATH.write_text(rendered, encoding="utf-8")
    elif not DOCS_PATH.is_file() or DOCS_PATH.read_text(encoding="utf-8") != rendered:
        print("capability docs are stale; run python3 scripts/check-capabilities.py --write-docs", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
