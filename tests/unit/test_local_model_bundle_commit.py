"""Kaggle runs record the code's commit explicitly: from the bundle's
BUNDLE.json, else from git, else the runner stops."""

import json
import subprocess

from packages.support_evaluator.local_model_baseline import REPO_ROOT, bundle_commit


def test_the_bundle_file_wins(tmp_path):
    (tmp_path / "BUNDLE.json").write_text(json.dumps({"commit": "beb9b5e", "data": {}}))
    assert bundle_commit(tmp_path) == "beb9b5e"


def test_a_git_checkout_gives_its_head():
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    assert bundle_commit(REPO_ROOT) == head


def test_neither_gives_none(tmp_path):
    assert bundle_commit(tmp_path) is None
