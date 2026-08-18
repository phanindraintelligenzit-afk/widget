import sqlite3
import json

try:
    print('=== SQLITE VALIDATION ROWS (dpi_ls.db) ===')
    conn = sqlite3.connect('dpi_ls.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM validation_resource_evaluations WHERE resource_name IN ('Zipkin', 'Jaeger', 'DeepEval') ORDER BY last_run DESC LIMIT 25")
    rows = cursor.fetchall()
    
    zipkin_metrics = []
    for row in rows:
        metric = row['metric']
        if row['resource_name'] == 'Zipkin':
            zipkin_metrics.append((metric, row['current_value']))
        if metric in ['trace_id', 'latency', 'span_timeline', 'execution_timeline', 'span_count']:
            print(f"[{row['resource_name']}] {metric}: {row['current_value']}")
        if row['resource_name'] == 'DeepEval' and ('score' in metric.lower() or 'metric' in metric.lower()):
            print(f"[{row['resource_name']}] {metric}: {row['current_value']}")
    
    print("\n[Zipkin Full Metrics Dump]")
    for m, v in zipkin_metrics:
        print(f"{m}: {v}")
except Exception as e:
    print(f"SQLite Error: {e}")
