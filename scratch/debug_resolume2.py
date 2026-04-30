import os
import trimesh
from mask_processor import get_scene_hierarchy, get_resolume_polygon_data

session_dir = 'temp_uploads/cdb176b3-fe7e-4314-a10c-5796001e6ee0'
filepath = os.path.join(session_dir, 'Octagon_Full.step')

if not os.path.exists(filepath):
    print(f"File not found: {filepath}")
    import sys
    sys.exit(1)

hierarchy = get_scene_hierarchy(filepath)
layer_ids = [layer['id'] for layer in hierarchy['layers']]
print(f"Found layers: {layer_ids}")

if layer_ids:
    print(f"Testing with layer: {layer_ids[0]}")
    try:
        get_resolume_polygon_data(filepath, [layer_ids[0]], 1920, 1080, [], [], None)
        print("Success!")
    except Exception as e:
        import traceback
        traceback.print_exc()
