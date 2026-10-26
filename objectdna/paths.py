"""Find repository assets in editable/replay checkouts, bundled assets in wheels."""

from pathlib import Path


def asset_root():
    repository = Path(__file__).resolve().parents[1]
    # Source snapshots include the same training entry point for exact replay.
    if (repository / "scripts/train.py").is_file():
        return repository
    return Path(__file__).resolve().parent / "assets"
