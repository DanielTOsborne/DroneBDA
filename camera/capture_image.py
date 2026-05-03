#!/usr/bin/env python3
"""
Capture a single snapshot from a V4L2 camera device using v4l2py.
Requires: pip install v4l2py numpy opencv-python
"""

import os
import socket
import sys
import time
import cv2
import numpy as np
from linuxpy.video.device import Device
import v4l2
import find_craters
from skimage.metrics import structural_similarity as ssim

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from Server import system_state

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

def compute_and_save_homography(gray1, gray2, homography_file):
	# Detect ORB keypoints and descriptors
	orb = cv2.ORB_create(5000)
	kp1, des1 = orb.detectAndCompute(gray1, None)
	kp2, des2 = orb.detectAndCompute(gray2, None)

	if des1 is None or des2 is None:
		raise ValueError("Could not find enough features in one or both images.")

	# Match descriptors using brute-force matcher
	bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
	matches = bf.match(des1, des2)
	matches = sorted(matches, key=lambda x: x.distance)

	if len(matches) < 4:
		raise ValueError("Not enough matches to compute homography.")

	# Extract matched keypoints
	src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
	dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

	# Compute homography
	H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
	if H is None:
		raise ValueError("Homography computation failed.")
	
	return H
		
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

def compare_images(img1, img2):
	if img1.shape != img2.shape:
		img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))

	# Convert to grayscale for SSIM
	gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
	gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
	# Compute SSIM
	print(gray1.shape, gray2.shape)
	score, _ = ssim(gray1, gray2, full=True)
	similarity_percentage = score * 100

	return similarity_percentage

def process_frame(img, previous_img = None, output_file=None, camera_matrix=None, dist_coeffs=None):
	print(repr(img))

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

	# Compare with previous frame
	if previous_img is not None:
		similarity = compare_images(previous_img, img)
		print(f"Similarity with previous frame: {similarity:.2f}%")
		if similarity > 90.0:
			print("Image is too similar to the previous one, skipping.")
			cv2.imwrite(f"{output_file}_similar.jpg", img)
			return None

	# Save snapshot
	if output_file is not None:
		cv2.imwrite(f"{output_file}.jpg", img)

	return img

def capture_snapshot(cam, output_file=None, camera_matrix=None, dist_coeffs=None):
	# output_file doesn't contain extension
	frame = next(iter(cam))
	return process_frame(frame, output_file, camera_matrix, dist_coeffs)

def stitched_to_original(pt_stitched, H_inv):
	px = np.array([pt_stitched[0], pt_stitched[1], 1.0])
	mapped = H_inv @ px
	mapped /= mapped[2]  # normalize
	return mapped[0], mapped[1]

def transform_point(pt, H):
    """Transform a single (x, y) point using homography H."""
    px = np.array([pt[0], pt[1], 1.0])
    mapped = H @ px
    mapped /= mapped[2]  # normalize
    return int(round(mapped[0])), int(round(mapped[1]))

