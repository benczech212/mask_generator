import numpy as np
import matplotlib.tri as mtri

# Mock data
width = 1920
height = 1080

def get_pixel_coords(verts, cx, cy, rx, ry, w, h):
    min_x, min_y = cx - rx / 2, cy - ry / 2
    px = ((verts[:, 0] - min_x) / rx) * w
    py = ((verts[:, 1] - min_y) / ry) * h
    py = h - py
    return np.column_stack((px, py))

# A simple 3D object: a tent shape
verts_3d = np.array([
    [0, 0, 0],
    [1, 0, 0],
    [1, 1, 0],
    [0, 1, 0],
    [0.5, 0.5, 1]
])
faces = np.array([
    [0, 1, 4],
    [1, 2, 4],
    [2, 3, 4],
    [3, 0, 4]
])

# Perspective projection (mock)
persp_verts = verts_3d[:, :2] * (1.0 - verts_3d[:, 2:] * 0.2)
ortho_verts = verts_3d[:, :2]

persp_pts = get_pixel_coords(persp_verts, 0.5, 0.5, 2.0, 2.0, width, height)
ortho_pts = get_pixel_coords(ortho_verts, 0.5, 0.5, 2.0, 2.0, width, height)

# Points we want to map (e.g. from cv2.findContours)
p_loop = [
    persp_pts[0].tolist(), # [0, 0] mapped
    ((persp_pts[0] + persp_pts[1]) / 2).tolist(), # Midpoint edge
    persp_pts[4].tolist()  # Peak
]

# Use Triangulation to find barycentric coords
triangulation = mtri.Triangulation(persp_pts[:, 0], persp_pts[:, 1], faces)
trifinder = triangulation.get_trifinder()

o_loop = []
for p in p_loop:
    tri_idx = trifinder(p[0], p[1])
    if tri_idx != -1:
        face = faces[tri_idx]
        v0, v1, v2 = persp_pts[face[0]], persp_pts[face[1]], persp_pts[face[2]]
        # Barycentric coords
        denom = (v1[1] - v2[1]) * (v0[0] - v2[0]) + (v2[0] - v1[0]) * (v0[1] - v2[1])
        w0 = ((v1[1] - v2[1]) * (p[0] - v2[0]) + (v2[0] - v1[0]) * (p[1] - v2[1])) / denom
        w1 = ((v2[1] - v0[1]) * (p[0] - v2[0]) + (v0[0] - v2[0]) * (p[1] - v2[1])) / denom
        w2 = 1.0 - w0 - w1
        
        o0, o1, o2 = ortho_pts[face[0]], ortho_pts[face[1]], ortho_pts[face[2]]
        o_pt = w0 * o0 + w1 * o1 + w2 * o2
        o_loop.append(o_pt.tolist())
    else:
        print("Point outside triangles:", p)
        # Find nearest vertex fallback
        dists = np.sum((persp_pts - p)**2, axis=1)
        nearest = np.argmin(dists)
        o_loop.append(ortho_pts[nearest].tolist())

print("P Loop:", p_loop)
print("O Loop:", o_loop)
