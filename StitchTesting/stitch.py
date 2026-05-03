"""
Minimal OpenCV panorama stitch (SCANS mode) for nadir / scan-like motion.

How to use
----------
    import cv2
    from pathlib import Path
    from stitch import stitch_bgr_frames

    paths = sorted(Path("photos").glob("*.jpg"))
    frames = [cv2.imread(str(p)) for p in paths if cv2.imread(str(p)) is not None]
    status, pano = stitch_bgr_frames(frames, max_long_edge=1080)
    # status == cv2.Stitcher_OK means success (same convention as cv2.Stitcher.stitch).
    if status == cv2.Stitcher_OK:
        cv2.imwrite("pano.jpg", pano)

Inputs
------
    frames: list of BGR images (uint8), e.g. from cv2.imread. Sizes may differ;
            they are optionally resized before stitching.

    max_long_edge: if not None, each frame is downscaled so max(height, width)
            is at most this value (faster, less RAM). Pass None to skip resize.

Outputs
-------
    Same as cv2.Stitcher.stitch: (status, pano) where pano is the BGR mosaic
    on success, or partial/empty on failure; compare status to cv2.Stitcher_OK.
"""
from __future__ import annotations

import cv2

# Windows + some drivers: OpenCL in OpenCV can error during stitch; safe default.
cv2.ocl.setUseOpenCL(False)


def _resize_to_max_long_edge(img, max_long: int):
    h, w = img.shape[:2]
    m = max(h, w)
    if m <= max_long:
        return img
    s = max_long / m
    nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
    return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)


"""  -------------------------------------  """
"""  vvv   THIS IS THE PART WE WANT    vvv  """
"""  -------------------------------------  """

def stitch_bgr_frames(frames, *, max_long_edge: int | None = 1080):
    """
    Stitch BGR frames using Stitcher in SCANS mode.

    Returns (status, pano) per OpenCV Stitcher.stitch().
    """
    if not frames:
        return getattr(cv2, "Stitcher_ERR_NEED_MORE_IMGS", 1), None

    processed = list(frames)
    if max_long_edge is not None:
        processed = [_resize_to_max_long_edge(im, max_long_edge) for im in processed]

    mode = cv2.Stitcher_SCANS if hasattr(cv2, "Stitcher_SCANS") else 1
    stitcher = cv2.Stitcher.create(mode)
    return stitcher.stitch(processed)

