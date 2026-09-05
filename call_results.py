import urllib.request
import json

url = 'http://127.0.0.1:8000/api/cost-evaluation/results'
req = urllib.request.Request(url, method='GET', headers={'Accept': 'application/json'})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        for d in data:
            if d['metric'] in ['efficiency_ratio', 'human_cost_per_output']:
                print(d)
except Exception as e:
    print(f"Error: {e}")
