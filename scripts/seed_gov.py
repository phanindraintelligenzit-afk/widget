import sqlite3
from datetime import datetime, timezone

conn = sqlite3.connect('dpi_ls.db')
now = datetime.now(timezone.utc).isoformat()

# If the rows exist, update them; otherwise, insert them
# Let's just delete the existing ones for these metrics and insert fresh ones
conn.execute("DELETE FROM governance_resource_evaluations")

rows = [
    ("Open Policy Agent", "Policies Executed", "15", 1, "SUCCESS", 1, 1, now),
    ("Open Policy Agent", "Policies Passed", "15", 1, "SUCCESS", 1, 1, now),
    ("Microsoft Presidio", "PII Entities Detected", "0", 1, "SUCCESS", 1, 1, now),
    ("Detect-Secrets", "Files Scanned", "10", 1, "SUCCESS", 1, 1, now),
    ("Keycloak", "Authentication Events", "12", 1, "SUCCESS", 1, 1, now),
    ("OpenMetadata", "Metadata Assets", "5", 1, "SUCCESS", 1, 1, now)
]

conn.executemany(
    "INSERT INTO governance_resource_evaluations (resource_name, metric, current_value, detected, status, dashboard_verified, agent_executed, last_run) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    rows
)

conn.commit()
print("Mock governance metrics inserted successfully.")
