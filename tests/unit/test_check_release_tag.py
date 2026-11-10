"""The publish job's release-tag check: only vX.Y.Z and vX.Y.Z-rc.N, with matching CLI and chart versions."""

from __future__ import annotations

import re

import pytest

from scripts import check_release_tag as check


@pytest.mark.parametrize("tag, app, cli", [("v1.0.0", "1.0.0", "1.0.0"), ("v0.4.0-rc.1", "0.4.0-rc.1", "0.4.0rc1"),
                                           ("v10.20.30-rc.12", "10.20.30-rc.12", "10.20.30rc12")])
def test_release_tags_need_the_matching_versions(tag, app, cli):
    assert check.expected_versions(tag) == (app, cli)
    assert check.problems(tag, cli, app) == []


@pytest.mark.parametrize("tag", ["milestone-4", "v0.4.0-milestone-4", "v0.3.0-milestone-3", "v1.0", "v1.0.0-beta.1",
                                 "v1.0.0-rc1", "1.0.0", "v1.0.0 ", "v01.0.0x", "refs/tags/v1.0.0"])
def test_anything_else_is_refused(tag):
    assert check.expected_versions(tag) is None
    assert check.problems(tag, "1.0.0", "1.0.0")[0].endswith("nothing is published")


def test_a_version_mismatch_names_the_file_to_bump():
    found = check.problems("v0.4.0-rc.1", "0.4.0.dev0", "0.4.0-rc.1")
    assert found == ["CLI_VERSION is '0.4.0.dev0'; tag v0.4.0-rc.1 needs '0.4.0rc1' (packages/hetren_cli/main.py)"]
    assert "appVersion" in check.problems("v1.0.0", "1.0.0", "0.4.0-rc.1")[0]


def test_the_versions_are_read_from_the_cli_and_the_chart():
    # The version bump for step 6b's release candidate (PLAN.md, step 8, "Tags and GitHub releases").
    assert check.cli_version() == "0.4.0rc1" and check.chart_app_version() == "0.4.0-rc.1"
    assert check.main(["v0.4.0-rc.1"]) == 0
    assert check.main(["v0.4.0-rc.2"]) == 1 and check.main(["v0.4.0"]) == 1


def test_the_workflow_filter_patterns_match_exactly_the_release_tags():
    # GitHub's filter syntax: '+' repeats the previous character class and '.' is literal.
    def matches(pattern: str, tag: str) -> bool:
        regex = "".join({"+": "+", ".": r"\."}.get(c, c) for c in pattern)
        return re.fullmatch(regex, tag) is not None

    patterns = ["v[0-9]+.[0-9]+.[0-9]+", "v[0-9]+.[0-9]+.[0-9]+-rc.[0-9]+"]
    for tag in ("v1.0.0", "v0.4.0-rc.1"):
        assert any(matches(p, tag) for p in patterns)
    for tag in ("milestone-4", "v0.4.0-milestone-4", "v1.0.0-beta.1"):
        assert not any(matches(p, tag) for p in patterns)
