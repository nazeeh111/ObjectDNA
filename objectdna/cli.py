"""ObjectDNA CLI. Runs locally; no account or billed API required."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog="objectdna")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Start local 3D workbench")
    serve.add_argument("--port", type=int, default=8768)
    fit = sub.add_parser("fit", help="Reconstruct data-only point cloud or mesh")
    fit.add_argument("input", type=Path)
    fit.add_argument("--out", type=Path, required=True)
    fit.add_argument("--units", choices=["mm", "m", "unknown"], default="unknown")
    fit.add_argument("--reference-extent-mm", type=float)
    fit.add_argument(
        "--align", action="store_true", help="Approximate PCA alignment (prealignment preferred)"
    )
    fit.add_argument("--ranking", choices=["learned", "geometric"], default="geometric")
    fit.add_argument("--no-refine", action="store_true")
    fit.add_argument("--candidate-mode", choices=["dense", "learned_compact"], default="dense")
    fit.add_argument(
        "--models",
        type=Path,
        help="Directory with proposal.json and optional ranker.json; defaults to bundled weights",
    )
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("objectdna.api:app", host="127.0.0.1", port=args.port)
    else:
        if args.out.exists():
            parser.error(
                "Output directory exists. Choose a new directory to preserve previous results."
            )
        from .io import read_points, MAX_BYTES
        from .inference import reconstruct
        from .cad import export_file, shape_stats

        with args.input.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        points = read_points(data, args.input.name)
        result = reconstruct(
            points,
            args.units,
            args.reference_extent_mm,
            args.ranking,
            not args.no_refine,
            args.align,
            candidate_mode=args.candidate_mode,
            ranker_path=args.models / "ranker.json" if args.models else None,
            proposal_path=args.models / "proposal.json" if args.models else None,
        )
        result["metrics"].update(shape_stats(result["spec"]))
        import hashlib

        result["provenance"].update(
            source_name=args.input.name,
            source_sha256=hashlib.sha256(data).hexdigest(),
            source_kind="user supplied, capture provenance unverified",
        )
        args.out.mkdir(parents=True)
        (args.out / "evidence.json").write_text(json.dumps(result, indent=2))
        if result["units"] == "mm":
            for ext in ("step", "stl", "py"):
                export_file(result["spec"], args.out / f"model.{ext}", ext)
        print(
            json.dumps(
                {
                    "family": result["spec"]["family"],
                    "metrics": result["metrics"],
                    "units": result["units"],
                    "output": str(args.out),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
