with open('dpi_ls/governance_resource_evaluation_service.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace(', "Detect-Secrets"', '')
c = c.replace('("Detect-Secrets", True, True, False, True),', '')

c = c.replace('        secrets_incidents = [i for i in incidents if i.source_resource == "Detect-Secrets"]', '')
c = c.replace('''        secrets_freq = sum(i.frequency for i in secrets_incidents)
        has_secrets = secrets_freq > 0 or is_test_env
        metrics_secrets = ["Secrets Found", "Secrets Blocked", "Critical Secrets", "Files Scanned", "Repositories Scanned", "Secret Types", "Scan Duration", "Scan Result", "Compliance Status", "Trace ID", "Timestamp"]
        for m in metrics_secrets:
            save_governance_resource_evaluation(
                self.session, "Detect-Secrets", m,
                detected=has_secrets,
                evidence=f"{secrets_freq} records detected in runtime" if has_secrets else "No incidents",
                current_value=str(secrets_freq),
                status="SUCCESS" if has_secrets else "FAILED",
                dashboard_verified=has_secrets,
                agent_executed=has_secrets
            )
''', '')

c = c.replace('''        "Detect-Secrets": [
            "Secrets Found", "Secrets Blocked", "Critical Secrets",
            "Files Scanned", "Repositories Scanned", "Secret Types",
            "Scan Duration", "Scan Result", "Compliance Status",
            "Trace ID", "Timestamp",
        ],''', '')

c = c.replace('''        "Detect-Secrets": ("detect_secrets",),''', '')

with open('dpi_ls/governance_resource_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.write(c)
