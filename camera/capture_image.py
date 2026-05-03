#!/usr/bin/env python3
"""
Capture a single snapshot from a V4L2 camera device using v4l2py.
Requires: pip install v4l2py numpy opencv-python
"""

import sys
import cv2
import numpy as np
from linuxpy.video.device import Device
import v4l2

def show_image(title, img, max_size=1000):
	if(max(img.shape[0], img.shape[1]) > max_size):
		print(img.shape)
		scale_factor = max_size / max(img.shape[0], img.shape[1])
		img = cv2.resize(img, (int(img.shape[1] * scale_factor), int(img.shape[0] * scale_factor)))

	cv2.imshow(title, img)

def capture_snapshot(device_id=0, output_file=None):
	# Open the V4L2 device
	with Device.from_id(device_id) as cam:
		
		# Set desired format (width, height, pixel format)
		cam.set_format(width=1920, height=1080, buffer_type=v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE)
		frame = next(iter(cam))
		
	# Convert MJPEG bytes to an OpenCV image
	np_arr = np.frombuffer(frame.data, np.uint8)
	img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

	if img is None:
		raise ValueError("Failed to decode image from camera.")

	# Save snapshot
	if output_file is not None:
		cv2.imwrite(output_file, img)
		
	show_image("Snapshot", img)
	print(f"Snapshot saved to {output_file}")

if __name__ == "__main__":
	# Allow optional device path and output file from command line
	dev_path = sys.argv[1] if len(sys.argv) > 1 else "0"
	out_file = sys.argv[2] if len(sys.argv) > 2 else "snapshot.jpg"
	capture_snapshot(int(dev_path), out_file)

	while True:
		if cv2.waitKey(1) > 0:
			cv2.destroyAllWindows()
			break
