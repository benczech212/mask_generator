import urllib.request
import urllib.error
import json
import math
payload = {
    "selected_nodes": ["Octagon Full"],
    "hidden_groups": [],
    "hidden_bodies": [],
    "camera_settings": {
        "perspective": True,
        "eye": [6552, 15818, -3048],
        "target": [-3499, -8448, 7620],
        "fov": 60
    },
    "ortho_angle": "x"
}

import os
# find the latest session dir for Octagon Full
uploads = "temp_uploads"
latest_session = None
latest_time = 0

for d in os.listdir(uploads):
    dp = os.path.join(uploads, d)
    if os.path.isdir(dp):
        files = os.listdir(dp)
        if any("Octagon_Full" in f for f in files):
            mtime = os.path.getmtime(dp)
            if mtime > latest_time:
                latest_time = mtime
                latest_session = d

if latest_session:
    print(f"Testing session: {latest_session}")
    # first fetch preview_export to get layers
    req = urllib.request.Request(
        f"http://localhost:5000/api/preview_export/{latest_session}", 
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    layer_ids = []
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode('utf-8'))
        layer_ids = [l['id'] for l in data.get('layers', [])]
        
    payload["selected_nodes"] = layer_ids
    
    req2 = urllib.request.Request(
        f"http://localhost:5000/api/resolume_preview/{latest_session}", 
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req2) as res:
        raw_data = res.read().decode('utf-8')
        if "Infinity" in raw_data or "NaN" in raw_data:
            print("INVALID JSON VALUES FOUND!!")
        else:
            print("No invalid JSON values found")
