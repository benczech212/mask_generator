import os
import sys
import numpy as np
import cv2

# Mock data
width = 1920
height = 1080

def get_pixel_coords(verts, cx, cy, rx, ry, width, height):
    min_x, max_x = cx - rx / 2, cx + rx / 2
    min_y, max_y = cy - ry / 2, cy + ry / 2
    
    px = ((verts[:, 0] - min_x) / rx) * width
    py = ((verts[:, 1] - min_y) / ry) * height
    # Matplotlib's image coordinates have y=0 at top
    py = height - py
    
    return np.column_stack((px, py))

persp_verts = np.array([[0,0], [1,0], [1,1], [0,1]])
ortho_verts = np.array([[0,0], [2,0], [2,2], [0,2]])

persp_pts = get_pixel_coords(persp_verts, 0.5, 0.5, 2.0, 2.0, width, height)
ortho_pts = get_pixel_coords(ortho_verts, 1.0, 1.0, 4.0, 4.0, width, height)

H, _ = cv2.findHomography(persp_pts, ortho_pts)
print("Homography:", H)

loop = [persp_pts[0].tolist(), persp_pts[1].tolist(), persp_pts[2].tolist()]
loop_array = np.array(loop, dtype=np.float32).reshape(-1, 1, 2)
ortho_loop = cv2.perspectiveTransform(loop_array, H).reshape(-1, 2).tolist()
print("Mapped loop:", ortho_loop)
print("Expected ortho pts:", ortho_pts[:3].tolist())
