import cv2
import numpy as np
import glob

# Define the dimensions of checkerboard
CHECKERBOARD = (9, 6)  # (number of inner corners per a chessboard row and column)
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# 3D points in real world space
objp = np.zeros((CHECKERBOARD[0]*CHECKERBOARD[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)
objp *= 24.6  # Scale the object points to the actual size of the checkerboard squares (24.6mm)

objpoints = []  # 3d point in real world space
imgpoints = []  # 2d points in image plane.

# If you have a set of calibration images, use glob to read them
images = glob.glob('calibration/*.jpg')  # Place your calibration images in this folder

for fname in images:
    img = cv2.imread(fname)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Find the chess board corners
    ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)

    # If found, add object points, image points (after refining them)
    if ret:
        objpoints.append(objp)
        corners2 = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1), criteria)
        imgpoints.append(corners2)

        # Draw and display the corners
        img = cv2.drawChessboardCorners(img, CHECKERBOARD, corners2, ret)
        cv2.imshow('img', img)
        cv2.waitKey(5000)

cv2.destroyAllWindows()

# Calibration
ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)

print("Camera matrix :\n", mtx)
print("Distortion coefficients :\n", dist)
print("Rotation Vectors :\n", rvecs)
print("Translation Vectors :\n", tvecs)

# Save the calibration results
np.savez('calibration_data.npz', mtx=mtx, dist=dist, rvecs=rvecs, tvecs=tvecs)
