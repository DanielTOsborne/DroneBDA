from collections import Counter
import socket
from typing import Any, List, Tuple
import cv2
import numpy as np
import math
import sys
import os

from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

MAX_DISTANCE = 300
INTERACTIVE = False

def show_image(title, img, max_size=1000):
	if INTERACTIVE:
		if(max(img.shape[0], img.shape[1]) > max_size):
			print(img.shape)
			scale_factor = max_size / max(img.shape[0], img.shape[1])
			img = cv2.resize(img, (int(img.shape[1] * scale_factor), int(img.shape[0] * scale_factor)))

		cv2.imshow(title, img)
	
def gradient_gaussian_edge_preserve(gray, sigma=1.5, edge_strength=1.0):
	"""
	Apply Gaussian smoothing while preserving hard edges using gradient masking.

	:param image_path: Path to the input image
	:param sigma: Standard deviation for Gaussian blur
	:param edge_strength: Multiplier for edge enhancement
	:return: Processed image
	"""
	# Apply Gaussian blur
	blurred = cv2.GaussianBlur(gray, (0, 0), sigma)

	# Compute gradients using Sobel operator
	grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
	grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)

	# Compute gradient magnitude
	gradient_magnitude = cv2.magnitude(grad_x, grad_y)

	# Normalize to [0,1] for blending
	gradient_norm = cv2.normalize(gradient_magnitude, None, 0.0, 1.0, cv2.NORM_MINMAX)

	# Create edge mask (strong edges = keep original, weak edges = use blur)
	edge_mask = np.expand_dims(gradient_norm, axis=2) ** edge_strength

	gray_exp = np.expand_dims(gray, axis=2)  # shape (H, W, 1)
	blurred_exp = np.expand_dims(gray, axis=2)  # shape (H, W, 1)

	# Blend blurred and original image based on edge mask
	result = (gray_exp * edge_mask + blurred_exp * (1 - edge_mask)).astype(np.uint8)

	return result

def detect_lines(image_path, canny_thresh1=75, canny_thresh2=200, hough_thresh=130):
	"""Detect lines in an image using Canny + Hough Transform."""
	img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
	if img is None:
		raise FileNotFoundError(f"Image not found: {image_path}")

	# Apply Gaussian blur to reduce noise
	blurred = gradient_gaussian_edge_preserve(img, sigma=1.3, edge_strength=1)

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

def find_parallel_lines(lines, angle_tolerance_deg=2, min_distance=200):
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
				if dist > min_distance:
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

def circle_relation(c1, r1, c2, r2):
	# Distance between centers
	dist = math.dist(c1, c2)
	
	if dist + min(r1, r2) <= max(r1, r2):
		return 2 #"One circle is inside the other"
	elif dist < r1 + r2:
		return 1 #"Circles overlap"
	elif dist == r1 + r2:
		return -1 #"Circles touch externally"
	else:
		return 0 #"Circles are separate"
	
def filter_circles_by_mode(circles):
	"""
	Given a list of circles (as radii), find the mode radius and
	discard circles with radius greater than the mode.
	
	:param circles: list of positive numbers (radii)
	:return: filtered list of radii
	"""
	# Validate input
	if not isinstance(circles, list) or not all(isinstance(r, (int, float)) and r > 0 for r in circles):
		raise ValueError("Input must be a list of positive numbers representing radii.")

	if not circles:
		return []

	# Find the mode radius
	radius_counts = Counter(circles)
	mode_radius = max(radius_counts.items(), key=lambda x: (x[1], -x[0]))[0]
	# ^ Picks the most frequent; if tie, picks the smaller radius

	# Filter out circles larger than the mode
	filtered = [r for r in circles if r <= mode_radius]

	return filtered, mode_radius

