"""Verify that a release tag and the integration manifest use the same SemVer."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MANIFEST = Path("custom_components/ford_connect/manifest.json")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def main() -> int:
    """Check the supplied vX.Y.Z tag against manifest.json."""
    if len(sys.argv) != 2:
        print("Usage: check_release_version.py vMAJOR.MINOR.PATCH", file=sys.stderr)
        return 2

    tag = sys.argv[1]
    if not tag.startswith("v") or not SEMVER.fullmatch(tag[1:]):
        print(
            f"Invalid release tag {tag!r}; expected vMAJOR.MINOR.PATCH",
            file=sys.stderr,
        )
        return 1

    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        print(f"Cannot read {MANIFEST}: {err}", file=sys.stderr)
        return 1

    version = manifest.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        print(
            f"Invalid manifest version {version!r}; expected MAJOR.MINOR.PATCH",
            file=sys.stderr,
        )
        return 1

    if tag[1:] != version:
        print(
            f"Version mismatch: tag {tag} does not match manifest version {version}",
            file=sys.stderr,
        )
        return 1

    print(f"Release tag {tag} matches manifest version {version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
