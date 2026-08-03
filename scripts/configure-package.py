#!/usr/bin/env python3
"""Restrict the pi-exts package to one extension, or enable all extensions."""

import argparse
import json
import re
from pathlib import Path

SETTINGS_PATH = Path.home() / ".pi" / "agent" / "settings.json"
VALID_EXTENSION_NAME = re.compile(r"[a-z0-9][a-z0-9-]*\Z")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("name", nargs="?")
    args = parser.parse_args()

    if args.name and not VALID_EXTENSION_NAME.fullmatch(args.name):
        parser.error(
            "extension names must contain only lowercase letters, digits, and hyphens"
        )

    try:
        settings = json.loads(SETTINGS_PATH.read_text())
    except (OSError, json.JSONDecodeError) as error:
        parser.error(f"cannot read {SETTINGS_PATH}: {error}")

    packages = settings.get("packages", [])
    packages = [
        package
        for package in packages
        if package != args.source
        and not (isinstance(package, dict) and package.get("source") == args.source)
    ]

    if args.name:
        packages.append(
            {
                "source": args.source,
                "extensions": [f"+extensions/rp152kpi:{args.name}/index.ts"],
                "skills": [],
                "prompts": [],
                "themes": [],
            }
        )
    else:
        packages.append(args.source)

    settings["packages"] = packages
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2) + "\n")


if __name__ == "__main__":
    main()
