import urllib.request
import json
from datetime import datetime

url = "http://127.0.0.1:8000/api/governance-evaluation/push"

incidents = [
    {
        "agent_id": "chandra-finops",
        "source_resource": "Open Policy Agent",
        "name": "S3 Bucket Public Access violation",
        "category": "Policy",
        "severity": "HIGH",
        "severity_weight": 8.0,
        "frequency": 2,
        "risk_contribution": 16.0
    },
    {
        "agent_id": "chandra-finops",
        "source_resource": "Microsoft Presidio",
        "name": "SSN Masking Failure",
        "category": "PII",
        "severity": "CRITICAL",
        "severity_weight": 10.0,
        "frequency": 1,
        "risk_contribution": 10.0
    },
    {
        "agent_id": "chandra-finops",
        "source_resource": "Detect-Secrets",
        "name": "AWS Access Key leaked",
        "category": "Secrets",
        "severity": "CRITICAL",
        "severity_weight": 10.0,
        "frequency": 1,
        "risk_contribution": 10.0
    }
]

for inc in incidents:
    req = urllib.request.Request(url, method="POST")
    req.add_header("Content-Type", "application/json")
    data = json.dumps(inc).encode("utf-8")
    try:
        response = urllib.request.urlopen(req, data=data)
        print("Pushed:", response.read().decode())
    except Exception as e:
        print("Error pushing:", e)