if __name__ == "__main__":
	test: bool = False
	if len(sys.argv) > 1 and sys.argv[1] == "--test":
		test = True

	camera_matrix, dist_coeffs = load_calibration("calibration_data.npz")
	while True:
		print("Waiting for first pass trigger...")
		while True:
			state = system_state.read_state()
			if state[0] == "cameraScan":
				print("First pass trigger detected!")
				break
			time.sleep(1)

		dev_path = sys.argv[1] if len(sys.argv) > 1 else "0"
		out_file = sys.argv[2] if len(sys.argv) > 2 else "snapshot.jpg"
		# Once we have a trigger for the first pass, we can start capture capturing snapshots
		counter: int = 0
		os.chdir(os.path.dirname(os.path.abspath(__file__)))

		if not os.path.exists("map"):
			os.makedirs("map")

		frames = []
		if not test:
			try:
				os.remove("map/snapshot*.jpg")
			except:
				pass

			# Open the V4L2 device
			with Device.from_id(int(dev_path)) as cam:
				print("First pass in progress... waiting for lock to be removed.")
				# Set desired format (width, height, pixel format)
				cam.set_format(width=1920, height=1080, buffer_type=v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE)

				frames = []
				prev_img = None
				countdown = 30
				while system_state.read_state()[0] == "cameraScan" and countdown > 0:
					countdown -= 1
					frame = next(iter(cam))
					# Convert MJPEG bytes to an OpenCV image
					frame = np.frombuffer(frame.data, np.uint8)
					img = cv2.imdecode(frame, cv2.IMREAD_COLOR)
					if img is None:
						raise ValueError("Failed to decode image from camera.")

					out_file = f"map/snapshot_{counter:05d}"
					processed_img = process_frame(img, prev_img, out_file, camera_matrix, dist_coeffs)
					if processed_img is not None:
						frames.append(processed_img)
						prev_img = processed_img
					counter += 1
		else:
			# For testing, process existing images in the "test_images" directory
			test_dir = "map"
			prev_img = None
			for filename in sorted(os.listdir(test_dir)):
				if filename.lower().endswith(".jpg"):
					if "blurry" in filename or "similar" in filename:
						continue  # Skip rejected images

					img_path = os.path.join(test_dir, filename)
					img = cv2.imread(img_path, cv2.IMREAD_COLOR)

					processed_img = process_frame(img, prev_img, camera_matrix, dist_coeffs)
					if processed_img is not None:
						frames.append(processed_img)
						prev_img = processed_img
					counter += 1

		print("Total frames captured during first pass: ", counter)

		# Done capturing snapshots for the first pass
		print("First pass complete. No longer capturing snapshots.")

		if counter > 0:
			# Stitch the captured snapshots into a mosaic (optional, can be done offline)
			status, pano = stitch_bgr_frames(frames, max_long_edge=1080)

			STITCHED_IMAGE_PATH = "map/runway.jpg"
			if status == cv2.Stitcher_OK:
				cv2.imwrite(STITCHED_IMAGE_PATH, pano)

			circles = find_craters.find_craters(STITCHED_IMAGE_PATH)

			if len(frames) > 0:
				H = compute_and_save_homography(frames[0], pano, "homography.npz")
				print("Homography matrix:\n", H)
				# H: homography from original -> stitched
				# H_inv: inverse homography
				H_inv = np.linalg.inv(H)

				# highlight relative points on image
				output = pano.copy()

				# Given the homography, we can map points from the stitched image back to the original camera frame:
				relative_points = []
				origin = []
				for circle in circles:
					cx, cy, r = circle
					orig_x, orig_y = stitched_to_original((cx, cy), H_inv)
					print(f"Crater at stitched ({cx}, {cy}) maps to original ({orig_x:.2f}, {orig_y:.2f}) with radius {r}")
					center = (cx, cy)

					origin = [orig_x, orig_y]
					relative_points.append([orig_x, orig_y, r])

					# Transform center
					center_stitched = transform_point(center, H)

					# Approximate radius scaling:
					# Transform a point on the circle's edge to get new radius
					edge_point_original = (center[0] + r, center[1])
					edge_point_stitched = transform_point(edge_point_original, H)

					# Euclidean distance in stitched space
					radius_stitched = int(round(np.linalg.norm(
						np.array(center_stitched) - np.array(edge_point_stitched)
					)))

					# Draw on stitched image
					output = pano.copy()
					cv2.circle(output, center_stitched, radius_stitched, (0, 255, 0), 2)
					cv2.circle(output, center_stitched, 2, (0, 0, 255), 3)

				cv2.imwrite("map/annotated_relative_map.png", output)
		
		system_state.write_state("cameraComplete")

		with open("coordinates.csv", "w") as f:
			print(f"{origin[0]:.2f}, {origin[1]:.2f}", file=f)

			for circle in relative_points:
				print(f"{circle[0]:.2f},{circle[1]:.2f}", file=f)

		if test:
			break

