# Real scan demonstrations

Actual CPU reconstruction of two CC BY 4.0 Google Scanned Objects captures. Published processed meshes are sampled into 12,000 points. These are physical-capture derivatives, not raw depth frames.

| Object | Ranking | Model | Observed RMS mm | Sampled scan/CAD Chamfer mm | Support | Hypothesis accepted |
|---|---|---|---:|---:|---:|---|
| cereal_box | geometric | block | 1.984 | 2.678 | 94.8% | True |
| cereal_box | learned | block | 1.984 | 2.678 | 94.8% | True |
| porcelain_tray | geometric | enclosure | 2.958 | 5.077 | 82.7% | False |
| porcelain_tray | learned | enclosure | 2.958 | 5.077 | 82.7% | False |

No ground-truth CAD or independently measured dimensions are available. Volume IoU and dimensional accuracy are unknown. The cereal result describes the outer envelope; it does not establish a solid interior, cardboard thickness, material, or function. The flared porcelain tray is outside the grammar and must be treated as a failure/stress example.

STEP, STL, editable CadQuery and complete evidence are saved in each case folder. Attribution and byte-level provenance are in [data/real](../../data/real/README.md).
