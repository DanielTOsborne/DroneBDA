"""
Minimal OpenCV Stitcher smoke test: load sequential JPGs, stitch, save pano.

There is no "direction of travel" input to Stitcher: it aligns frames from
feature matches + estimated transforms. Portrait vs landscape does not confuse
it by itself. For phone-pointed-down walking (mostly translation over a floor),
Stitcher_SCANS often behaves better than the default PANORAMA (rotation-heavy).

If the mosaic looks scrambled, verify filenames sort in true capture order; if
your walk was opposite that order, set REVERSE_CAPTURE_ORDER = True.

Incremental mode (INCREMENTAL_STITCH=True) merges one frame at a time into a
growing master, similar to a running sum. That matches a drone that wants a
mosaic during flight and can drop each source frame after a successful merge.
Caveats: OpenCV still runs matching on the whole master each step, so later
steps can get slower as the canvas grows; error drift can differ from one-shot
batch stitch. The master image itself grows in memory — you save retaining N
full frames, not necessarily total RAM. Pairwise stitch([master, new]) often
fails once master is already a blended mosaic (Stitcher_ERR_NEED_MORE_IMGS is
common); batch sees all raw overlaps at once. Use FALLBACK_TO_BATCH_ON_INCREMENTAL_FAIL
or keep batch on the drone / ground station. Other latency ideas: stitch every
K frames in a short sliding window, stream frames to a laptop, or estimate
homographies only between consecutive raw frames and accumulate on a canvas.

Hierarchical / "2048" pairing (merge 1+2 and 3+4, then merge those two mosaics):
first-level pairs are raw+raw and can work, but the next level merges two
already-blended images — the same weakness as incremental master+raw. So a
merge tree does not fix Stitcher's composite problem; it adds complexity for
little gain unless you redesign around transforms on a canvas (not nested
Stitcher calls on mosaics).

Image size: Stitcher does not require all inputs to have the same width/height.
A growing output canvas and slight skew vs the phone frame are normal; that is
not what breaks pairwise composite stitching.

Performance (speed): dominant levers are fewer pixels (lower MAX_LONG_EDGE),
fewer frames (FRAME_STRIDE > 1 for a coarse map), and SCANS mode for nadir.
OpenCV's seam stage requires 3-channel images; true 1-channel inputs fail.
USE_LUMINANCE_ONLY converts BGR to gray then GRAY2BGR so stitching stays 3-channel
but uses luminance only (closer to your crater detector's grayscale path and
sometimes a bit steadier on low-texture pavement). Re-test quality if you enable it.
On Linux/Jetson, try re-enabling OpenCL (remove setUseOpenCL(False)) if stable.
"""
from pathlib import Path

import cv2

# Avoid OpenCL path on some Windows/GPU setups (CL_OUT_OF_RESOURCES during stitch).
cv2.ocl.setUseOpenCL(False)

HERE = Path(__file__).resolve().parent
OUT_NAME = "stitch_pano.jpg"
# Cap longest edge before stitch (largest speed lever; try 720 for coarse-only mosaics).
MAX_LONG_EDGE = 1080

# Use every Nth frame (1 = all). N>1 speeds stitching when overlap is very high.
FRAME_STRIDE = 1

# BGR -> gray -> GRAY2BGR (Stitcher requires 3 channels; plain grayscale Mat will crash).
USE_LUMINANCE_ONLY = False

# If overlap direction seems inverted vs how files sort, flip the sequence.
REVERSE_CAPTURE_ORDER = False

# True: merge frame-by-frame into a master (drone-style). False: one batch stitch.
INCREMENTAL_STITCH = False

# Pairwise stitch(master, new) often fails once the master is already a blend; OpenCV
# expects fresh views. If incremental fails, optionally run one batch stitch on all frames.
FALLBACK_TO_BATCH_ON_INCREMENTAL_FAIL = True

# cv2.Stitcher_SCANS: planar / scan-like motion (good first try for nadir walking).
# cv2.Stitcher_PANORAMA: rotating-camera panoramas (OpenCV default).
STITCH_MODE = (
    cv2.Stitcher_SCANS if hasattr(cv2, "Stitcher_SCANS") else getattr(cv2, "Stitcher_PANORAMA", 0)
)


def resize_to_max_long_edge(img, max_long: int):
    h, w = img.shape[:2]
    long = max(h, w)
    if long <= max_long:
        return img
    scale = max_long / long
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def preprocess_for_stitch(img):
    """Resize, optional luminance-only 3-channel (Stitcher seam finder requires 3 ch)."""
    out = resize_to_max_long_edge(img, MAX_LONG_EDGE)
    if USE_LUMINANCE_ONLY and len(out.shape) == 3 and out.shape[2] == 3:
        g = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        out = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
    return out


def list_jpg_paths(folder: Path) -> list[Path]:
    skip = {OUT_NAME.casefold()}
    return sorted(
        (
            p
            for p in {q.resolve(): q for q in folder.glob("*.jpg")}.values()
            if p.name.casefold() not in skip
        ),
        key=lambda p: p.name.lower(),
    )


def load_images_from_paths(paths: list[Path]) -> list:
    images = []
    for p in paths:
        im = cv2.imread(str(p))
        if im is None:
            raise SystemExit(f"Could not read: {p}")
        images.append(im)
    return images


def dummy_release_frame(path: Path, index: int, total: int) -> None:
    """Drone hook: free source buffer / delete file after merge. No-op for local testing."""
    print(f"  [dummy] release frame after merge: {path.name} ({index + 1}/{total})")


