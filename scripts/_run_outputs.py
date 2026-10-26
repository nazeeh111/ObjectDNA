"""Small CLI output helpers: new artifacts never replace prior research evidence."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path


def require_new_directory(path: Path, parser, example: str) -> Path:
    path = path.expanduser()
    if path.exists() or path.is_symlink():
        parser.error(
            f"Output {path} already exists and was preserved. Choose a fresh directory, for example: {example}"
        )
    return path


def create_output_directory(path: Path, parser, example: str) -> Path:
    require_new_directory(path, parser, example)
    try:
        path.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        parser.error(
            f"Cannot create output {path}: {exc}. Try a fresh writable directory: {example}"
        )
    return path


def require_new_files(paths, parser, example: str):
    paths = [Path(path).expanduser() for path in paths]
    normalized = [str(path.resolve()).casefold() for path in paths]
    if len(normalized) != len(set(normalized)):
        parser.error(
            f"The model path conflicts with a manifest or card name. Choose a distinct model filename: {example}"
        )
    for path in paths:
        if path.exists() or path.is_symlink():
            parser.error(
                f"Output {path} already exists and was preserved. The model, manifest and card stay together. Choose a fresh model destination, for example: {example}"
            )
        if path.parent.exists() and not path.parent.is_dir():
            parser.error(f"Output parent {path.parent} is not a directory. Try: {example}")
    return paths


def write_new_bundle(files: dict[Path, str], parser, example: str):
    """Create all bundle files exclusively; roll back only bytes this call created."""
    require_new_files(files, parser, example)
    created = []
    try:
        for path, content in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as target:
                created.append(path)
                target.write(content)
    except OSError as exc:
        for path in created:
            path.unlink()
        parser.error(
            f"Could not save the model bundle; prior files were preserved: {exc}. Try: {example}"
        )


def model_files(directory: Path | None, parser, root: Path) -> dict[str, Path]:
    """Resolve and verify both numeric models and their matching training manifests."""
    if directory is None:
        from objectdna.paths import asset_root

        directory = asset_root() / "models"
    directory = directory.expanduser().resolve()
    result = {"ranker": directory / "ranker.json", "proposal": directory / "proposal.json"}
    manifests = {"ranker": "training_manifest.json", "proposal": "proposal_manifest.json"}
    for kind, path in result.items():
        manifest_path = directory / manifests[kind]
        try:
            model = json.loads(path.read_text(encoding="utf-8"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            digest = hashlib.sha256(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if digest != model["training_manifest_sha256"]:
                raise ValueError(f"{kind} model and training manifest hashes differ")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            parser.error(
                f"Cannot use model bundle {directory}: {exc}. Use the bundled models, or train both models into one fresh directory and pass --models that-directory."
            )
    return result


def source_files(root: Path, relative_paths, models: dict[str, Path]):
    files = {name: root / name for name in relative_paths}
    files.update({f"models/{name}.json": path for name, path in models.items()})
    return files


def file_hashes(files: dict[str, Path]):
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}
