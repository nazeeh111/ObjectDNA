"""ObjectDNA CLI. Runs locally; no account or billed API required."""

import argparse
import json
from pathlib import Path
from . import __version__


def main():
    parser = argparse.ArgumentParser(
        prog="objectdna",
        description="Fit a bounded construction hypothesis to prealigned scan geometry, then inspect and edit actual CAD.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(
            [
                "First run: objectdna serve, then choose the labeled synthetic bracket.",
                "Save project retains normalized points and edit history; evidence-summary JSON is not reopenable.",
                "Canonical axes: X width, Y depth, Z height. Metric CAD export requires supplied scale.",
                "No physical reconstruction accuracy or manufacturing fitness is established.",
            ]
        ),
    )
    parser.add_argument("--version", action="version", version=f"ObjectDNA {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Start local 3D workbench")
    serve.add_argument("--port", type=int, default=8768)
    fit = sub.add_parser("fit", help="Reconstruct data-only point cloud or mesh")
    fit.add_argument("input", type=Path)
    fit.add_argument(
        "--out",
        type=Path,
        required=True,
        help="New output directory for evidence and, with metric scale, CAD artifacts",
    )
    fit.add_argument(
        "--units",
        choices=["mm", "m", "unknown"],
        default="unknown",
        help="Input coordinate units; unknown stays relative and blocks metric CAD export",
    )
    fit.add_argument(
        "--reference-extent-mm",
        type=float,
        help="Measured maximum bounding-box extent in mm; scale is supplied, never inferred",
    )
    fit.add_argument(
        "--align",
        action="store_true",
        help="Approximate PCA alignment may swap or flip axes; prealignment is preferred",
    )
    fit.add_argument("--ranking", choices=["learned", "geometric"], default="geometric")
    fit.add_argument("--no-refine", action="store_true")
    fit.add_argument("--candidate-mode", choices=["dense", "learned_compact"], default="dense")
    fit.add_argument(
        "--models",
        type=Path,
        help="Directory with proposal.json and optional ranker.json; defaults to bundled weights",
    )
    create = sub.add_parser(
        "project-create", help="Save a bounded project from a fit evidence record"
    )
    create.add_argument(
        "evidence", type=Path, help="Full evidence.json from a CLI fit, including source points"
    )
    create.add_argument("--out", type=Path, required=True)
    opened = sub.add_parser(
        "project-open", help="Validate/recompute a saved project and print evidence JSON"
    )
    opened.add_argument("project", type=Path)
    edited = sub.add_parser("project-edit", help="Apply a data-only spec and save a new project")
    edited.add_argument("project", type=Path)
    edited.add_argument("--spec", type=Path, required=True)
    edited.add_argument("--out", type=Path, required=True)
    exported = sub.add_parser("project-export", help="Recompute and export one CAD artifact")
    exported.add_argument("project", type=Path)
    exported.add_argument(
        "--format",
        choices=["step", "stl", "py", "json"],
        required=True,
        help="Individual artifact; JSON is evidence summary, not a reopenable project",
    )
    exported.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("objectdna.api:app", host="127.0.0.1", port=args.port)
    elif args.command.startswith("project-"):
        from .project import (
            decode_project,
            restore_project,
            encode_project,
            write_exclusive,
            MAX_PROJECT_BYTES,
            _unique_pairs,
        )
        from .cad import validate_spec, export_file
        import tempfile
        import os

        def read_bounded(path, limit):
            with path.open("rb") as stream:
                data = stream.read(limit + 1)
            if not data or len(data) > limit:
                raise ValueError("Input is empty or exceeds its size limit.")
            return data

        def parse_data(data):
            return json.loads(
                data.decode("utf-8"),
                object_pairs_hook=_unique_pairs,
                parse_constant=lambda _: (_ for _ in ()).throw(
                    ValueError("Nonfinite JSON is forbidden.")
                ),
            )

        try:
            if args.command == "project-create":
                source = parse_data(read_bounded(args.evidence, MAX_PROJECT_BYTES))
                result = restore_project(decode_project(encode_project(source)))
                write_exclusive(args.out, encode_project(result))
                print(json.dumps({"project": str(args.out), "units": result["units"]}))
            else:
                project = decode_project(read_bounded(args.project, MAX_PROJECT_BYTES))
                if args.command == "project-edit":
                    spec = validate_spec(parse_data(read_bounded(args.spec, 65536)))
                    if len(project["history"]) >= 128:
                        raise ValueError("Project edit history has reached its 128-entry limit.")
                    project["history"].append({"kind": "edited", "spec": spec})
                    import hashlib
                    from .project import _dump

                    project["project_sha256"] = hashlib.sha256(
                        _dump({k: v for k, v in project.items() if k != "project_sha256"})
                    ).hexdigest()
                result = restore_project(project)
                if args.command == "project-open":
                    print(
                        json.dumps(
                            {
                                "project_sha256": result["project_source_sha256"],
                                "units": result["units"],
                                "spec": result["spec"],
                                "metrics": result["metrics"],
                                "provenance": result["provenance"],
                                "history": result["project_history"],
                            },
                            allow_nan=False,
                        )
                    )
                elif args.command == "project-edit":
                    write_exclusive(args.out, encode_project(result))
                    print(
                        json.dumps(
                            {
                                "project": str(args.out),
                                "history_entries": len(result["project_history"]),
                            }
                        )
                    )
                else:
                    if result["units"] != "mm" and args.format != "json":
                        raise ValueError("Metric export requires calibrated units.")
                    if args.format == "json":
                        data = (
                            json.dumps(
                                {
                                    "units": result["units"],
                                    "spec": result["spec"],
                                    "metrics": result["metrics"],
                                    "provenance": result["provenance"],
                                },
                                allow_nan=False,
                            ).encode()
                            + b"\n"
                        )
                        write_exclusive(args.out, data)
                    else:
                        with tempfile.TemporaryDirectory(prefix="objectdna-project-") as directory:
                            artifact = Path(directory) / ("model." + args.format)
                            export_file(result["spec"], artifact, args.format)
                            write_exclusive(args.out, artifact.read_bytes())
                    print(json.dumps({"output": str(args.out), "format": args.format}))
        except (ValueError, TypeError, KeyError, OSError, OverflowError, RecursionError) as exc:
            parser.exit(2, f"objectdna: {exc}\n")
    else:
        if args.out.exists() or args.out.is_symlink():
            parser.error(
                "Output directory exists. Choose a new directory to preserve previous results."
            )
        from .io import read_points, MAX_BYTES
        from .inference import reconstruct
        from .cad import export_file, shape_stats

        try:
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
        except (ValueError, OSError) as exc:
            parser.exit(2, f"objectdna: {exc}\n")
        except KeyboardInterrupt:
            parser.exit(
                130,
                "objectdna: canceled. Inspect the output directory before retrying; choose a fresh destination.\n",
            )


if __name__ == "__main__":
    main()
