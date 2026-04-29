import trimesh
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

def get_perspective_projection(vertices, fov, aspect, near, far, camera_pos, camera_target, up_vector):
    # Calculate view matrix
    zaxis = camera_pos - camera_target
    zaxis = zaxis / np.linalg.norm(zaxis)
    xaxis = np.cross(up_vector, zaxis)
    xaxis = xaxis / np.linalg.norm(xaxis)
    yaxis = np.cross(zaxis, xaxis)
    
    view_mat = np.eye(4)
    view_mat[0, :3] = xaxis
    view_mat[1, :3] = yaxis
    view_mat[2, :3] = zaxis
    view_mat[0, 3] = -np.dot(xaxis, camera_pos)
    view_mat[1, 3] = -np.dot(yaxis, camera_pos)
    view_mat[2, 3] = -np.dot(zaxis, camera_pos)
    
    # Calculate projection matrix
    f = 1.0 / np.tan(fov / 2.0)
    proj_mat = np.zeros((4, 4))
    proj_mat[0, 0] = f / aspect
    proj_mat[1, 1] = f
    proj_mat[2, 2] = (near + far) / (near - far)
    proj_mat[2, 3] = (2 * near * far) / (near - far)
    proj_mat[3, 2] = -1.0
    
    # Transform vertices
    ones = np.ones((len(vertices), 1))
    v4 = np.hstack([vertices, ones])
    
    v4_view = v4 @ view_mat.T
    v4_proj = v4_view @ proj_mat.T
    
    # Perspective divide
    v2_proj = v4_proj[:, :2] / v4_proj[:, 3:4]
    return v2_proj

scene = trimesh.load('../Octagon.obj')
print(f"Loaded {len(scene.geometry)} geometries.")

# Perspective settings
camera_pos = np.array([50.0, -50.0, 50.0])
camera_target = np.array([0.0, 0.0, 0.0])
up_vector = np.array([0.0, 0.0, 1.0])
fov = np.radians(60)

fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_facecolor('white')
ax.axis('off')

colors = ['red', 'green', 'blue', 'cyan', 'magenta', 'yellow']
i = 0

all_v2 = []

for name, geom in scene.geometry.items():
    v2 = get_perspective_projection(geom.vertices, fov, 1920/1080, 0.1, 1000.0, camera_pos, camera_target, up_vector)
    all_v2.append(v2)
    tris = v2[geom.faces]
    
    collection = PolyCollection(tris, facecolors=colors[i % len(colors)], edgecolors='black', linewidths=0.5)
    ax.add_collection(collection)
    i += 1

all_v2 = np.vstack(all_v2)
min_x, min_y = np.min(all_v2, axis=0)
max_x, max_y = np.max(all_v2, axis=0)

range_x = max_x - min_x
range_y = max_y - min_y
center_x = (max_x + min_x) / 2
center_y = (max_y + min_y) / 2

target_ratio = 1920 / 1080
actual_ratio = range_x / range_y if range_y != 0 else 1

if actual_ratio < target_ratio:
    range_x = range_y * target_ratio
else:
    range_y = range_x / target_ratio

ax.set_xlim(center_x - range_x * 0.6, center_x + range_x * 0.6)
ax.set_ylim(center_y - range_y * 0.6, center_y + range_y * 0.6)

plt.savefig('test_perspective.png', dpi=100)
print("Saved test_perspective.png")
