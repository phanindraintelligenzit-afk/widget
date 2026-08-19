import re
import sys

filename = 'widget/resources.html'
try:
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
except FileNotFoundError:
    print(f"Could not find {filename}")
    sys.exit(1)

# Fix 1: RESOURCE_META
if '"LLMGuard":' not in content:
    risk_gov_meta = """
  "LLMGuard": {
    name: 'LLMGuard',
    icon: '🛡️', category: 'Risk & Security',
    description: 'Comprehensive security scanner for LLM prompts and responses.',
    tags: ['Security', 'Prompt Injection', 'Toxicity']
  },
  "TruLens": {
    name: 'TruLens',
    icon: '🔬', category: 'Risk & Security',
    description: 'Evaluation and tracking for LLM apps, focusing on groundedness and relevance.',
    tags: ['Evaluation', 'Relevance', 'Tracking']
  },
  "Rebuff": {
    name: 'Rebuff',
    icon: '🛡️', category: 'Risk & Security',
    description: 'Prompt injection detection and mitigation.',
    tags: ['Security', 'Injection', 'Defense']
  },
  "Open Policy Agent": {
    name: 'Open Policy Agent',
    icon: '📜', category: 'Governance',
    description: 'Cloud-native policy engine that unifies policy enforcement across the stack.',
    tags: ['Policy', 'Rules', 'Runtime']
  },
  "Microsoft Presidio": {
    name: 'Microsoft Presidio',
    icon: '🕵️', category: 'Governance',
    description: 'Data protection and de-identification SDK for text and images.',
    tags: ['PII', 'Anonymization', 'Data Privacy']
  },
  "Detect-Secrets": {
    name: 'Detect-Secrets',
    icon: '🔑', category: 'Governance',
    description: 'Enterprise secrets scanning to prevent credential leakage.',
    tags: ['Secrets', 'Scanning', 'Compliance']
  },"""
    content = content.replace("const RESOURCE_META = {", "const RESOURCE_META = {" + risk_gov_meta)

# Fix 2: loadUrls
content = re.sub(
    r'const \[r1, r2, r3, r4, r5\] = await Promise\.all\(\[\s*fetch\(`\$\{API\}/api/cost-evaluation/urls`\),\s*fetch\(`\$\{API\}/api/validation-evaluation/urls`\),\s*fetch\(`\$\{API\}/api/quality-evaluation/urls`\),\s*fetch\(`\$\{API\}/api/productivity-evaluation/urls`\),\s*fetch\(`\$\{API\}/api/execution-evaluation/urls`\)\s*\]\);',
    r'''const [r1, r2, r3, r4, r5, r6, r7] = await Promise.all([
      fetch(`${API}/api/cost-evaluation/urls`),
      fetch(`${API}/api/validation-evaluation/urls`),
      fetch(`${API}/api/quality-evaluation/urls`),
      fetch(`${API}/api/productivity-evaluation/urls`),
      fetch(`${API}/api/execution-evaluation/urls`),
      fetch(`${API}/api/risk-evaluation/urls`),
      fetch(`${API}/api/governance-evaluation/urls`)
    ]);''', content)

content = re.sub(
    r'processUrls\(r5\)\s*\]\);',
    r'processUrls(r5),\n      processUrls(r6),\n      processUrls(r7)\n    ]);', content)

# Fix 3: runEvaluation and loadData endpoints
for endpoint_type in ['evaluate', 'results']:
    method_str = ", { method: 'POST', headers: { 'Accept': 'application/json' } }" if endpoint_type == 'evaluate' else ", { headers: { Accept: 'application/json' } }"
    
    # We use regex to match the Promise.all fetch block
    search = fr'''const \[r1, r2, r3, r4, r5\] = await Promise\.all\(\[\s*fetch\(`\$\{{API\}}/api/cost-evaluation/{endpoint_type}`.*?\),\s*fetch\(`\$\{{API\}}/api/validation-evaluation/{endpoint_type}`.*?\),\s*fetch\(`\$\{{API\}}/api/quality-evaluation/{endpoint_type}`.*?\),\s*fetch\(`\$\{{API\}}/api/productivity-evaluation/{endpoint_type}`.*?\),\s*fetch\(`\$\{{API\}}/api/execution-evaluation/{endpoint_type}`.*?\)'''
    
    repl = fr'''const [r1, r2, r3, r4, r5, r6, r7] = await Promise.all([
      fetch(`${{API}}/api/cost-evaluation/{endpoint_type}`{method_str}),
      fetch(`${{API}}/api/validation-evaluation/{endpoint_type}`{method_str}),
      fetch(`${{API}}/api/quality-evaluation/{endpoint_type}`{method_str}),
      fetch(`${{API}}/api/productivity-evaluation/{endpoint_type}`{method_str}),
      fetch(`${{API}}/api/execution-evaluation/{endpoint_type}`{method_str}),
      fetch(`${{API}}/api/risk-evaluation/{endpoint_type}`{method_str}),
      fetch(`${{API}}/api/governance-evaluation/{endpoint_type}`{method_str})'''
    
    content = re.sub(search, repl, content, flags=re.DOTALL)