def group_lines_by_theta_radians(lines, tolerance_deg=2):
	"""
	Group lines by theta within ±tolerance_deg degrees (theta in radians).
	
	Args:
		lines (list of dict): Each dict should have at least {'rho': float, 'theta': float}.
							Theta is in radians (0–2π).
		tolerance_deg (float): Allowed deviation in degrees for grouping.
	
	Returns:
		list of list: Groups of lines.
	"""

	# Convert tolerance from degrees to radians
	tolerance_rad = tolerance_deg * math.pi / 180.0
	
	# Normalize theta to [0, 2π)
	lines = lines.copy()  # avoid modifying original
	for line in lines:
		line[0][1] = line[0][1] % (2 * math.pi)

	# Sort by theta
	sorted_lines = sorted(lines, key=lambda x: x[0][1])

	groups = []
	current_group = [sorted_lines[0]]
	
	for line in sorted_lines[1:]:
		prev_theta = current_group[-1][0][1]
		diff = min(abs(line[0][1] - prev_theta),
				2 * math.pi - abs(line[0][1] - prev_theta))

		if diff <= tolerance_rad or math.isclose(diff, tolerance_rad, abs_tol=1e-12):
			current_group.append(line)
		else:
			groups.append(current_group)
			current_group = [line]
	
	groups.append(current_group)

	# Merge first and last group if they wrap around (e.g., near 0 and 2π)
	first_theta = groups[0][0][0][1]
	last_theta = groups[-1][-1][0][1]
	wrap_diff = min(abs(first_theta - last_theta),
					2 * math.pi - abs(first_theta - last_theta))
	
	if wrap_diff <= tolerance_rad:
		groups[0] = groups[-1] + groups[0]
		groups.pop()
	
	return groups

# Convert (rho, theta) to two points for each line
def rho_theta_to_points(rho, theta, length=2000):
	a = np.cos(theta)
	b = np.sin(theta)
	x0 = a * rho
	y0 = b * rho
	pt1 = (int(x0 + length * (-b)), int(y0 + length * (a)))
	pt2 = (int(x0 - length * (-b)), int(y0 - length * (a)))
	return pt1, pt2

def combine_polygons():
	# Define two polygons (coordinates in (x, y) order)
	polygon1 = Polygon([(0, 0), (4, 0), (4, 4), (0, 4)])
	polygon2 = Polygon([(2, 2), (6, 2), (6, 6), (2, 6)])

	# Validate polygons (Shapely automatically fixes some invalid shapes)
	if not polygon1.is_valid or not polygon2.is_valid:
		raise ValueError("One or both polygons are invalid.")

	# Check if they overlap
	if polygon1.intersects(polygon2):
		print("Polygons overlap.")

		# Intersection (overlapping region)
		overlap_region = polygon1.intersection(polygon2)
		print("Overlap area:", overlap_region.area)

		# Union (combined shape without duplicates)
		combined_shape = unary_union([polygon1, polygon2])
		print("Combined area:", combined_shape.area)

		# Difference (part of polygon1 not in polygon2)
		difference_shape = polygon1.difference(polygon2)
		print("Polygon1 minus Polygon2 area:", difference_shape.area)
	else:
		print("Polygons do not overlap.")

	# Optional: Output WKT (Well-Known Text) for visualization/debugging
	print("Overlap WKT:", overlap_region.wkt if polygon1.intersects(polygon2) else "None")


