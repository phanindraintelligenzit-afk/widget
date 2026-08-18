import sqlite3
import json

try:
    conn = sqlite3.connect('dpi_ls.db')
    c = conn.cursor()
    c.execute("SELECT sub_metrics FROM score_history ORDER BY computed_at DESC LIMIT 1")
    row = c.fetchone()
    if row:
        data = json.loads(row[0])
        print("=== BACKEND SQLITE DATABASE (RAGAS METRICS) ===")
        # Print only the Ragas metrics for clarity
        for key, details in data.get("Q", {}).items():
            if details.get("src") == "Ragas":
                print(f"Metric: {key}")
                print(f"  Value: {details.get('val')}")
                print(f"  Source: {details.get('src')}")
                print(f"  Status: {details.get('status')}")
                print("-" * 40)
    else:
        print("No records found in database.")
except Exception as e:
    print(f"Error reading database: {e}")