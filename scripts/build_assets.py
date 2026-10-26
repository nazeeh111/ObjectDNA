#!/usr/bin/env python3
"""Stage or verify the source-controlled resources distributed in portable wheels."""

from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("models", "data/real", "data/synthetic", "web/dist")


def sources():
    result = {}
    for folder in FOLDERS:
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and path.name != ".DS_Store":
                if path.is_symlink():
                    raise ValueError(f"Symlinks are not packaged: {path}")
                result[str(path.relative_to(ROOT))] = path
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        result[name] = ROOT / name
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "objectdna/assets")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if staged assets differ from current source; never modify files.",
    )
    args = parser.parse_args()
    inputs = sources()
    expected = {name: digest(path) for name, path in inputs.items()}
    if not (ROOT / "web/dist/index.html").is_file():
        parser.error("Build the workbench first: npm --prefix web run build")
    if args.check:
        manifest = args.out / "ASSET_MANIFEST.json"
        if not manifest.is_file():
            parser.error("No staged asset manifest. Stage assets into a fresh directory first.")
        recorded = json.loads(manifest.read_text())
        stale = sorted(
            name
            for name in set(expected) | set(recorded)
            if expected.get(name) != recorded.get(name)
            or not (args.out / name).is_file()
            or digest(args.out / name) != expected.get(name)
        )
        if stale:
            parser.error(
                "Staged assets are stale: "
                + ", ".join(stale)
                + ". Rebuild into a fresh --out directory and preserve the old stage before replacing it."
            )
        print(f"Verified {len(expected)} staged assets against current source.")
        return
    if args.out.exists():
        parser.error(
            "Output exists. Choose a fresh --out directory; preserve an existing valid stage before replacing it."
        )
    args.out.mkdir(parents=True)
    for name, path in inputs.items():
        target = args.out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    (args.out / "ASSET_MANIFEST.json").write_text(json.dumps(expected, indent=2) + "\n")
    print(f"Staged {len(expected)} assets in {args.out}")


if __name__ == "__main__":
    main()
