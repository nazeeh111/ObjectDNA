import io
import numpy as np
import pytest
from objectdna.geometry import normalize_points, simulate_scan, validate_points, volume_iou, sdf
from objectdna.samples import SPECS
from objectdna.inference import reconstruct, detect_holes
from objectdna.io import read_points


@pytest.mark.parametrize("sample", list(SPECS))
def test_recovers_supported_family_and_geometry(sample):
    gt = SPECS[sample]
    points = simulate_scan(gt, 812, n=1800, noise=0.0007, outliers=0.005)
    r = reconstruct(points, ranking="geometric")
    assert r["spec"]["family"] == gt["family"]
    assert volume_iou(r["spec"], gt) > 0.88
    assert r["metrics"]["observed_support"] > 0.95
    assert any(x["status"] == "unknown" for x in r["uncertainty"])


def test_unknown_scale_stays_explicit():
    r = reconstruct(
        simulate_scan(SPECS["bracket"], 23, n=500), units="unknown", ranking="geometric"
    )
    assert r["units"] == "relative"
    assert r["metrics"]["observed_rmse_mm"] is None
    assert not r["provenance"]["transform"]["calibrated"]
    a, _, p = normalize_points(
        simulate_scan(SPECS["bracket"], 23, n=500), units="unknown", reference_extent_mm=80
    )
    assert p["calibrated"]
    assert np.max(np.ptp(a, axis=0)) == pytest.approx(80, rel=0.04)


@pytest.mark.parametrize(
    "pts", [np.zeros((100, 3)), np.zeros((4, 3)), [[float("nan"), 0, 0]] * 100]
)
def test_bad_points(pts):
    with pytest.raises(ValueError):
        validate_points(pts)


def test_pickle_rejected_and_xyz_round_trip():
    cloud = simulate_scan(SPECS["enclosure"], 44, n=100)
    text = "\n".join(" ".join(str(v) for v in p) for p in cloud)
    np.testing.assert_allclose(read_points(text.encode(), "part.xyz"), cloud)
    f = io.BytesIO()
    np.save(f, np.array([{"malicious": "not evaluated"}], dtype=object))
    with pytest.raises(ValueError):
        read_points(f.getvalue(), "bad.npy")


def test_sphere_is_flagged_as_unsupported():
    rng = np.random.default_rng(4)
    pts = rng.normal(size=(1600, 3))
    pts = pts / np.linalg.norm(pts, axis=1)[:, None] * 30
    r = reconstruct(pts, ranking="geometric")
    assert not r["metrics"]["accepted"]


def test_huge_npy_header_rejected_before_allocation():
    stream = io.BytesIO()
    np.lib.format.write_array_header_1_0(
        stream, {"descr": "<f8", "fortran_order": False, "shape": (10**12, 3)}
    )
    with pytest.raises(ValueError, match="before allocation"):
        read_points(stream.getvalue(), "oversized.npy")


def test_npy_numeric_roundtrip_and_truncated_payload():
    cloud = simulate_scan(SPECS["bracket"], 41, n=100)
    f = io.BytesIO()
    np.save(f, cloud)
    np.testing.assert_allclose(read_points(f.getvalue(), "valid.npy"), cloud)
    with pytest.raises(ValueError, match="payload"):
        read_points(f.getvalue()[:-8], "truncated.npy")


@pytest.mark.parametrize(
    "data",
    [
        b"ply\nformat ascii 1.0\n",
        b"ply\nformat ascii 1.0\nelement vertex 80\nproperty nonsense x\nend_header\n",
    ],
)
def test_malformed_ply_is_a_validation_error(data):
    with pytest.raises(ValueError, match="Malformed"):
        read_points(data, "broken.ply")


def test_quantized_duplicate_cloud_retains_three_dimensional_evidence():
    corners = np.array([[x, y, z] for x in (0.0, 10.0) for y in (0.0, 10.0) for z in (0.0, 10.0)])
    cloud, dims, pose = normalize_points(np.repeat(corners, 10, axis=0))
    assert len(cloud) == 80
    np.testing.assert_allclose(dims, [10.0, 10.0, 10.0])
    assert np.isfinite(cloud).all() and pose["removed_points"] == 0


def test_denoising_without_enough_surface_evidence_is_a_validation_error():
    corners = np.array([[x, y, z] for x in (0.0, 10.0) for y in (0.0, 10.0) for z in (0.0, 10.0)])
    cloud = np.vstack([np.zeros((95, 3)), corners[1:6]])
    with pytest.raises(ValueError, match="degenerate"):
        normalize_points(cloud)


def test_pcd_vector_fields_do_not_shift_xyz_coordinates():
    rng = np.random.default_rng(188)
    points = rng.uniform(0, 20, (100, 3))
    features = rng.uniform(100, 200, (100, 3))
    payload = io.StringIO()
    np.savetxt(payload, np.column_stack([features, points]))
    header = "VERSION .7\nFIELDS histogram x y z\nSIZE 4 4 4 4\nTYPE F F F F\nCOUNT 3 1 1 1\nWIDTH 100\nHEIGHT 1\nPOINTS 100\nDATA ascii\n"
    np.testing.assert_allclose(
        read_points((header + payload.getvalue()).encode(), "part.pcd"), points
    )


@pytest.mark.parametrize("counts", ["2 1 1", "1 1", "0 1 1", "1000000000000 1 1"])
def test_pcd_rejects_ambiguous_or_invalid_coordinate_counts(counts):
    header = f"FIELDS x y z\nCOUNT {counts}\nDATA ascii\n"
    with pytest.raises(ValueError, match="COUNT|scalar"):
        read_points((header + "0 0 0\n" * 100).encode(), "bad.pcd")


def test_compact_learned_proposals_are_bounded_and_explicit():
    from objectdna.inference import candidates
    from objectdna.proposal import load_proposal

    if load_proposal() is None:
        pytest.skip("Train proposal first")
    cloud, dims, _ = normalize_points(simulate_scan(SPECS["enclosure"], 551, n=1000))
    dense = candidates(cloud, dims, use_learned_proposal=False)
    compact = candidates(cloud, dims, candidate_mode="learned_compact")
    assert len(compact) <= 8 and len(compact) < len(dense)
    assert {c["family"] for c in compact} == {"bracket", "block", "enclosure"}
    for c in compact:
        if c["family"] != "block":
            assert 0.02 * min(dims) <= c["parameters"]["thickness"] <= 0.4 * min(dims)


def test_compact_mode_does_not_silently_fall_back(monkeypatch):
    import objectdna.proposal as proposal
    from objectdna.inference import candidates

    monkeypatch.setattr(proposal, "load_proposal", lambda: None)
    cloud, dims, _ = normalize_points(simulate_scan(SPECS["bracket"], 11, n=300))
    with pytest.raises(ValueError, match="requires the trained"):
        candidates(cloud, dims, candidate_mode="learned_compact")
