import cv2
import numpy as np
import math
import sys

def detect_lines(image_path, canny_thresh1=50, canny_thresh2=150, hough_thresh=130):
	"""Detect lines in an image using Canny + Hough Transform."""
	img = cv2.imread(image_path)
	if img is None:
		raise FileNotFoundError(f"Image not found: {image_path}")

	gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
	# Apply Gaussian blur to reduce noise
	blurred = cv2.GaussianBlur(gray, (9, 9), 2)

	edges = cv2.Canny(blurred, canny_thresh1, canny_thresh2, apertureSize=3)

	# HoughLines returns (rho, theta) for each line
	lines = cv2.HoughLines(edges, 1, np.pi / 180, hough_thresh)
	return img, lines

def are_parallel(theta1, theta2, angle_tolerance_deg=2):
	"""Check if two lines are parallel within a tolerance."""
	angle_diff = abs(theta1 - theta2)
	angle_diff = min(angle_diff, np.pi - angle_diff)  # handle wrap-around
	return math.degrees(angle_diff) <= angle_tolerance_deg

def distance_between_parallel_lines(rho1, rho2):
	"""Distance between two parallel lines in pixels."""
	return abs(rho1 - rho2)

def find_parallel_lines(lines, angle_tolerance_deg=2):
	"""Find all pairs of parallel lines and their distances."""
	parallels = []
	if lines is None:
		return parallels

	lines = [l[0] for l in lines]  # unpack from [[[rho, theta]], ...]
	for i in range(len(lines)):
		rho1, theta1 = lines[i]
		for j in range(i + 1, len(lines)):
			rho2, theta2 = lines[j]
			if are_parallel(theta1, theta2, angle_tolerance_deg):
				dist = distance_between_parallel_lines(rho1, rho2)
				parallels.append(((rho1, theta1), (rho2, theta2), dist))
	return parallels

def draw_lines(img, lines):
	"""Draw lines on the image for visualization."""
	drawn = img.copy()
	if lines is None:
		return drawn
	for rho, theta in [l[0] for l in lines]:
		a = math.cos(theta)
		b = math.sin(theta)
		x0 = a * rho
		y0 = b * rho
		x1 = int(x0 + 1000 * (-b))
		y1 = int(y0 + 1000 * (a))
		x2 = int(x0 - 1000 * (-b))
		y2 = int(y0 - 1000 * (a))
		cv2.line(drawn, (x1, y1), (x2, y2), (0, 0, 255), 2)
	return drawn

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("Usage: python detect_parallel_lines.py <image_path>")
		sys.exit(1)

	image_path = sys.argv[1]
	img, lines = detect_lines(image_path)

	parallels = find_parallel_lines(lines, angle_tolerance_deg=2)
	max_distance = 0

	if parallels:
		print("Parallel lines found:")
		for (l1, l2, dist) in parallels:
			print(f"Line1 (rho={l1[0]:.2f}, theta={math.degrees(l1[1]):.2f}°) "
				f"|| Line2 (rho={l2[0]:.2f}, theta={math.degrees(l2[1]):.2f}°) "
				f"=> Distance: {dist:.2f} px")
			if dist > max_distance:
				max_distance = dist
		print(f"Maximum distance between parallel lines: {max_distance:.2f} px")
	else:
		print("No parallel lines found.")

	
	# Optional: visualize detected lines
	drawn_img = draw_lines(img, lines)
	cv2.imshow("Detected Lines", drawn_img)
	while True:
		if cv2.waitKey(1) > 0:
			cv2.destroyAllWindows()
			break
