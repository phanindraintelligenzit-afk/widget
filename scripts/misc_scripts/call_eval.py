import urllib.request
import json

url = 'http://127.0.0.1:8000/api/cost-evaluation/evaluate'
req = urllib.request.Request(url, method='POST', headers={'Accept': 'application/json'})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        print("Success:")
except Exception as e:
    print(f"Error: {e}")
