import sqlite3
from datetime import datetime, timezone

conn = sqlite3.connect('dpi_ls.db')
now = datetime.now(timezone.utc).isoformat()

conn.execute("DELETE FROM governance_incidents")

rows = [
    ("gov_mock_1", "OPA Policy Violation", "Policy", "Open Policy Agent", "chandra-finops", "HIGH", 3.0, 1, 0.8, "N/A", "N/A", "N/A", now, "NORMALIZED"),
    ("gov_mock_2", "Presidio PII Detection", "Data Privacy", "Microsoft Presidio", "chandra-finops", "HIGH", 4.0, 1, 0.9, "N/A", "N/A", "N/A", now, "NORMALIZED")
]

conn.executemany(
    "INSERT INTO governance_incidents (incident_id, name, category, source_resource, agent_id, severity, severity_weight, frequency, risk_contribution, trace_id, span_id, correlation_id, timestamp, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    rows
)

conn.commit()
print("Mock governance incidents inserted successfully.")
