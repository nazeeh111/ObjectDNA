"""Local-only workbench API, bounded imports, data-only CAD edits, session isolation."""

from __future__ import annotations
import copy
from collections import OrderedDict
from pathlib import Path
import tempfile
import threading
import time
import uuid
import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field, ConfigDict
from .inference import reconstruct, ROOT
from .geometry import sdf, sample_surface
from .io import read_points, MAX_BYTES
from .samples import list_samples, get_sample

app = FastAPI(
    title="ObjectDNA", version="0.1.0", description="Local evidence-aware scan-to-CAD workbench"
)
STORE = OrderedDict()
LOCK = threading.Lock()
CAD_LOCK = threading.Lock()


class Reconstruction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sample_id: str | None = None
    points: list[list[float]] | None = Field(default=None, max_length=200000)
    units: str | None = None
    reference_extent_mm: float | None = None
    ranking: str = "geometric"
    refine: bool = True
    align: bool = False
    candidate_mode: str = "dense"


class Edit(BaseModel):
    id: str
    spec: dict


@app.middleware("http")
async def bounded_local_request(request: Request, call_next):
    # Prevent hostile websites from silently issuing writes to a loopback server.
    host = request.headers.get("host", "").split(":")[0]
    if host not in ("localhost", "127.0.0.1", "[", "testserver"):
        return __import__("fastapi").responses.JSONResponse(
            {"detail": "Loopback host required."}, status_code=403
        )
    origin = request.headers.get("origin")
    if origin and origin not in (
        str(request.base_url).rstrip("/"),
        "http://localhost:8768",
        "http://127.0.0.1:8768",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ):
        return __import__("fastapi").responses.JSONResponse(
            {"detail": "Cross-origin requests are disabled."}, status_code=403
        )
    if int(request.headers.get("content-length", "0")) > MAX_BYTES + 1024 * 1024:
        return __import__("fastapi").responses.JSONResponse(
            {"detail": "Request exceeds 25 MiB import limit."}, status_code=413
        )
    return await call_next(request)


def add_cad(result):
    from .cad import mesh_data, shape_stats

    with CAD_LOCK:
        result["mesh"] = mesh_data(result["spec"])
        result["metrics"].update(shape_stats(result["spec"]))
    return result


def save(result):
    result["id"] = uuid.uuid4().hex
    with LOCK:
        STORE[result["id"]] = copy.deepcopy(result)
        while len(STORE) > 24:
            STORE.popitem(last=False)
    return result


def lookup(id):
    with LOCK:
        if id not in STORE:
            raise HTTPException(404, "Session expired or unknown. Reconstruct the source again.")
        return copy.deepcopy(STORE[id])


@app.get("/api/health")
def health():
    from .inference import load_ranker

    return {
        "status": "ok",
        "version": "0.1.0",
        "ranker_available": load_ranker() is not None,
        "cad_backend": "CadQuery/OpenCascade",
        "photo_reconstruction": "optional external VGGT adapter; not a validated bundled model",
        "part_level_modeling": False,
    }


@app.get("/api/samples")
def samples():
    return {"samples": list_samples()}


