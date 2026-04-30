import urllib.request
import urllib.error
import json
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
    req = urllib.request.Request(
        f"http://localhost:5000/api/preview_export/{latest_session}", 
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode('utf-8'))
            if 'layers' in data:
                print(f"Found {len(data['layers'])} layers")
            else:
                print(data)
    except urllib.error.HTTPError as e:
        print(e.code, e.read().decode('utf-8'))
else:
    print("No session found")
