"""Reports the lines changed under the foundation (backend/platform/, web/src/platform/) against main.

App PRs must change nothing here, or explain each change in a `platform:` commit. CI runs this on every PR
and prints the result; it never fails the build on its own, the reviewer decides.

Usage: python scripts/foundation_diff.py [--base origin/main] [--fail-on-change]
"""

from __future__ import annotations

import argparse
import subprocess
import sys

FOUNDATION_PATHS = ("backend/platform/", "web/src/platform/")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout


def resolve_base(candidates: list[str]) -> str:
    for ref in candidates:
        if (
            subprocess.run(
                ["git", "rev-parse", "--verify", "-q", ref], capture_output=True
            ).returncode
            == 0
        ):
            return ref
    sys.exit(f"none of the base refs exist: {candidates}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--base", default=None, help="base ref (default: origin/main, then main)"
    )
    parser.add_argument(
        "--fail-on-change",
        action="store_true",
        help="exit 1 when foundation lines changed",
    )
    args = parser.parse_args()

    base = args.base or resolve_base(["origin/main", "main"])
    merge_base = git("merge-base", base, "HEAD").strip()
    numstat = git("diff", "--numstat", merge_base, "HEAD", "--", *FOUNDATION_PATHS)

    added = removed = 0
    rows: list[tuple[str, str, str]] = []
    for line in numstat.splitlines():
        a, r, path = line.split("\t", 2)
        rows.append((a, r, path))
        added += int(a) if a.isdigit() else 0
        removed += int(r) if r.isdigit() else 0

    print(f"Foundation diff against {base} ({merge_base[:10]}):")
    if not rows:
        print("  0 lines changed under backend/platform/ and web/src/platform/")
        return 0
    for a, r, path in rows:
        print(f"  +{a:>5} -{r:>5}  {path}")
    print(f"  total: +{added} -{removed} across {len(rows)} file(s)")

    platform_commits = git(
        "log", "--format=%h %s", f"{merge_base}..HEAD", "--", *FOUNDATION_PATHS
    ).splitlines()
    print("Commits touching the foundation:")
    for commit in platform_commits or ["  (none)"]:
        marker = (
            ""
            if commit.split(" ", 1)[-1].startswith("platform:")
            or commit.startswith("  (")
            else "  <- not titled 'platform:'"
        )
        print(f"  {commit}{marker}")

    if args.fail_on_change:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
