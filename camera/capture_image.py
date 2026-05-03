#!/usr/bin/env python3
"""
Capture a single snapshot from a V4L2 camera device using v4l2py.
Requires: pip install v4l2py numpy opencv-python
"""

import os
import sys
import time
import cv2
import numpy as np
from linuxpy.video.device import Device
import v4l2
import find_craters

def show_image(title, img, max_size=1000):
	if(max(img.shape[0], img.shape[1]) > max_size):
		print(img.shape)
		scale_factor = max_size / max(img.shape[0], img.shape[1])
		img = cv2.resize(img, (int(img.shape[1] * scale_factor), int(img.shape[0] * scale_factor)))

	cv2.imshow(title, img)

def load_calibration(file_path):
	"""
	Load camera calibration parameters from a .npz file.
	The file should contain 'mtx' and 'dist'.
	"""
	if not os.path.exists(file_path):
		print(f"Calibration file '{file_path}' not found.")
		sys.exit(1)

	try:
		data = np.load(file_path)
		camera_matrix = data['mtx']
		dist_coeffs = data['dist']
	except KeyError:
		print("Calibration file missing required keys: 'mtx', 'dist'.")
		sys.exit(1)

	return camera_matrix, dist_coeffs

def variance_of_laplacian(image):
	"""
	Compute the Laplacian of the image and return the variance.
	Higher variance means sharper image.
	"""
	return cv2.Laplacian(image, cv2.CV_64F).var()

def is_image_blurry(image, threshold=100.0):
	"""
	Detect if an image is blurry.
	:param image_path: Path to the image file.
	:param threshold: Variance threshold below which the image is considered blurry.
	:return: (is_blurry: bool, variance: float)
	"""
	# Convert to grayscale
	gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

	# Compute variance of Laplacian
	fm = variance_of_laplacian(gray)

	return (fm < threshold, fm)

def _resize_to_max_long_edge(img, max_long: int):
	h, w = img.shape[:2]
	m = max(h, w)
	if m <= max_long:
		return img
	s = max_long / m
	nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
	return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)

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

def process_frame(frame, output_file=None, camera_matrix=None, dist_coeffs=None):
	# Convert MJPEG bytes to an OpenCV image
	np_arr = np.frombuffer(frame.data, np.uint8)
	img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

	if img is None:
		raise ValueError("Failed to decode image from camera.")

	if camera_matrix is not None and dist_coeffs is not None:
		print(repr(img.shape))
		h, w = img.shape[:2]
		new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
			camera_matrix, dist_coeffs, (w, h), 1, (w, h)
		)

		# Undistort the frame
		undistorted_frame = cv2.undistort(img, camera_matrix, dist_coeffs, None, new_camera_matrix)

		# Optional: crop the image to the valid ROI
		x, y, w, h = roi
		img = undistorted_frame[y:y+h, x:x+w]

	blurry, variance = is_image_blurry(img, 10)

	if blurry:
		print(f"Image is blurry (variance: {variance}).")

		if output_file is not None:
			cv2.imwrite(f"{output_file}_blurry.jpg", img)
		return None

	# Save snapshot
	if output_file is not None:
		cv2.imwrite(f"{output_file}.jpg", img)

	return img

def capture_snapshot(cam, output_file=None, camera_matrix=None, dist_coeffs=None):
	# output_file doesn't contain extension
	frame = next(iter(cam))
	return process_frame(frame, output_file, camera_matrix, dist_coeffs)

if __name__ == "__main__":
	camera_matrix, dist_coeffs = load_calibration("calibration_data.npz")

	while True:
		print("Waiting for first pass trigger...")
		while not os.path.exists("/tmp/first_pass_lock"):
			time.sleep(1)

		dev_path = sys.argv[1] if len(sys.argv) > 1 else "0"
		out_file = sys.argv[2] if len(sys.argv) > 2 else "snapshot.jpg"
		# Once we have a trigger for the first pass, we can start capture capturing snapshots
		counter: int = 0
		os.chdir(os.path.dirname(os.path.abspath(__file__)))

		if not os.path.exists("map"):
			os.makedirs("map")

		frames = []
		# Open the V4L2 device
		with Device.from_id(int(dev_path)) as cam:
			print("First pass in progress... waiting for lock to be removed.")
			# Set desired format (width, height, pixel format)
			cam.set_format(width=1920, height=1080, buffer_type=v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE)

			frames = []
			while os.path.exists("/tmp/first_pass_lock"):
				frame = next(iter(cam))
				frames.append(frame)

			print("Total frames captured during first pass: ", len(frames))
			for frame in frames:
				out_file = f"map/snapshot_{counter:05d}"
				frame = process_frame(frame, out_file, camera_matrix, dist_coeffs)
				if frame is not None:
					frames.append(frame)
				counter += 1

		# Done capturing snapshots for the first pass
		print("First pass complete. No longer capturing snapshots.")

		# Stitch the captured snapshots into a mosaic (optional, can be done offline)
		status, pano = stitch_bgr_frames(frames, max_long_edge=1080)

		if status == cv2.Stitcher_OK:
			cv2.imwrite("map/runway.jpg", pano)

		circles = find_craters.find_craters("map/runway.jpg")