# Fix 4: unpack json
content = re.sub(
    r'const \[costData, valData, qualData, prodData, execData\] = await Promise\.all\(\[r1\.json\(\), r2\.json\(\), r3\.json\(\), r4\.json\(\), r5\.json\(\)\]\);',
    r'const [costData, valData, qualData, prodData, execData, riskData, govData] = await Promise.all([r1.json(), r2.json(), r3.json(), r4.json(), r5.json(), r6.json(), r7.json()]);',
    content)

# Fix 5: resource arrays and concat
content = re.sub(
    r'const execResources = \["Langfuse", "Phoenix", "Traceloop"\];',
    r'const execResources = ["Langfuse", "Phoenix", "Traceloop"];\n    const riskResources = ["LLMGuard", "Rebuff", "TruLens"];\n    const govResources = ["Open Policy Agent", "Microsoft Presidio", "Detect-Secrets"];',
    content)

content = re.sub(
    r'\.\.\.execData\.filter\(r => \[\'Phoenix\', \'Traceloop\'\]\.includes\(r\.resource_name\)\)\s*\];',
    r'''...execData.filter(r => ['Phoenix', 'Traceloop'].includes(r.resource_name)),
      ...riskData.filter(r => riskResources.includes(r.resource_name)),
      ...govData.filter(r => govResources.includes(r.resource_name))
    ];''', content)

# Fix 6: category grouping logic
content = re.sub(
    r"\['Risk & Security'\].includes\(meta.category\) \? 'Risk'",
    r"['Risk & Security'].includes(meta.category) ? 'Risk' : meta.category === 'Governance' ? 'Governance'",
    content
)

# Fix 7: add Risk and Gov render templates
if 'renderGovernanceTableHtml' not in content:
    renderHtml = """
    if (meta.category === 'Governance') {
      if (typeof window.renderGovernanceTableHtml === 'function') {
        const mergedSub = { ...chandraGovSub, ...liveMetrics };
        return window.renderGovernanceTableHtml(mergedSub, settingsObj, chandraGovValue, name);
      }
      return `<div style="padding:15px;color:#64748b;">Governance rendering logic missing.</div>`;
    }
    if (meta.category === 'Risk & Security') {
      if (typeof window.renderRiskTableHtml === 'function') {
        const mergedSub = { ...chandraRiskSub, ...liveMetrics };
        return window.renderRiskTableHtml(mergedSub, settingsObj, chandraRiskValue, name);
      }
      return `<div style="padding:15px;color:#64748b;">Risk rendering logic missing.</div>`;
    }"""
    content = content.replace("if (['OpenTelemetry', 'Grafana Tempo'", renderHtml + "\n    if (['OpenTelemetry', 'Grafana Tempo'")

# Fix 8: setup vars
if 'let chandraRiskSub =' not in content:
    content = content.replace('let chandraRiskValue = 1.0;', 'let chandraRiskValue = 1.0;\nlet chandraRiskSub = {};\nlet chandraGovSub = {};\nlet chandraGovValue = 1.0;')
    content = content.replace('chandraRiskValue = chandra.metrics?.R !== undefined ? chandra.metrics.R : 1.0;', 'chandraRiskValue = chandra.metrics?.R !== undefined ? chandra.metrics.R : 1.0;\n        chandraRiskSub = chandra.sub_metrics?.R || {};\n        chandraGovSub = chandra.sub_metrics?.G || {};\n        chandraGovValue = chandra.metrics?.G !== undefined ? chandra.metrics.G : 1.0;')

with open(filename, 'w', encoding='utf-8') as f:
    f.write(content)
print("done")
