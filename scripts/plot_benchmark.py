#!/usr/bin/env python3
"""Make a static, shareable figure from retained benchmark measurements."""

from pathlib import Path
import argparse
import json
from _run_outputs import require_new_directory, create_output_directory


def plotting_libraries():
    import numpy as np
    import os
    import tempfile

    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "objectdna-mpl-cache"))
    import matplotlib

    matplotlib.use("Agg")
    # Use Matplotlib's bundled font bytes for a portable figure. On restricted macOS
    # hosts system_profiler may return no font inventory; no system-font access is needed.
    if __import__("sys").platform == "darwin":
        import re

        manager_source = (Path(matplotlib.__file__).parent / "font_manager.py").read_text()
        version = re.search(r"__version__ = ['\"]([^'\"]+)", manager_source).group(1)
        cache = Path(matplotlib.get_cachedir())
        cache.mkdir(parents=True, exist_ok=True)
        font_file = cache / f"fontlist-v{version}.json"
        if not font_file.exists():
            entries = []
            for filename, style, weight in [
                ("DejaVuSans.ttf", "normal", 400),
                ("DejaVuSans-Bold.ttf", "normal", 700),
                ("DejaVuSans-Oblique.ttf", "oblique", 400),
                ("DejaVuSans-BoldOblique.ttf", "oblique", 700),
            ]:
                entries.append(
                    {
                        "__class__": "FontEntry",
                        "fname": "fonts/ttf/" + filename,
                        "name": "DejaVu Sans",
                        "style": style,
                        "variant": "normal",
                        "weight": weight,
                        "stretch": "normal",
                        "size": "scalable",
                    }
                )
            font_file.write_text(
                json.dumps(
                    {
                        "__class__": "FontManager",
                        "_version": version,
                        "_FontManager__default_weight": "normal",
                        "default_size": None,
                        "defaultFamily": {"ttf": "DejaVu Sans", "afm": "Helvetica"},
                        "afmlist": [],
                        "ttflist": entries,
                    }
                )
            )
    import matplotlib.pyplot as plt

    return np, plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "results/synthetic-v1",
        help="Read-only benchmark input folder.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Fresh figure directory; defaults to runs/figures/{input-folder-name}.",
    )
    parser.add_argument(
        "--timing-results",
        type=Path,
        help="Optional matching timing folder with case_medians.json; defaults to timing-v2 beside the input.",
    )
    args = parser.parse_args()
    example = "python scripts/plot_benchmark.py --results runs/compact-test-v2 --out runs/figures/compact-v2-new"
    out = require_new_directory(
        args.out or Path(__file__).resolve().parents[1] / "runs/figures" / args.results.name,
        parser,
        example,
    )
    summary = json.loads((args.results / "summary.json").read_text())
    rows = json.loads((args.results / "cases.json").read_text())
    timing_path = (args.timing_results or args.results.parent / "timing-v2") / "case_medians.json"
    if args.timing_results is not None and not timing_path.is_file():
        parser.error(f"Timing measurements not found: {timing_path}")
    timing_medians = (
        json.loads(timing_path.read_text())
        if "compact_geometric" in summary["methods"] and timing_path.exists()
        else None
    )
    np, plt = plotting_libraries()
    create_output_directory(out, parser, example)
    methods = (
        ["dense_geometric", "compact_geometric"] if timing_medians else list(summary["methods"])
    )
    labels = {
        "bbox": "Bounding box",
        "geometric_refined": "Geometric + refine",
        "learned_no_proposal": "No learned proposal",
        "learned_unrefined": "No refinement",
        "learned_refined": "Learned ranker + refine",
        "dense_geometric": "Dense geometric search",
        "compact_geometric": "Learned compact + geometry",
        "compact_ranker": "Compact + learned ranker",
    }
    palette = {
        "bbox": "#b7c0c1",
        "geometric_refined": "#687b82",
        "learned_no_proposal": "#aaa28c",
        "learned_unrefined": "#558f8a",
        "learned_refined": "#e55c2f",
        "dense_geometric": "#687b82",
        "compact_geometric": "#e55c2f",
        "compact_ranker": "#558f8a",
    }
    colors = [palette[m] for m in methods]
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": "#243033",
            "text.color": "#243033",
            "axes.edgecolor": "#8d999c",
            "xtick.color": "#566266",
            "ytick.color": "#566266",
            "figure.facecolor": "#fbfaf6",
            "axes.facecolor": "#fbfaf6",
            "savefig.facecolor": "#fbfaf6",
        }
    )
    fig, axes = plt.subplots(
        1, 3, figsize=(13.2, 4.6), gridspec_kw={"width_ratios": [1.05, 1.05, 1.0]}
    )
    rng = np.random.default_rng(97)
    second = (
        ("runtime_seconds", "Inference time (s) ↓")
        if "compact_geometric" in methods
        else ("chamfer_mm", "Chamfer distance (mm) ↓")
    )
    for ax, metric, label in ((axes[0], "volumetric_iou", "Volumetric IoU ↑"), (axes[1], *second)):
        for i, method in enumerate(methods):
            vals = (
                np.array([r[method] for r in timing_medians])
                if metric == "runtime_seconds" and timing_medians
                else np.array(
                    [r[metric] for r in rows if r["method"] == method and "error" not in r]
                )
            )
            boots = np.mean(vals[rng.integers(0, len(vals), (3000, len(vals)))], axis=1)
            lo, hi = np.quantile(boots, [0.025, 0.975])
            mean = float(vals.mean())
            ax.barh(i, mean, color=colors[i], height=0.65)
            ax.errorbar(
                mean,
                i,
                xerr=[[max(0, mean - lo)], [max(0, hi - mean)]],
                fmt="none",
                ecolor="#243033",
                capsize=3,
                lw=1,
            )
            ax.text(
                max(mean, hi) + (0.012 if metric == "volumetric_iou" else 0.04),
                i,
                f"{mean:.3f}",
                va="center",
                fontsize=9,
            )
        ax.set_yticks(range(len(methods)), [labels[m] for m in methods] if ax == axes[0] else [])
        ax.invert_yaxis()
        ax.set_xlabel(label)
        ax.grid(axis="x", alpha=0.15)
        ax.set_axisbelow(True)
        ax.set_xlim(0, 1.1 if metric == "volumetric_iou" else None)
    baseline = "geometric_refined" if "geometric_refined" in methods else "dense_geometric"
    selected = "learned_refined" if "learned_refined" in methods else "compact_geometric"
    a = {r["seed"]: r for r in rows if r["method"] == baseline and "error" not in r}
    b = {r["seed"]: r for r in rows if r["method"] == selected and "error" not in r}
    for family, color in zip(("block", "bracket", "enclosure"), ("#687b82", "#e55c2f", "#558f8a")):
        ids = [i for i in a if i in b and a[i]["truth_family"] == family]
        axes[2].scatter(
            [a[i]["volumetric_iou"] for i in ids],
            [b[i]["volumetric_iou"] for i in ids],
            s=24,
            color=color,
            label=family,
            alpha=0.8,
            edgecolors="white",
            linewidths=0.4,
        )
    axes[2].plot([0, 1], [0, 1], color="#8d999c", linestyle="--", lw=1)
    axes[2].set(
        xlim=(0, 1.02), ylim=(0, 1.02), xlabel="Dense geometric IoU", ylabel="Learned pipeline IoU"
    )
    axes[2].legend(frameon=False, loc="lower right", fontsize=8)
    axes[2].grid(alpha=0.15)
    fig.suptitle(
        f"ObjectDNA · {summary['test_cases']} held-out synthetic objects",
        x=0.035,
        ha="left",
        fontsize=17,
        fontweight="bold",
    )
    runtime_caption = (
        " Runtime uses per-case medians of 3 locked repeats." if timing_medians else ""
    )
    fig.text(
        0.035,
        0.015,
        "Authored three-family grammar. Independent 7,000-point surfaces; 50,000-point Monte Carlo IoU. Bars: averages across cases with 95% bootstrap intervals.\nSynthetic acquisition only. Runtime excludes cold import and benchmark-only checks. No upstream neural baselines reproduced; no real-world superiority claim."
        + runtime_caption,
        fontsize=8,
        color="#566266",
    )
    fig.tight_layout(rect=(0, 0.11, 1, 0.91), w_pad=2.8)
    fig.savefig(out / "benchmark.png", dpi=180)
    fig.savefig(out / "benchmark.svg")
    plt.close(fig)
    print(out / "benchmark.png")


if __name__ == "__main__":
    main()