@app.post("/api/reconstruct")
def run(body: Reconstruction):
    try:
        if (body.sample_id is None) == (body.points is None):
            raise ValueError("Choose exactly one sample or point array.")
        points = get_sample(body.sample_id) if body.sample_id else body.points
        # Bundled fixtures have known mm units. Raw arrays do not establish
        # absolute scale unless the caller declares units or a reference.
        units = body.units if body.units is not None else ("mm" if body.sample_id else "unknown")
        result = reconstruct(
            points,
            units,
            body.reference_extent_mm,
            body.ranking,
            body.refine,
            body.align,
            candidate_mode=body.candidate_mode,
        )
        result["provenance"].update(
            source_kind=(
                "synthetic"
                if body.sample_id not in ("cereal_box", "porcelain_tray")
                else "physical scan (processed mesh)"
            )
            if body.sample_id
            else "user supplied",
            source_name=body.sample_id or "Point array",
        )
        if body.sample_id in ("cereal_box", "porcelain_tray"):
            import json

            result["provenance"]["dataset"] = json.loads(
                (ROOT / "data/real/provenance.json").read_text()
            )[body.sample_id]
            result["warnings"].append(
                "This is a processed physical surface scan. Absolute dimensional accuracy has no independent caliper ground truth. A block models the outer envelope; shell, contents and mechanical function remain unknown."
            )
        return save(add_cad(result))
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/import")
def import_scan(
    file: UploadFile = File(...),
    units: str = Form("unknown"),
    reference_extent_mm: str = Form(""),
    align: bool = Form(False),
    ranking: str = Form("geometric"),
    refine: bool = Form(True),
    candidate_mode: str = Form("dense"),
):
    try:
        data = file.file.read(MAX_BYTES + 1)
        points = read_points(data, file.filename or "")
        result = reconstruct(
            points,
            units,
            float(reference_extent_mm) if reference_extent_mm.strip() else None,
            ranking=ranking,
            refine=refine,
            align=align,
            candidate_mode=candidate_mode,
        )
        import hashlib

        result["provenance"].update(
            source_kind="imported; capture provenance unverified",
            source_name=Path(file.filename or "Scan").name,
            source_sha256=hashlib.sha256(data).hexdigest(),
        )
        return save(add_cad(result))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/edit")
def edit(body: Edit):
    from .cad import validate_spec

    result = lookup(body.id)
    try:
        spec = validate_spec(body.spec)
        result["spec"] = spec
        cloud = np.array(result["source_points"])
        obs = np.abs(sdf(cloud, spec))
        diag = np.linalg.norm([spec["parameters"][k] for k in ("width", "depth", "height")])
        from scipy.spatial import cKDTree

        rev = cKDTree(cloud).query(sample_surface(spec, 5000, 77))[0]
        result["metrics"].update(
            observed_rmse_mm=float(np.sqrt(np.mean(obs**2))) if result["units"] == "mm" else None,
            chamfer_mm=float((obs.mean() + rev.mean()) / 2) if result["units"] == "mm" else None,
            observed_support=float(np.mean(obs < diag * 0.012)),
            surface_coverage=float(np.mean(rev < diag * 0.025)),
            accepted=False,
        )
        result["residuals"] = obs.tolist()
        result["provenance"]["edited"] = True
        result["uncertainty"] = [
            {
                "feature": "User edited dimensions",
                "status": "user specified",
                "detail": "Edited CAD dimensions are design intent, not newly observed measurements.",
            }
        ] + result["uncertainty"]
        result["warnings"].append(
            "Dimensions were edited. Inspect updated residuals against the original scan."
        )
        return save(add_cad(result))
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/export/{id}")
def export(id: str, format: str = "step"):
    from .cad import export_file

    result = lookup(id)
    if format not in ("step", "stl", "py", "json"):
        raise HTTPException(422, "Choose step, stl, py, or json.")
    if result["units"] != "mm" and format != "json":
        raise HTTPException(
            422, "Calibrate maximum extent in mm or declare known units before metric CAD export."
        )
    folder = tempfile.TemporaryDirectory(prefix="objectdna-export-")
    path = Path(folder.name) / f"objectdna.{format}"
    try:
        if format == "json":
            import json

            # Full evidence manifest, not only geometric parameters.
            path.write_text(
                json.dumps(
                    {
                        k: v
                        for k, v in result.items()
                        if k not in ("mesh", "source_points", "residuals")
                    },
                    indent=2,
                )
            )
        else:
            with CAD_LOCK:
                export_file(result["spec"], path, format)
        return FileResponse(path, filename=path.name, background=BackgroundTask(folder.cleanup))
    except Exception:
        folder.cleanup()
        raise


DIST = ROOT / "web/dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="workbench")
