"""The publish job's release-tag check (docs/milestone-4/PLAN.md, step 8, "Tags and GitHub releases").

Before the job logs in to the registry, the tag must be a release tag, ``vX.Y.Z`` or ``vX.Y.Z-rc.N``, and its
version must equal the CLI's ``CLI_VERSION`` (in Python's version format: ``X.Y.Z`` or ``X.Y.ZrcN``) and the Helm
chart's ``appVersion`` (``X.Y.Z`` or ``X.Y.Z-rc.N``). Milestone tags (``milestone-N``) and anything else are refused.

    python3 scripts/check_release_tag.py "$GITHUB_REF_NAME"
"""

from __future__ import annotations

from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_MAIN = REPO_ROOT / "packages/hetren_cli/main.py"
CHART = REPO_ROOT / "deploy/helm/hetren/Chart.yaml"
RELEASE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?$")


def expected_versions(tag: str) -> tuple[str, str] | None:
    """(the chart's appVersion, the CLI's version) a release tag requires; None if it is not a release tag."""
    match = RELEASE_TAG.match(tag)

    if not match:
        return None

    major, minor, patch, rc = match.groups()
    base = f"{major}.{minor}.{patch}"
    return (f"{base}-rc.{rc}", f"{base}rc{rc}") if rc is not None else (base, base)


def cli_version(text: str | None = None) -> str | None:
    text = CLI_MAIN.read_text(encoding="utf-8") if text is None else text
    match = re.search(r'^CLI_VERSION = "([^"]+)"$', text, re.MULTILINE)
    return match.group(1) if match else None


def chart_app_version(text: str | None = None) -> str | None:
    text = CHART.read_text(encoding="utf-8") if text is None else text
    match = re.search(r'^appVersion:\s*"?([^"\s]+)"?\s*$', text, re.MULTILINE)
    return match.group(1) if match else None


def problems(tag: str, cli: str | None, app: str | None) -> list[str]:
    expected = expected_versions(tag)

    if expected is None:
        return [f"{tag!r} is not a release tag (vX.Y.Z or vX.Y.Z-rc.N); nothing is published"]

    want_app, want_cli = expected
    found = []

    if cli != want_cli:
        found.append(f"CLI_VERSION is {cli!r}; tag {tag} needs {want_cli!r} (packages/hetren_cli/main.py)")

    if app != want_app:
        found.append(f"the chart's appVersion is {app!r}; tag {tag} needs {want_app!r} (deploy/helm/hetren/Chart.yaml)")

    return found


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv

    if len(args) != 1:
        print("usage: check_release_tag.py <tag>", file=sys.stderr)
        return 2

    found = problems(args[0], cli_version(), chart_app_version())

    for problem in found:
        print(f"FAIL  {problem}")

    if found:
        return 1

    print(f"ok    {args[0]}: CLI_VERSION {cli_version()}, chart appVersion {chart_app_version()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
