import sqlite3
import json
import urllib.request
import datetime
import subprocess

print('=== SQLITE ROWS ===')
conn = sqlite3.connect('storage.db')
cursor = conn.cursor()
cursor.execute("SELECT metric, current_value FROM validation_resource_evaluations WHERE resource_name='Zipkin' OR resource_name='Jaeger' ORDER BY last_run DESC LIMIT 15")
for row in cursor.fetchall():
    print(row)

print('\n=== ZIPKIN REST API ===')
try:
    end_time = datetime.datetime.now()
    end_ts = int(end_time.timestamp() * 1000)
    url = f'http://localhost:9411/api/v2/traces?endTs={end_ts}&lookback=3600000&limit=1'
    data = json.loads(urllib.request.urlopen(url).read().decode())
    print(json.dumps(data, indent=2))
except Exception as e:
    print('Zipkin Error:', e)

print('\n=== JAEGER REST API ===')
try:
    url = 'http://localhost:16686/api/traces?service=chandra-finops-agent&limit=1'
    data = json.loads(urllib.request.urlopen(url).read().decode())
    print(json.dumps(data, indent=2)[:500] + '... (truncated)')
except Exception as e:
    print('Jaeger Error:', e)

print('\n=== GIT DIFF ===')
try:
    print(subprocess.check_output(['git', 'diff', 'examples/test_agent.py', 'dpi_ls/validation_resource_evaluation_service.py']).decode('utf-8'))
except Exception as e:
    print('Git Diff Error:', e)
