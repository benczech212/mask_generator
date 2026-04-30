import sys
sys.path.append('.')
from mask_processor import load_mesh
filepath = "temp_uploads/3900a792-ca8d-4ab5-b005-99590d6efafe/Octagon_Full.step"
mesh, face_map, scene = load_mesh(filepath, return_face_mapping=True)
for node, mats in face_map.items():
    for mat in mats.keys():
        print(f"Layer ID: {node}_{mat}")
