import sys
sys.path.append('.')
from mask_processor import get_resolume_polygon_data
filepath = "temp_uploads/3900a792-ca8d-4ab5-b005-99590d6efafe/Octagon_Full.step"
import os

uploads = "temp_uploads"
latest_session = None
latest_time = 0

for d in os.listdir(uploads):
    dp = os.path.join(uploads, d)
    if os.path.isdir(dp):
        files = os.listdir(dp)
        if any("Octagon_Full" in f for f in files) or any("Octagon Full" in f for f in files):
            mtime = os.path.getmtime(dp)
            if mtime > latest_time:
                latest_time = mtime
                latest_session = d
                filepath = os.path.join(dp, files[0])

if latest_session:
    print(f"Testing session: {latest_session}")
    camera_settings = {
        "perspective": True,
        "eye": [6552, 15818, -3048],
        "target": [-3499, -8448, 7620],
        "fov": 60
    }
    
    # Run directly
    polygon_data = get_resolume_polygon_data(filepath, ["Octagon Full"], 1920, 1080, [], [], camera_settings, is_layer_ids=False, ortho_angle='-z', cull_backfaces=False)
    
    print(f"Found {len(polygon_data)} polygons")
    for i, p in enumerate(polygon_data[:3]):
        print(f"Poly {i}:")
        for loop in p['loops']:
            print(loop)
