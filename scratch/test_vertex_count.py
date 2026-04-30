import sys
import os
sys.path.append('.')
from mask_processor import get_resolume_polygon_data, load_mesh

filepath = './Octagon Full.obj'
full_mesh, face_mapping, scene = load_mesh(filepath, return_face_mapping=True)
selected_nodes = list(face_mapping.keys())

camera_settings = {
    'pos': [0, 0, 100],
    'target': [0, 0, 0],
    'fov': 60.0
}
data = get_resolume_polygon_data(filepath, selected_nodes, 1920, 1080, camera_settings=camera_settings)

for p_data in data:
    layer_id = p_data['layer_id']
    for i, loop in enumerate(p_data['resolume_loops']):
        print(f"Layer {layer_id}_{i} points: {len(loop['output'])}")
