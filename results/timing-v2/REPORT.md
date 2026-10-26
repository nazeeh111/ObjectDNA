# Locked v2 timing repeat

48 paired synthetic scans × 3 repeats, balanced randomized method/object order, warmup excluded. One BLAS/OpenMP thread requested. Source unchanged during run: True.

| Mode | Mean of per-case medians (s) | Median of per-case medians (s) |
|---|---:|---:|
| Dense geometric | 0.1771 | 0.1742 |
| Learned compact + geometry | 0.1054 | 0.1042 |

Ratio of mean case medians: **1.68×**, exploratory paired bootstrap 95% interval [1.60, 1.76]. Median per-case speedup: 1.67×. Compact-minus-dense mean paired difference: -0.0717s, interval [-0.0805, -0.0634].

- Timing-only repeat of fixed modes on already evaluated scans; no tuning, retraining or quality selection.
- Observed runtime is production reconstruction wall time, excluding cold imports, CAD validation/export and benchmark-only ground-truth metrics.
- One BLAS/OpenMP thread requested; method order and object order randomized on every repeat.
- Run after heavyweight owned test/render tasks finished; unrelated system load remains uncontrolled.
- Exploratory paired bootstrap over 48 synthetic objects is not a universal speed guarantee.
