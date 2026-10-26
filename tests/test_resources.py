from pathlib import Path
import json, hashlib
import pytest


def test_staged_package_assets_are_hash_verified_when_present():
    root = Path(__file__).resolve().parents[1] / "objectdna/assets"
    if not root.exists():
        pytest.skip("Run scripts/build_assets.py for a portable wheel stage.")
    manifest = json.loads((root / "ASSET_MANIFEST.json").read_text())
    for name, sha in manifest.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == sha
    assert (root / "models/ranker.json").exists()
    assert (root / "models/proposal.json").exists()
    assert (root / "web/dist/index.html").exists()
    assert (root / "data/real/provenance.json").exists()
