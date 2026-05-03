import signal
import cv2
import sys
import os
import numpy as np

# Graceful exit on Ctrl+C
def signal_handler(sig, frame):
    print("\n[INFO] Ctrl+C detected. Exiting...")
    cv2.destroyAllWindows()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(f"Error: File '{image_path}' not found.")
        sys.exit(1)

    # Load image from file
    image = cv2.imread(image_path, cv2.IMREAD_COLOR)

    # Validate image load
    if image is None:
        print(f"Error: Could not load image from '{image_path}'.")
        sys.exit(1)

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur to reduce noise before edge detection
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.4)

    # Perform Canny edge detection
    # Threshold1 and Threshold2 can be tuned for better results
    edges = cv2.Canny(blurred, threshold1=100, threshold2=200)

    # Display results
    cv2.imshow("Original Image", image)
    cv2.imshow("Edges", edges)

    # Save the edge-detected image
    output_path = "edges_output.jpg"
    cv2.imwrite(output_path, edges)
    print(f"Edge-detected image saved as '{output_path}'.")

    # Wait for a key press and close windows
    while True:
        cv2.waitKey(1)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
