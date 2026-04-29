import urllib.request, json, os

req = urllib.request.Request('http://127.0.0.1:5000/api/resolume_preview/ccb6c50b-7fe3-4989-98e9-d4d405b3c04c', 
    data=json.dumps({
        'selected_layers': ['z_whole'],
        'width': 1920,
        'height': 1080
    }).encode(),
    headers={'Content-Type': 'application/json'}
)
try:
    with urllib.request.urlopen(req) as res:
        print("Preview success!", len(json.loads(res.read())['polygons']))
        
        req2 = urllib.request.Request('http://127.0.0.1:5000/api/export/ccb6c50b-7fe3-4989-98e9-d4d405b3c04c',
            data=json.dumps({
                'selected_layers': [{'id': 'z_whole', 'name': 'Layer Custom', 'input_source': '0:1'}],
                'width': 1920,
                'height': 1080
            }).encode(),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req2) as res2:
            print("Export Status:", res2.status)
            with open('scratch/out.zip', 'wb') as f:
                f.write(res2.read())
        os.system('unzip -o scratch/out.zip -d scratch/out_zip')
except Exception as e:
    print("Failed")
    import traceback
    traceback.print_exc()