def detect_circles(image_path, max_radius:int=200, lines=None, distance_from_edge=40):
	if not os.path.exists(image_path):
		print(f"Error: File '{image_path}' not found.")
		sys.exit(1)

	# Load image (grayscale)
	image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
	if image is None:
		raise FileNotFoundError("Image not found. Check the path.")

	# Apply Gaussian blur to reduce noise
	blurred = cv2.GaussianBlur(image, (5, 5), 2)

	regions = []
	if lines is not None and len(lines) > 0:
		# Mask with lines
		mask = np.zeros(blurred.shape, dtype=np.uint8)
		for line in lines:
			rho, theta = line[0]
			a = math.cos(theta)
			b = math.sin(theta)
			x0 = a * rho
			y0 = b * rho
			x1 = int(x0 + 1000 * (-b))
			y1 = int(y0 + 1000 * (a))
			x2 = int(x0 - 1000 * (-b))
			y2 = int(y0 - 1000 * (a))
			cv2.line(mask, (x1, y1), (x2, y2), 255, 5)  # thicker line for masking

		groups = group_lines_by_theta_radians(lines, tolerance_deg=1)

		#polygon_points = np.array(dtype=np.int32).reshape(0, 4, 2)  # shape (N, 4, 2) for quadrilaterals
		polygons = MultiPolygon()
		for lines in groups:
			for line1 in lines:
				for line2 in lines:
					if len(lines) < 2:
						continue

					rho1, theta1 = line1[0]
					rho2, theta2 = line2[0]
					pt1_1, pt1_2 = rho_theta_to_points(rho1, theta1)
					pt2_1, pt2_2 = rho_theta_to_points(rho2, theta2)

					# Create a mask for the region between the two parallel lines
					cv2.fillPoly(mask, [np.array([pt1_1, pt1_2, pt2_2, pt2_1])], 255)
					if polygons.is_empty:
						polygons = MultiPolygon([Polygon([pt1_1, pt1_2, pt2_2, pt2_1])])
					else:
						poly = Polygon([pt1_1, pt1_2, pt2_2, pt2_1])
						if poly.is_valid:
							polygons = polygons.union(poly)
							polygons = unary_union(polygons)  # merge overlapping polygons

					print("Merged geometry type:", polygons.geom_type)
					print("Is merged geometry valid?", polygons.is_valid)
					regions.append(mask)

		safe_polygons = polygons.buffer(-distance_from_edge)  # shrink inward

		safe_mask = np.zeros(blurred.shape, dtype=np.uint8)
		if not safe_polygons.is_empty:
			if safe_polygons.geom_type == 'Polygon':
				pts = np.array(safe_polygons.exterior.coords, dtype=np.int32)
				cv2.fillPoly(safe_mask, [pts], 255)
			elif safe_polygons.geom_type == 'MultiPolygon':
				for subpoly in safe_polygons:
					pts = np.array(subpoly.exterior.coords, dtype=np.int32)
					cv2.fillPoly(safe_mask, [pts], 255)

		# Optional: apply mask to image
		masked_image = cv2.bitwise_and(image, image, mask=safe_mask)

		show_image("Masked Image", masked_image)
		input_image = masked_image
	else:
		input_image = blurred

	# Detect circles using Hough Transform
	circles = cv2.HoughCircles(
		input_image,                   # Input image
		cv2.HOUGH_GRADIENT,            # Detection method
		dp=1.2,                        # Inverse ratio of accumulator resolution
		minDist=30,                    # Minimum distance between circle centers
		param1=100,                    # Higher threshold for Canny
		param2=30,                     # Accumulator threshold (lower = more detections)
		minRadius=int(max_radius / 8),      # Minimum radius
		maxRadius=max_radius           # Maximum radius
	)

	# Convert circle parameters to integers
	output = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

	# Save and display result
	output = draw_lines(output, lines)

	filtered = []

	if circles is not None:
		circles = np.uint16(np.around(circles))
		# Convert to integer list of tuples
		circles = np.around(circles[0, :]).astype(int)  # shape (N, 3)
		circles = [[x, y, r] for x, y, r in circles]

		# Sort circles by radius (largest first)
		circles = sorted(circles, key=lambda c: c[2], reverse=True)

		# Extract radii
		radii = [r for _, _, r in circles]

		# Find mode of radii
		radius_counts = Counter(radii)
		mode_radius = radius_counts.most_common(1)[0][0]

		print(f"Mode radius: {mode_radius}")
		print(repr(radius_counts))

		# Discard circles with radius greater than mode
		circles = [c for c in circles if c[2] <= mode_radius]

		if lines is not None and len(lines) > 0:
			# Distance transform from mask edge
			edges = cv2.morphologyEx(masked_image, cv2.MORPH_GRADIENT, np.ones((3,3), np.uint8))
			dist_map = cv2.distanceTransform(cv2.bitwise_not(edges), cv2.DIST_L2, 5)

			# Filter circles by distance from mask edge
			min_dist_from_edge = 40  # pixels
			valid_circles = []
			if circles is not None:
				for x, y, r in circles:
					if dist_map[y, x] >= min_dist_from_edge:
						valid_circles.append([x, y, r])
						print(f"Keeping circle at ({x}, {y}) with radius {r} (distance from edge: {dist_map[y, x]:.2f} px)")
					else:
						print(f"Discarding circle at ({x}, {y}) with radius {r} due to proximity to edge (distance {dist_map[y, x]:.2f} px)")
			circles = valid_circles

		for c in circles:
			x, y, r = c
			keep = True
			for fx, fy, fr in filtered:
				relation = circle_relation((x, y), r, (fx, fy), fr)
				if relation != 0:
					print(f"Discarding circle at ({x}, {y}) with radius {r} due to relation {relation} with circle at ({fx}, {fy}) with radius {fr}")
					keep = False
					break
			if keep:
				print(f"Keeping circle at ({x}, {y}) with radius {r} after relation checks")
				filtered.append([x, y, r])

		for (x, y, r) in filtered[0:]:
			# Draw the outer circle
			cv2.circle(output, (x, y), r, (0, 255, 0), 2)
			# Draw the center
			cv2.circle(output, (x, y), 2, (0, 0, 255), 3)

	cv2.imwrite("map/annotated_map.png", output)
	show_image("Detected Circle", output)

	return filtered

