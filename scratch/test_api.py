import urllib.request, json, sys
url = f"http://{sys.argv[1]}:8080/api/v1/composition"
try:
    with urllib.request.urlopen(url, timeout=2) as r:
        data = json.loads(r.read())
        print(json.dumps(data.get('layers', [])[0], indent=2))
except Exception as e:
    print(e)
