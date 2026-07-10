import sqlite3
import json
import urllib.request
import datetime

def fetch_json(url):
    try:
        req = urllib.request.Request(url)
        return json.loads(urllib.request.urlopen(req).read().decode())
    except Exception as e:
        return f"Error: {e}"

print("="*50)
print("STEP 3: JAEGER REST API")
jaeger_url = 'http://localhost:16686/api/traces?service=chandra-finops-agent&limit=1'
jaeger_data = fetch_json(jaeger_url)
if isinstance(jaeger_data, dict) and 'data' in jaeger_data and len(jaeger_data['data']) > 0:
    trace = jaeger_data['data'][0]
    print(f"Trace exists: {trace.get('traceID')}")
    print(f"Spans exist: {len(trace.get('spans', []))} spans")
    print(f"Duration exists: {trace['spans'][0].get('duration')} microseconds")
else:
    print(f"Jaeger returned empty or error: {jaeger_data}")

print("="*50)
print("STEP 4: ZIPKIN REST API")
end_time = datetime.datetime.now()
end_ts = int(end_time.timestamp() * 1000)
zipkin_url = f'http://localhost:9411/api/v2/traces?endTs={end_ts}&lookback=3600000&limit=1'
zipkin_data = fetch_json(zipkin_url)
if isinstance(zipkin_data, list) and len(zipkin_data) > 0:
    spans = zipkin_data[0]
    print(f"Trace exists: {spans[0].get('traceId')}")
    print(f"Spans exist: {len(spans)} spans")
    print(f"Duration exists: {spans[0].get('duration')} microseconds")
else:
    print(f"Zipkin returned empty or error: {zipkin_data}")

print("="*50)
print("STEP 5: VALIDATION BACKEND API")
backend_url = 'http://127.0.0.1:8000/api/validation-evaluation/registry'
backend_data = fetch_json(backend_url)
if isinstance(backend_data, list):
    for resource in backend_data:
        print(f"Resource: {resource.get('name')} | Status: {resource.get('status')}")
else:
    print(f"Backend API returned: {backend_data}")

print("="*50)
print("STEP 6: SQLITE VALIDATION ROWS")
try:
    conn = sqlite3.connect('storage.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM validation_resource_evaluations WHERE resource_name IN ('Zipkin', 'Jaeger', 'DeepEval') ORDER BY last_run DESC LIMIT 15")
    rows = cursor.fetchall()
    
    for row in rows:
        metric = row['metric']
        if metric in ['trace_id', 'latency', 'span_timeline', 'execution_timeline']:
            print(f"[{row['resource_name']}] {metric}: {row['current_value']}")
        if row['resource_name'] == 'DeepEval' and 'Score' in metric:
            print(f"[{row['resource_name']}] {metric}: {row['current_value']}")
except Exception as e:
    print(f"SQLite Error: {e}")
print("="*50)
