const fs = require('fs');
let html = fs.readFileSync('widget/resources.html', 'utf8');

// 1. variables
html = html.replace('let chandraRiskValue = 1.0;', 'let chandraRiskValue = 1.0;\nlet chandraGovSub = {};\nlet chandraGovValue = 1.0;');
html = html.replace('chandraRiskValue = chandra.metrics?.R !== undefined ? chandra.metrics.R : 1.0;', 'chandraRiskValue = chandra.metrics?.R !== undefined ? chandra.metrics.R : 1.0;\n        chandraGovSub = chandra.sub_metrics?.G || {};\n        chandraGovValue = chandra.metrics?.G !== undefined ? chandra.metrics.G : 1.0;');

// 2. URLs
html = html.replace(
  'fetch(`${API}/api/risk-evaluation/urls`)',
  'fetch(`${API}/api/risk-evaluation/urls`),\n      fetch(`${API}/api/governance-evaluation/urls`)'
);

let loadUrlsFn = html.substring(html.indexOf('async function loadUrls() {'), html.indexOf('} catch (e) {', html.indexOf('async function loadUrls() {')));
let newLoadUrlsFn = loadUrlsFn
  .replace('fetch(`${API}/api/risk-evaluation/urls`)', 'fetch(`${API}/api/risk-evaluation/urls`),\n      fetch(`${API}/api/governance-evaluation/urls`)')
  .replace('const [u1, u2, u3, u4, u5, u6] = await Promise.all', 'const [u1, u2, u3, u4, u5, u6, u7] = await Promise.all')
  .replace('const [cUrls, vUrls, qUrls, pUrls, eUrls, rUrls] = await Promise.all([u1.json(), u2.json(), u3.json(), u4.json(), u5.json(), u6.json()]);', 'const [cUrls, vUrls, qUrls, pUrls, eUrls, rUrls, gUrls] = await Promise.all([u1.json(), u2.json(), u3.json(), u4.json(), u5.json(), u6.json(), u7.json()]);')
  .replace('...rUrls', '...rUrls,\n        ...gUrls');
if (loadUrlsFn !== newLoadUrlsFn && loadUrlsFn.length > 10) {
    html = html.replace(loadUrlsFn, newLoadUrlsFn);
}


// 3. Resource definitions
const govResources = `
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
  },`;
html = html.replace('const RESOURCE_META = {', 'const RESOURCE_META = {' + govResources);

// 4. Render Table
const renderGovTable = `
    if (meta.category === 'Governance') {
      if (typeof window.renderGovernanceTableHtml === 'function') {
        const mergedSub = { ...chandraGovSub, ...liveMetrics };
        return window.renderGovernanceTableHtml(mergedSub, settingsObj, chandraGovValue, name);
      }
      return \`<div style="padding:15px;color:#64748b;">Governance rendering logic missing.</div>\`;
    }
`;
html = html.replace("if (typeof window.renderRiskTableHtml === 'function') {", renderGovTable + "\n    if (typeof window.renderRiskTableHtml === 'function') {");

// 5. Dimension grouping logic
html = html.replace(
  "['Risk & Security'].includes(meta.category) ? 'Risk'",
  "['Risk & Security'].includes(meta.category) ? 'Risk' : meta.category === 'Governance' ? 'Governance'"
);

// 6. Run evaluations
let runEvalsFn = html.substring(html.indexOf('async function runEvaluations() {'), html.indexOf('} catch (e) {', html.indexOf('async function runEvaluations() {')));
let newRunEvalsFn = runEvalsFn
  .replace("fetch(`${API}/api/risk-evaluation/evaluate`, { method: 'POST', headers: { 'Accept': 'application/json' } })", "fetch(`${API}/api/risk-evaluation/evaluate`, { method: 'POST', headers: { 'Accept': 'application/json' } }),\n      fetch(`${API}/api/governance-evaluation/evaluate`, { method: 'POST', headers: { 'Accept': 'application/json' } })")
  .replace("const [r1, r2, r3, r4, r5, r6] = await Promise.all", "const [r1, r2, r3, r4, r5, r6, r7] = await Promise.all")
  .replace("const [costData, valData, qualData, prodData, execData, riskData] = await Promise.all([r1.json(), r2.json(), r3.json(), r4.json(), r5.json(), r6.json()]);", "const [costData, valData, qualData, prodData, execData, riskData, govData] = await Promise.all([r1.json(), r2.json(), r3.json(), r4.json(), r5.json(), r6.json(), r7.json()]);")
  .replace('const riskResources = ["LLMGuard", "Rebuff", "TruLens"];', 'const riskResources = ["LLMGuard", "Rebuff", "TruLens"];\n    const govResources = ["Open Policy Agent", "Microsoft Presidio", "Detect-Secrets"];')
  .replace("...riskData.filter(r => riskResources.includes(r.resource_name))", "...riskData.filter(r => riskResources.includes(r.resource_name)),\n      ...govData.filter(r => govResources.includes(r.resource_name))");
if (runEvalsFn !== newRunEvalsFn && runEvalsFn.length > 10) {
    html = html.replace(runEvalsFn, newRunEvalsFn);
}


// 7. Load Evaluations
let loadEvalsFn = html.substring(html.indexOf('async function loadEvaluations() {'), html.indexOf('} catch (e) {', html.indexOf('async function loadEvaluations() {')));
let newLoadEvalsFn = loadEvalsFn
  .replace("fetch(`${API}/api/risk-evaluation/results`, { headers: { Accept: 'application/json' } })", "fetch(`${API}/api/risk-evaluation/results`, { headers: { Accept: 'application/json' } }),\n      fetch(`${API}/api/governance-evaluation/results`, { headers: { Accept: 'application/json' } })")
  .replace("const [r1, r2, r3, r4, r5, r6] = await Promise.all", "const [r1, r2, r3, r4, r5, r6, r7] = await Promise.all")
  .replace("const [costData, valData, qualData, prodData, execData, riskData] = await Promise.all([r1.json(), r2.json(), r3.json(), r4.json(), r5.json(), r6.json()]);", "const [costData, valData, qualData, prodData, execData, riskData, govData] = await Promise.all([r1.json(), r2.json(), r3.json(), r4.json(), r5.json(), r6.json(), r7.json()]);")
  .replace('const riskResources = ["LLMGuard", "Rebuff", "TruLens"];', 'const riskResources = ["LLMGuard", "Rebuff", "TruLens"];\n    const govResources = ["Open Policy Agent", "Microsoft Presidio", "Detect-Secrets"];')
  .replace("...riskData.filter(r => riskResources.includes(r.resource_name))", "...riskData.filter(r => riskResources.includes(r.resource_name)),\n      ...govData.filter(r => govResources.includes(r.resource_name))");
if (loadEvalsFn !== newLoadEvalsFn && loadEvalsFn.length > 10) {
    html = html.replace(loadEvalsFn, newLoadEvalsFn);
}


fs.writeFileSync('widget/resources.html', html);
console.log('Successfully patched resources.html for Governance!');
