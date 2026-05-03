
import os
import sys
import cv2
import numpy as np
import signal

# Graceful exit on Ctrl+C
def signal_handler(sig, frame):
	print("\n[INFO] Ctrl+C detected. Exiting...")
	cv2.destroyAllWindows()
	sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def detect_lines(image_path):
	# Load the image
	image = cv2.imread(image_path)
	if image is None:
		raise FileNotFoundError(f"Image not found: {image_path}")

	# Convert to grayscale
	gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

	# Apply Gaussian blur to reduce noise
	blurred = cv2.GaussianBlur(gray, (9, 9), 2)

	# Apply Canny edge detection
	edges = cv2.Canny(blurred, 50, 150, apertureSize=3)

	# Detect lines using Hough Transform
	# rho = 1 pixel, theta = 1 degree (in radians), threshold = 150
	lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)

	# Draw the detected lines on the original image
	if lines is not None:
		for rho, theta in lines[:, 0]:
			a = np.cos(theta)
			b = np.sin(theta)
			x0 = a * rho
			y0 = b * rho
			# Calculate start and end points of the line
			x1 = int(x0 + 1000 * (-b))
			y1 = int(y0 + 1000 * (a))
			x2 = int(x0 - 1000 * (-b))
			y2 = int(y0 - 1000 * (a))
			cv2.line(image, (x1, y1), (x2, y2), (0, 0, 255), 2)

	# Show results
	cv2.imshow("Edges", edges)
	cv2.imshow("Detected Lines", image)
	while True:
		if cv2.waitKey(1) > 0:
			cv2.destroyAllWindows()
			break


def detect_circles(image_path):
	if len(sys.argv) != 2:
		print("Usage: python script.py <image_path>")
		sys.exit(1)

	image_path = sys.argv[1]

	if not os.path.exists(image_path):
		print(f"Error: File '{image_path}' not found.")
		sys.exit(1)

	# Load image (grayscale)
	image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
	if image is None:
		raise FileNotFoundError("Image not found. Check the path.")

	# Apply Gaussian blur to reduce noise
	blurred = cv2.GaussianBlur(image, (9, 9), 2)

	# Edge detection (optional, HoughCircles can work without explicit edges)
	edges = cv2.Canny(blurred, 50, 150)

	# Detect circles using Hough Transform
	circles = cv2.HoughCircles(
		blurred,                       # Input image
		cv2.HOUGH_GRADIENT,            # Detection method
		dp=1.2,                        # Inverse ratio of accumulator resolution
		minDist=40,                    # Minimum distance between circle centers
		param1=100,                    # Higher threshold for Canny
		param2=40,                     # Accumulator threshold (lower = more detections)
		minRadius=30,                  # Minimum radius
		maxRadius=200                  # Maximum radius
	)

	# Convert circle parameters to integers
	output = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
	if circles is not None:
		circles = np.uint16(np.around(circles))
		for (x, y, r) in circles[0, :]:
			# Draw the outer circle
			cv2.circle(output, (x, y), r, (0, 255, 0), 2)
			# Draw the center
			cv2.circle(output, (x, y), 2, (0, 0, 255), 3)

	# Save and display result
	cv2.imwrite("reconstructed_circle.png", output)
	cv2.imshow("Detected Circle", output)
	while True:
		if cv2.waitKey(1) > 0:
			cv2.destroyAllWindows()
			break

if __name__ == "__main__":
	# Example usage: python build_circle.py path_to_image.jpg
	if len(sys.argv) != 2:
		print("Usage: python build_circle.py <image_path>")
		sys.exit(1)

	image_path = sys.argv[1]

	if not os.path.exists(image_path):
		print(f"Error: File '{image_path}' not found.")
		sys.exit(1)

	#detect_lines(image_path)

	detect_circles(image_path)