def make_stitcher(mode):
    if hasattr(cv2, "Stitcher"):
        return cv2.Stitcher.create(mode)
    # OpenCV 3.x: no mode selector in createStitcher; uses panorama-style path.
    return cv2.createStitcher(False)


def stitch_mode_label():
    scans = getattr(cv2, "Stitcher_SCANS", None)
    pano = getattr(cv2, "Stitcher_PANORAMA", 0)
    if scans is not None and STITCH_MODE == scans:
        return "SCANS"
    if STITCH_MODE == pano:
        return "PANORAMA"
    return f"mode_{STITCH_MODE}"


def prepare_paths(folder: Path) -> list[Path]:
    paths = list_jpg_paths(folder)
    if not paths:
        raise SystemExit(f"No .jpg images in {folder}")
    if REVERSE_CAPTURE_ORDER:
        paths.reverse()
        print("Reversed frame order (REVERSE_CAPTURE_ORDER=True)")
    if FRAME_STRIDE > 1:
        paths = paths[::FRAME_STRIDE]
        print(f"FRAME_STRIDE={FRAME_STRIDE}: using {len(paths)} frames after subsampling")
    return paths


def stitch_status_name(status: int) -> str:
    for name in (
        "Stitcher_OK",
        "Stitcher_ERR_NEED_MORE_IMGS",
        "Stitcher_ERR_HOMOGRAPHY_EST_FAIL",
        "Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL",
    ):
        if hasattr(cv2, name) and getattr(cv2, name) == status:
            return name
    return str(status)


def stitch_batch(stitcher, imgs: list):
    ok = getattr(cv2, "Stitcher_OK", 0)
    status, pano = stitcher.stitch(imgs)
    return pano, status, ok


def stitch_incremental(stitcher, paths: list[Path]):
    ok = getattr(cv2, "Stitcher_OK", 0)
    master = None
    n = len(paths)
    for i, p in enumerate(paths):
        im = cv2.imread(str(p))
        if im is None:
            raise SystemExit(f"Could not read: {p}")
        before = im.shape[:2]
        im = preprocess_for_stitch(im)
        after = im.shape[:2]
        if before != after:
            print(
                f"  frame {i + 1}: resize {before[1]}x{before[0]} -> {after[1]}x{after[0]} "
                f"(max long edge {MAX_LONG_EDGE})"
            )
        else:
            print(f"  frame {i + 1}: {after[1]}x{after[0]} (already <= {MAX_LONG_EDGE}px long edge)")

        if master is None:
            master = im
            print(f"  incremental: master = frame 1/{n} shape={master.shape}")
        else:
            status, master = stitcher.stitch([master, im])
            if status != ok:
                return None, status, i + 1
            print(f"  incremental: merged frame {i + 1}/{n} master shape={master.shape}")

        dummy_release_frame(p, i, n)

    return master, ok, n


def main():
    paths = prepare_paths(HERE)
    print(f"Found {len(paths)} images in {HERE}")
    print(
        f"Stitch mode: {stitch_mode_label()} ({STITCH_MODE}), incremental={INCREMENTAL_STITCH}, "
        f"luminance_only={USE_LUMINANCE_ONLY}, max_long_edge={MAX_LONG_EDGE}"
    )

    stitcher = make_stitcher(STITCH_MODE)
    ok = getattr(cv2, "Stitcher_OK", 0)

    if INCREMENTAL_STITCH:
        pano, status, detail = stitch_incremental(stitcher, paths)
        if status != ok:
            print(
                f"Incremental stitch failed at merge step {detail}: "
                f"{stitch_status_name(status)} ({status})"
            )
            if not FALLBACK_TO_BATCH_ON_INCREMENTAL_FAIL:
                return 1
            print("Falling back to batch stitch on all frames (see FALLBACK_TO_BATCH_ON_INCREMENTAL_FAIL).")
            imgs = load_images_from_paths(paths)
            for i, im in enumerate(imgs):
                before = im.shape[:2]
                imgs[i] = preprocess_for_stitch(im)
                after = imgs[i].shape[:2]
                if before != after:
                    print(
                        f"  {i + 1}: resize {before[1]}x{before[0]} -> {after[1]}x{after[0]} "
                        f"(max long edge {MAX_LONG_EDGE})"
                    )
                else:
                    print(f"  {i + 1}: {after[1]}x{after[0]} (already <= {MAX_LONG_EDGE}px long edge)")
            pano, status, _ = stitch_batch(stitcher, imgs)
            if status != ok:
                print(f"Batch stitch also failed: {stitch_status_name(status)} ({status})")
                return 1
    else:
        imgs = load_images_from_paths(paths)
        print(f"Loaded {len(imgs)} images (batch path)")
        for i, im in enumerate(imgs):
            before = im.shape[:2]
            imgs[i] = preprocess_for_stitch(im)
            after = imgs[i].shape[:2]
            if before != after:
                print(
                    f"  {i + 1}: resize {before[1]}x{before[0]} -> {after[1]}x{after[0]} "
                    f"(max long edge {MAX_LONG_EDGE})"
                )
            else:
                print(f"  {i + 1}: {after[1]}x{after[0]} (already <= {MAX_LONG_EDGE}px long edge)")
        pano, status, ok_ref = stitch_batch(stitcher, imgs)
        if status != ok_ref:
            print(f"Stitch failed, status={status} (expected {ok_ref} = OK)")
            return 1

    out_path = HERE / OUT_NAME
    cv2.imwrite(str(out_path), pano)
    print(f"Wrote {out_path} shape={pano.shape}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
