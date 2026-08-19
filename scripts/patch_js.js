const fs = require('fs');
let text = fs.readFileSync('widget/dpi-ls.js', 'utf8');

text = text.replace(
  '"G = 1 − (policy_violations / total_actions)"',
  '"G = Validated Governance Controls / Required Governance Controls"'
);

const renderGov = `
  function renderGovernanceTableHtml(sub, settings, value, resourceFilter) {
    if (!sub) return \`<div style="padding:15px;color:#64748b;">No Governance telemetry available.</div>\`;

    const gScoreVal = value || 0;
    const finalWeightedVal = (gScoreVal * (settings?.weights?.G || 0.20)).toFixed(2);
    const required = sub["Required Controls"] || 0;
    const validated = sub["Validated Controls"] || 0;

    const resources = sub.runtime_resources || {};
    let rowHtml = "";

    const opa = resources["Open Policy Agent"] || {};
    const presidio = resources["Microsoft Presidio"] || {};
    const secrets = resources["Detect-Secrets"] || {};

    if (!resourceFilter || resourceFilter === "Open Policy Agent") {
      rowHtml += \`
        <tr style="background:#020617;border-bottom:1px solid #1e293b;">
          <td style="padding:8px 14px;color:#38bdf8;font-weight:600;">Open Policy Agent</td>
          <td style="padding:8px 14px;color:#e2e8f0;">Policies Executed: \${opa["Policies Executed"] || 0}</td>
          <td style="padding:8px 14px;color:#e2e8f0;">Failed: \${opa["Policies Failed"] || 0}</td>
          <td style="padding:8px 14px;color:#e2e8f0;">Denied: \${opa["Denied Requests"] || 0}</td>
          <td style="padding:8px 14px;color:#4ade80;">Success</td>
          <td style="padding:8px 14px;color:#e2e8f0;">SUCCESS</td>
          <td style="padding:8px 14px;color:#94a3b8;">Runtime Telemetry</td>
        </tr>
      \`;
    }

    if (!resourceFilter || resourceFilter === "Microsoft Presidio") {
      rowHtml += \`
        <tr style="background:#020617;border-bottom:1px solid #1e293b;">
          <td style="padding:8px 14px;color:#38bdf8;font-weight:600;">Microsoft Presidio</td>
          <td style="padding:8px 14px;color:#e2e8f0;">PII Entities Detected: \${presidio["PII Entities Detected"] || 0}</td>
          <td style="padding:8px 14px;color:#e2e8f0;">Masked: \${presidio["Masked Entities"] || 0}</td>
          <td style="padding:8px 14px;color:#e2e8f0;">Failures: \${presidio["Mask Failure"] || 0}</td>
          <td style="padding:8px 14px;color:#4ade80;">Success</td>
          <td style="padding:8px 14px;color:#e2e8f0;">SUCCESS</td>
          <td style="padding:8px 14px;color:#94a3b8;">Runtime Telemetry</td>
        </tr>
      \`;
    }

    if (!resourceFilter || resourceFilter === "Detect-Secrets") {
      rowHtml += \`
        <tr style="background:#020617;border-bottom:1px solid #1e293b;">
          <td style="padding:8px 14px;color:#38bdf8;font-weight:600;">Detect-Secrets</td>
          <td style="padding:8px 14px;color:#e2e8f0;">Secrets Found: \${secrets["Secrets Found"] || 0}</td>
          <td style="padding:8px 14px;color:#e2e8f0;">Blocked: \${secrets["Secrets Blocked"] || 0}</td>
          <td style="padding:8px 14px;color:#e2e8f0;">Critical: \${secrets["Critical Secrets"] || 0}</td>
          <td style="padding:8px 14px;color:#4ade80;">Success</td>
          <td style="padding:8px 14px;color:#e2e8f0;">SUCCESS</td>
          <td style="padding:8px 14px;color:#94a3b8;">Runtime Telemetry</td>
        </tr>
      \`;
    }

    let incRows = "";
    if (sub.incidents && sub.incidents.length > 0) {
      incRows = sub.incidents
        .filter(inc => !resourceFilter || inc.source === resourceFilter)
        .map(inc => \`
          <tr style="background:#1e1b4b;border-bottom:1px solid #312e81;">
            <td style="padding:8px 14px;color:#f472b6;">Incident: \${escapeHtml(inc.name)}</td>
            <td style="padding:8px 14px;color:#e2e8f0;">\${escapeHtml(inc.source)}</td>
            <td style="padding:8px 14px;color:#cbd5e1;">\${escapeHtml(inc.category)}</td>
            <td style="padding:8px 14px;color:#f87171;">Severity: \${inc.severity} (\${inc.severity_weight})</td>
            <td style="padding:8px 14px;color:#fbbf24;">Freq: \${inc.frequency}</td>
            <td style="padding:8px 14px;color:#ef4444;font-weight:bold;">IMPACT</td>
            <td style="padding:8px 14px;color:#94a3b8;font-size:10px;">Trace: \${escapeHtml(inc.trace_id || 'N/A')}</td>
          </tr>
        \`).join("");
    }

    return \`
      <div style="padding:20px;background:#020617;font-family:'Courier New',Courier,monospace;">
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px;">
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Raw Value</div>
            <div style="color:#38bdf8;font-size:18px;font-weight:800;">\${gScoreVal.toFixed(4)}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Weighted (×20%)</div>
            <div style="color:#4ade80;font-size:18px;font-weight:800;">\${finalWeightedVal}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Formula</div>
            <div style="color:#e2e8f0;font-size:11px;line-height:1.4;">Governance = Validated Controls / Required Controls</div>
          </div>
        </div>
        <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;">
          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Governance Calculation</div>
          <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
            <div>Required Controls : \${required}</div>
            <div>Validated Controls : \${validated}</div>
            <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Governance Score : \${validated} / \${required} = \${gScoreVal.toFixed(3)}</div>
          </div>
        </div>
      </div>

      <div class="governance-table-wrapper" style="padding:20px;background:#090d16;font-family:'Courier New',Courier,monospace;border:1px solid #334155;border-radius:\${resourceFilter ? '8px' : '0 0 8px 8px'};">
        <div style="font-size:13px;font-weight:800;color:#facc15;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">
          ▶ \${resourceFilter ? resourceFilter.toUpperCase() + ' ' : ''}GOVERNANCE TRACEABILITY & AUDIT
        </div>
        <table style="width:100%;border-collapse:collapse;text-align:left;">
          <thead>
            <tr style="background:#0f172a;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #334155;">
              <th style="padding:10px 14px;text-align:left;">Metric / Incident</th>
              <th style="padding:10px 14px;text-align:left;">Resource / Detail 1</th>
              <th style="padding:10px 14px;text-align:left;">Detail 2</th>
              <th style="padding:10px 14px;text-align:left;">Detail 3</th>
              <th style="padding:10px 14px;text-align:left;">Impact</th>
              <th style="padding:10px 14px;text-align:left;">Status</th>
              <th style="padding:10px 14px;text-align:left;">Source</th>
            </tr>
          </thead>
          <tbody>
            \${rowHtml || \`<tr><td colspan="7" style="padding:15px;color:#64748b;text-align:center;">No Governance telemetry mapped.</td></tr>\`}
            \${incRows}
          </tbody>
        </table>
      </div>
    \`;
  }
`;

if (!text.includes('function renderGovernanceTableHtml')) {
  text = text.replace('function renderValidationTableHtml', renderGov + '\n  function renderValidationTableHtml');
  text = text.replace('if (key === "Q") {', 'if (key === "G") {\n      return renderGovernanceTableHtml(sub, settings, value);\n    }\n    if (key === "Q") {');
  
  // Now add resource filtering logic in resourceDetail if needed for G
  // "Risk" handles LLMGuard etc. Governance handles OPA, Presidio, Detect-Secrets
  fs.writeFileSync('widget/dpi-ls.js', text);
  console.log('Patched dpi-ls.js for Governance successfully');
} else {
  console.log('Governance rendering already present in dpi-ls.js');
}
