import os
from mask_processor import get_resolume_polygon_data

session_dir = 'temp_uploads/cdb176b3-fe7e-4314-a10c-5796001e6ee0'
filepath = os.path.join(session_dir, 'Octagon_Full.step')

selected_layer_ids = ['perspective_whole']
width = 1920
height = 1080
camera_settings = {
    'pos': [0, 0, 1000],
    'target': [0, 0, 0],
    'fov_y': 60
}

try:
    polygon_data = get_resolume_polygon_data(filepath, selected_layer_ids, width, height, [], [], camera_settings)
    print("Success!")
except Exception as e:
    import traceback
    traceback.print_exc()
