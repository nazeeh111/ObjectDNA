"""Bounded data-only import. No uploaded program, pickled array or URL is executed."""

from io import BytesIO, StringIO
from pathlib import Path
import numpy as np
from .geometry import validate_points

MAX_BYTES = 25 * 1024 * 1024


def read_points(data: bytes, filename: str):
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Import a nonempty file smaller than 25 MiB.")
    suffix = Path(filename).suffix.lower()
    if suffix == ".npy":
        stream = BytesIO(data)
        version = np.lib.format.read_magic(stream)
        if version == (1, 0):
            shape, fortran, dtype = np.lib.format.read_array_header_1_0(
                stream, max_header_size=4096
            )
        elif version == (2, 0):
            shape, fortran, dtype = np.lib.format.read_array_header_2_0(
                stream, max_header_size=4096
            )
        else:
            raise ValueError("Use NPY format version 1 or 2 with a real numeric XYZ array.")
        if len(shape) != 2 or shape[1] != 3 or not 80 <= shape[0] <= 200000:
            raise ValueError("NPY must declare 80–200,000 XYZ points, before allocation.")
        if dtype.kind not in "fiu" or dtype.itemsize > 8 or dtype.hasobject:
            raise ValueError(
                "NPY must contain real numeric coordinates with at most 8 bytes per value."
            )
        offset = stream.tell()
        count = shape[0] * shape[1]
        if len(data) - offset != count * dtype.itemsize:
            raise ValueError("NPY payload does not match the declared array size.")
        arr = np.frombuffer(data, dtype=dtype, count=count, offset=offset).reshape(
            shape, order="F" if fortran else "C"
        )
    elif suffix in (".xyz", ".txt", ".csv", ".pts"):
        text = data.decode("utf-8-sig")
        lines = text.splitlines()
        if suffix == ".pts" and lines and len(lines[0].split()) == 1:
            text = "\n".join(lines[1:])
        arr = np.loadtxt(
            StringIO(text), delimiter="," if suffix == ".csv" else None, usecols=(0, 1, 2)
        )
    elif suffix == ".pcd":
        text = data.decode("utf-8")
        lines = text.splitlines()
        idx = next((i for i, l in enumerate(lines) if l.upper().startswith("DATA ")), None)
        if idx is None or lines[idx].strip().lower() != "data ascii":
            raise ValueError(
                "PCD import currently supports DATA ascii; convert binary PCD to PLY first."
            )
        fields = next((l.split()[1:] for l in lines[:idx] if l.upper().startswith("FIELDS ")), [])
        if not all(k in fields for k in ("x", "y", "z")):
            raise ValueError("PCD needs x y z fields.")
        if len(fields) != len(set(fields)):
            raise ValueError("PCD field names must be unique.")
        counts = next(
            (
                [int(v) for v in l.split()[1:]]
                for l in lines[:idx]
                if l.upper().startswith("COUNT ")
            ),
            [1] * len(fields),
        )
        if len(counts) != len(fields) or any(n < 1 for n in counts) or sum(counts) > 4096:
            raise ValueError(
                "PCD COUNT must provide a positive count for each field, with at most 4096 values per point."
            )
        if any(counts[fields.index(k)] != 1 for k in ("x", "y", "z")):
            raise ValueError("PCD x y z fields must each contain one scalar coordinate.")
        # Vector properties occupy multiple numeric columns, even though they
        # have only one name in FIELDS (for example a 33-value descriptor).
        offsets = np.cumsum([0] + counts[:-1]).tolist()
        arr = np.loadtxt(
            StringIO("\n".join(lines[idx + 1 :])),
            usecols=tuple(offsets[fields.index(k)] for k in ("x", "y", "z")),
        )
    elif suffix in (".ply", ".stl", ".obj"):
        import trimesh

        try:
            obj = trimesh.load(
                BytesIO(data), file_type=suffix[1:], process=False, skip_materials=True
            )
        except (ValueError, TypeError, IndexError, KeyError, OverflowError, EOFError) as exc:
            raise ValueError(
                "Malformed mesh or point-cloud file. Check the header and numeric payload."
            ) from exc
        if isinstance(obj, trimesh.Scene):
            if len(obj.geometry) != 1:
                raise ValueError(
                    "Import a single isolated object; assemblies are not yet supported."
                )
            obj = next(iter(obj.geometry.values()))
        if not hasattr(obj, "vertices"):
            raise ValueError("No vertices found in the file.")
        if len(obj.vertices) > 2000000:
            raise ValueError("Mesh is too large; decimate to fewer than 2 million vertices.")
        if hasattr(obj, "faces") and len(obj.faces):
            if len(obj.faces) > 2000000:
                raise ValueError("Mesh is too large; decimate first.")
            arr = trimesh.sample.sample_surface(obj, 6000, seed=0)[0]
        else:
            arr = np.asarray(obj.vertices)
    else:
        raise ValueError(
            "Supported files: XYZ, CSV, PTS, ASCII PCD, PLY, STL, OBJ and numeric NPY."
        )
    return validate_points(arr)
