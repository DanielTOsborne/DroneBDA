import signal
import cv2
import numpy as np
import os
import sys

# Graceful exit on Ctrl+C
def signal_handler(sig, frame):
    print("\n[INFO] Ctrl+C detected. Exiting...")
    cv2.destroyAllWindows()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

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

def main():
    # Path to calibration file (generated from chessboard calibration)
    calibration_file = "calibration_data.npz"
    camera_matrix, dist_coeffs = load_calibration(calibration_file)

    # Open default camera (0). Change index if multiple cameras.
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        sys.exit(1)

    print("Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break

        # Get optimal new camera matrix for undistortion
        h, w = frame.shape[:2]
        new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
            camera_matrix, dist_coeffs, (w, h), 1, (w, h)
        )

        # Undistort the frame
        undistorted_frame = cv2.undistort(frame, camera_matrix, dist_coeffs, None, new_camera_matrix)

        # Optional: crop the image to the valid ROI
        x, y, w, h = roi
        undistorted_frame = undistorted_frame[y:y+h, x:x+w]

        # Show both original and undistorted frames
        cv2.imshow("Original", frame)
        cv2.imshow("Undistorted", undistorted_frame)

        # Exit on 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
