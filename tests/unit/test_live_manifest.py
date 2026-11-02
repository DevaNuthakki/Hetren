"""The committed live test manifest pins the live split for the protocol
freeze. The live data is gitignored, so the hash check runs only where it
exists (the operator's machine); the counts are always checked."""

import json
from pathlib import Path

import pytest

from packages.support_evaluator.live_episodes import live_manifest


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs" / "milestone-2" / "live-test-v1.manifest.json"
LIVE_DIR = ROOT / "artifacts" / "milestone-2" / "live-test-v1"


def test_manifest_counts_and_categories():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert manifest["runs"] == 300 == sum(manifest["composition"].values())
    assert manifest["categories"] == {"final_label_only": 17, "live_confirmed_target": 6, "proxy_matched": 277}
    assert manifest["model"] == "gpt-4.1-mini-2025-04-14"


@pytest.mark.skipif(not (LIVE_DIR / "hetren_visible_final.jsonl").exists(), reason="live data is gitignored")
def test_local_live_data_matches_the_committed_manifest():
    assert live_manifest(LIVE_DIR) == json.loads(MANIFEST.read_text(encoding="utf-8"))
