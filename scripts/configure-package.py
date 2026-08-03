#!/usr/bin/env python3
"""Install a selected pi-exts resource bundle into Pi's user settings."""

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RESOURCES_PATH = REPO_ROOT / "resources.json"
SETTINGS_PATH = Path.home() / ".pi" / "agent" / "settings.json"
VALID_BUNDLE_NAME = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
RESOURCE_KINDS = ("extensions", "skills", "prompts", "themes")


def read_json(path: Path, description: str) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {description} at {path}: {error}") from error


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as temporary:
        json.dump(value, temporary, indent=2)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def resource_filters(bundle: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        kind: [f"+{resource}" for resource in bundle.get(kind, [])]
        for kind in RESOURCE_KINDS
    }


def local_extension_names(resources: dict[str, dict[str, list[str]]], bundle_name: str | None) -> set[str]:
    bundles = [resources[bundle_name]] if bundle_name else resources.values()
    names: set[str] = set()
    for bundle in bundles:
        for resource in bundle.get("extensions", []):
            path = Path(resource)
            if path.name == "index.ts" and path.parent.name.startswith("rp152kpi:"):
                names.add(path.parent.name)
    return names


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Pi package source, such as git:github.com/user/repo")
    parser.add_argument("bundle", nargs="?", help="Bundle name from resources.json")
    args = parser.parse_args()

    try:
        resources = read_json(RESOURCES_PATH, "resource manifest")
        settings = read_json(SETTINGS_PATH, "Pi settings")
    except ValueError as error:
        parser.error(str(error))

    if not isinstance(resources, dict) or not isinstance(settings, dict):
        parser.error("resource manifest and Pi settings must be JSON objects")

    if args.bundle:
        if not VALID_BUNDLE_NAME.fullmatch(args.bundle):
            parser.error("bundle names must contain only lowercase letters, digits, and hyphens")
        if args.bundle not in resources:
            parser.error(f"unknown bundle: {args.bundle}")
        bundle = resources[args.bundle]
        if not isinstance(bundle, dict):
            parser.error(f"invalid bundle: {args.bundle}")
    else:
        bundle = None

    packages = settings.get("packages", [])
    if not isinstance(packages, list):
        parser.error("Pi settings packages must be an array")
    packages = [
        package
        for package in packages
        if package != args.source
        and not (isinstance(package, dict) and package.get("source") == args.source)
    ]

    if bundle is None:
        packages.append(args.source)
    else:
        packages.append({"source": args.source, **resource_filters(bundle)})
    settings["packages"] = packages

    managed_names = local_extension_names(resources, args.bundle)
    extensions = settings.get("extensions", [])
    if not isinstance(extensions, list):
        parser.error("Pi settings extensions must be an array")
    remaining_extensions = [
        extension
        for extension in extensions
        if not (
            isinstance(extension, str)
            and Path(extension).name in managed_names
            and Path(extension).parent.name == "extensions"
        )
    ]
    if remaining_extensions:
        settings["extensions"] = remaining_extensions
    else:
        settings.pop("extensions", None)

    write_json_atomic(SETTINGS_PATH, settings)


if __name__ == "__main__":
    main()