def flatten_rho_theta_ignore_distance(data: List[Any]) -> List[Tuple[float, float]]:
	"""
	Flattens an array of rho/theta pairs with optional distances, ignoring the distance values.

	Args:
		data: List of entries like [[rho, theta], distance] or [[[rho, theta]]].

	Returns:
		A flat list of (rho, theta) tuples.
	"""
	flattened = []
	for entry in data:
		# Handle OpenCV HoughLines format [[[rho, theta]]]
		if isinstance(entry, (list, tuple)) and len(entry) == 1 and isinstance(entry[0], (list, tuple)):
			rho_theta = entry[0]
		# Handle custom format [[rho, theta], distance]
		elif isinstance(entry, (list, tuple)) and len(entry) >= 1:
			rho_theta = entry[0]
		else:
			raise ValueError(f"Invalid entry format: {entry}")

		if not (isinstance(rho_theta, (list, tuple)) and len(rho_theta) == 2):
			raise ValueError(f"Invalid rho/theta format: {rho_theta}")

		flattened.append([[float(rho_theta[0]), float(rho_theta[1])]])

	return flattened

def find_craters(image_path):
	img, lines = detect_lines(image_path)

	parallels = find_parallel_lines(lines, angle_tolerance_deg=1, min_distance=MAX_DISTANCE / 2)
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

	show_image("Detected Edges", draw_lines(img, parallels))

	if max_distance == 0:
		max_distance = MAX_DISTANCE  # default value if no parallels found
	else:
		max_distance /= 8  # use an eighth of the max distance between parallels as max radius for circles
		if max_distance < 20:
			max_distance = MAX_DISTANCE  # if distance is too small, assume bogus value and use default

	print(f"Using max circle radius: {max_distance:.2f} px")

	# Detect circles
	circles = detect_circles(image_path, int(max_distance), flatten_rho_theta_ignore_distance(parallels))

	return circles

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("Usage: python detect_parallel_lines.py <image_path>")
		sys.exit(1)

	INTERACTIVE = True
	image_path = sys.argv[1]

	circles = find_craters(image_path)

	# Push data to socket
	client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	client_socket.connect("/tmp/detection_socket")

	# Send circle data
	for circle in circles:
		data = f"{circle[0]},{circle[1]}\n"
		client_socket.sendall(data.encode())

	client_socket.close()

	while True:
		if cv2.waitKey(1) > 0:
			cv2.destroyAllWindows()
			break
