import yaml
import os

POLICY_DIR = r"d:\Projects\widget\widget\dpi_ls\policies"
os.makedirs(POLICY_DIR, exist_ok=True)

def generate_rules(count, prefix, categories, actions):
    rules = []
    for i in range(1, count + 1):
        rule = {
            "id": f"{prefix}-{i:03d}",
            "name": f"{prefix.replace('_', ' ').title()} Rule {i}",
            "description": f"Ensures compliance with {prefix} standards for action {i}.",
            "severity": "high" if i % 5 == 0 else ("medium" if i % 2 == 0 else "low"),
            "category": categories[i % len(categories)],
            "action": actions[i % len(actions)] + str(i),
            "conditions": {
                "all": [
                    {"field": "context", "operator": "exists"},
                    {"field": "user_id", "operator": "not_null"}
                ]
            }
        }
        rules.append(rule)
    return {"version": "1.0", "policies": rules}

files = {
    "enterprise_sox_gdpr_soc2.yaml": (210, "enterprise_compliance", ["sox", "gdpr", "soc2"], ["dataAccessed", "reportGenerated", "recordDeleted"]),
    "sap_hr_compliance.yaml": (160, "sap_hr", ["payroll", "recruitment", "benefits"], ["employeeSalaryModified", "candidateAutoRejected", "bonusAllocated"]),
    "healthcare_hipaa.yaml": (130, "healthcare", ["phi", "ehr", "billing"], ["patientRecordAccessed", "prescriptionModified", "billingExported"]),
    "pci_dss.yaml": (130, "pci_dss", ["card_data", "network", "access"], ["highValuePaymentSent", "cardDetailsStored", "transactionReversed"]),
    "ai_ml_governance.yaml": (110, "ai_ml", ["bias", "explainability", "drift"], ["modelDeployed", "trainingDataAccessed", "predictionOverridden"]),
    "legal_contracts.yaml": (90, "legal", ["nda", "vendor", "employment"], ["contractSigned", "clauseModified", "addendumCreated"]),
    "it_security_iso27001.yaml": (130, "it_sec", ["access", "encryption", "audit"], ["firewallPortOpened", "apiKeyCreatedWithNoExpiry", "adminLoginAttempt"]),
    "cloud_infrastructure.yaml": (130, "cloud", ["iam", "compute", "storage"], ["productionDeploymentPerformed", "s3BucketMadePublic", "instanceTerminated"])
}

for filename, (count, prefix, cats, acts) in files.items():
    path = os.path.join(POLICY_DIR, filename)
    data = generate_rules(count, prefix, cats, acts)
    with open(path, "w") as f:
        yaml.dump(data, f, sort_keys=False)

print("Generated all policies.")
