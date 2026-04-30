import sys
import numpy as np
import trimesh

sys.path.append('.')
from mask_processor import load_mesh, get_transform_params

camera_settings = {
    'pos': [6552, 15818, -3048],
    'target': [-3499, -8448, 7620]
}

# The user uploaded a step file recently, let's find it.
import os
upload_dir = 'temp_uploads'
sessions = os.listdir(upload_dir)
if sessions:
    latest_session = max(sessions, key=lambda s: os.path.getmtime(os.path.join(upload_dir, s)))
    files = [f for f in os.listdir(os.path.join(upload_dir, latest_session)) if f.endswith('.step') or f.endswith('.stp')]
    if files:
        filepath = os.path.join(upload_dir, latest_session, files[0])
        print(f"Loading {filepath}")
        mesh = load_mesh(filepath)
        verts, cx, cy, rx, ry, z = get_transform_params(mesh, 'perspective', 1920, 1080, camera_settings)
        print(f"cx: {cx}, cy: {cy}")
        print(f"rx: {rx}, ry: {ry}")
        
        valid_faces_mask = np.any(z[mesh.faces] < 0, axis=1)
        valid_tris = verts[mesh.faces[valid_faces_mask]]
        min_x, min_y = np.min(valid_tris.reshape(-1, 2), axis=0)
        max_x, max_y = np.max(valid_tris.reshape(-1, 2), axis=0)
        print(f"min_x: {min_x}, max_x: {max_x}, diff: {max_x - min_x}")
        print(f"min_y: {min_y}, max_y: {max_y}, diff: {max_y - min_y}")
