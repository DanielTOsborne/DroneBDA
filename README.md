# NATSEC Hackathon:  Team _Crater Be Gone_
### Drone-based BDA for expeditionary JADR/RADR Operations  


<br></br>

## Repo layout

| Path | Purpose |
|------|---------|
| **`Output Reporting/`** | Reporting slice: BoM / DD2768-style outputs (`report.py`, `amr.py`, `amr_operator.txt`, blank DD2768 PDF). Generated Markdown and PDFs go to **`Output Reporting/Reports/`** (that folder is in git with **`.gitkeep` only**; report files are gitignored). |
| **`SensorCollection/`** | RP2350 (Arduino-style) firmware: bring-up and calibration sketches, a **VMA208** accelerometer library, and a combined sketch (**MPU6050** IMU + **Benewake TFmini** LiDAR) for payload sensor readout over serial. |
| **`StitchTesting/`** | OpenCV stitching experiments: small **`stitch.py`** API (SCANS mode) for integration; **`stitchTest.py`** for local batch testing (more options). |
| **`requirements.txt`** | Python dependencies (Python **3.11**). |

**Reference:** `ERDC-GSL SR-25-1.pdf` in the repo root is the product of the 2023 Joint Airfield Repair (JADR) Symposium, a training event and workshop hosted jointly by the US Army Corps of Engineers' _Engineer Research and Development Center_ (ERDC) and the 20th Engineer Brigade, XVIII Airborne Corps. It included attendees from over 20 organizations across the US Military and British Army. This document, alongside existing Airfield Damage Repair regulation, serves as the guiding framework for this project. 

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
