# DroneBDA

Hackathon prototype: drone-enabled airfield damage assessment (planning-style outputs for a logistics demo).

## Repo layout

| Path | Purpose |
|------|---------|
| **`Output Reporting/`** | Reporting slice: BoM / DD2768-style outputs (`report.py`, `amr.py`, `amr_operator.txt`, blank DD2768 PDF). Generated Markdown and PDFs go to **`Output Reporting/Reports/`** (that folder is in git with **`.gitkeep` only**; report files are gitignored). |
| **`StitchTesting/`** | OpenCV stitching experiments: small **`stitch.py`** API (SCANS mode) for integration; **`stitchTest.py`** for local batch testing (more options). |
| **`requirements.txt`** | Python dependencies (Python **3.11**). |

## Commands

From the repo root (paths in quotes because of spaces in folder names):

```text
py -3.11 -m pip install -r requirements.txt
py -3.11 "Output Reporting/report.py"
```

Stitch smoke test (writes `StitchTesting/stitch_pano.jpg`):

```text
py -3.11 StitchTesting/stitchTest.py
```

Using the minimal stitch helper from code (run with `StitchTesting` on `PYTHONPATH`, or `cd` there):

```python
from stitch import stitch_bgr_frames
status, pano = stitch_bgr_frames(frames, max_long_edge=1080)  # pano is None if status != cv2.Stitcher_OK
```

## Optional local reference

Add **`ERDC-GSL SR-25-1.pdf`** at the repo root if you want ERDC BoM/repair wording on hand while coding; that filename is gitignored.
