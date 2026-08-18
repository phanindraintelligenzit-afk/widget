import urllib.request, urllib.parse, json
query = '{resource.service.name="dpi-ls-agent"}'
url = 'http://localhost:3200/api/search?q=' + urllib.parse.quote(query)
try:
    resp = urllib.request.urlopen(url).read().decode()
    data = json.loads(resp)
    traces = data.get('traces', [])
    print(f"Found traces: {len(traces)}")
    for t in traces:
        print(t.get('traceID'), t.get('startTimeUnixNano'))
except Exception as e:
    print(f"Error: {e}")
