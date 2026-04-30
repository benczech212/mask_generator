import cv2
import numpy as np
import matplotlib.pyplot as plt

# Create a test image with occlusion
# Two overlapping rectangles
img = np.zeros((400, 400), dtype=np.uint8)

# "Background" object in black (already black)

# "Target" object in white
cv2.rectangle(img, (100, 100), (300, 300), 255, -1)

# "Occluding" object in black
cv2.circle(img, (250, 250), 80, 0, -1)

# Find contours of white region
contours, hierarchy = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"Found {len(contours)} contours")

# Simplify contour
for i, contour in enumerate(contours):
    epsilon = 0.005 * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    print(f"Contour {i}: original pts={len(contour)}, simplified pts={len(approx)}")

