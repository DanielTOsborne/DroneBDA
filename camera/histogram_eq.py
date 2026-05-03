import signal
import cv2
import numpy as np
import sys
import os

# Graceful exit on Ctrl+C
def signal_handler(sig, frame):
    print("\n[INFO] Ctrl+C detected. Exiting...")
    cv2.destroyAllWindows()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def histogram_equalization(image):
    """
    Perform histogram equalization on a grayscale image.
    """
    return cv2.equalizeHist(image)

def contrast_stretching(image):
    """
    Perform contrast stretching on a grayscale image.
    Formula: (pixel - min) * (255 / (max - min))
    """
    min_val = np.min(image)
    max_val = np.max(image)
    
    if max_val == min_val:
        # Avoid division by zero (flat image)
        return image.copy()
    
    stretched = (image - min_val) * (255.0 / (max_val - min_val))
    return stretched.astype(np.uint8)

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(f"Error: File '{image_path}' not found.")
        sys.exit(1)

    # Read the image in grayscale
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print("Error: Unable to read image. Ensure it's a valid image file.")
        sys.exit(1)

    # Apply Histogram Equalization
    hist_eq_img = histogram_equalization(img)

    # Apply Contrast Stretching
    contrast_img = contrast_stretching(img)

    # Display results
    cv2.imshow("Original", img)
    cv2.imshow("Histogram Equalization", hist_eq_img)
    cv2.imshow("Contrast Stretching", contrast_img)

    # Save results
    cv2.imwrite("output_hist_eq.jpg", hist_eq_img)
    cv2.imwrite("output_contrast_stretch.jpg", contrast_img)

    print("Processing complete. Results saved as 'output_hist_eq.jpg' and 'output_contrast_stretch.jpg'.")
    while True:
        cv2.waitKey(1)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
