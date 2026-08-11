import re

def fix_dpi_ls():
    with open('d:/DPI-LS/widget/widget/dpi-ls.js', 'r', encoding='utf-8') as f:
        js = f.read()

    start_str = "  function renderRiskTableHtml(sub, settings, value, resourceFilter) {"
    start_idx = js.find(start_str)
    
    # find the end of renderRiskTableHtml (next function is renderQualityTableHtml)
    end_str = "  function renderQualityTableHtml(sub, settings, value, resourceFilter) {"
    end_idx = js.find(end_str)
    
    if start_idx == -1 or end_idx == -1:
        print("Could not find start/end")
        return

    original_style = """  function renderRiskTableHtml(sub, settings, value, resourceFilter) {
    if (!sub) return `<div style="padding:15px;color:#64748b;">No Risk telemetry available.</div>`;

    const resources = sub.runtime_resources || {};
    // Extract incidents
    const incidents = resources["Risk Incidents"] || {};

    let rScoreVal = value !== undefined && value !== null ? value : 1.0;
    
    // Map incidents to metrics map
    const metricsMap = {};
    metricsMap["Risk_Score"] = { val: rScoreVal, calc: rScoreVal, disp: rScoreVal, formula: "1 - min(1, Σ(Freq * Sev))", src: "Calculation", resource: "Calculation", dec: 4 };

    for (const [key, details] of Object.entries(incidents)) {
        if (key === "Total Incidents") continue;
        metricsMap[key] = {
            val: details.occurrences,
            calc: details.occurrences,
            disp: details.occurrences,
            formula: "Incident Frequency",
            src: "Runtime Telemetry",
            resource: details.source || "Unknown",
            dec: 0
        };
    }

    const fmt = (val, dec = 3) => {
      if (val === null || val === undefined) return "Unavailable";
      if (typeof val === 'number') {
        return val.toFixed(dec);
      }
      const num = parseFloat(val);
      return isNaN(num) ? val : num.toFixed(dec);
    };

    let entries = Object.entries(metricsMap);
    if (resourceFilter) {
      entries = entries.filter(([key, r]) => r.resource === resourceFilter || (r.resources && r.resources.includes(resourceFilter)));
    }
    entries = entries.filter(([_, m]) => m.val !== "Unavailable");

    const rowHtml = entries.map(([key, r]) => {
      const displayKey = key.replace(/_/g, ' ');
      
      const stColor = r.val > 0 && key !== "Risk_Score" ? "#ef4444" : "#10b981";
      const statusHtml = `<div style="display:inline-block;padding:2px 8px;border-radius:4px;background:${stColor}20;color:${stColor};font-size:11px;font-weight:700;">ACTIVE</div>`;
      
      return `
        <tr style="border-bottom:1px solid #1e293b;transition:background 0.2s;" onmouseover="this.style.background='#1e293b'" onmouseout="this.style.background='transparent'">
          <td style="padding:8px 12px;color:#94a3b8;font-size:12px;white-space:nowrap;">${displayKey}</td>
          <td style="padding:8px 12px;color:#38bdf8;font-size:12px;font-family:monospace;">${fmt(r.val, r.dec)}</td>
          <td style="padding:8px 12px;color:#facc15;font-size:11px;">${r.formula}</td>
          <td style="padding:8px 12px;color:#64748b;font-size:11px;">${r.src}</td>
          <td style="padding:8px 12px;color:#94a3b8;font-size:11px;">${r.resource}</td>
          <td style="padding:8px 12px;text-align:right;">${statusHtml}</td>
        </tr>
      `;
    }).join("");

    const traceabilityTable = `
      <div class="validation-table-wrapper" style="padding:20px;background:#090d16;font-family:'Courier New',Courier,monospace;border:1px solid #334155;border-radius:${resourceFilter ? '8px' : '0 0 8px 8px'};margin-top:20px;">
        <h3 style="color:#facc15;font-size:14px;margin-bottom:15px;display:flex;align-items:center;gap:8px;">
          <span>► RISK TRACEABILITY & AUDIT</span>
          <span style="background:rgba(250,204,21,0.1);padding:2px 8px;border-radius:12px;font-size:10px;">VERIFIED</span>
        </h3>
        <div style="overflow-x:auto;">
          <table style="width:100%;border-collapse:collapse;text-align:left;">
            <thead>
              <tr style="border-bottom:1px solid #334155;color:#64748b;font-size:11px;">
                <th style="padding:8px 12px;font-weight:600;">METRIC</th>
                <th style="padding:8px 12px;font-weight:600;">VALUE</th>
                <th style="padding:8px 12px;font-weight:600;">FORMULA</th>
                <th style="padding:8px 12px;font-weight:600;">SOURCE</th>
                <th style="padding:8px 12px;font-weight:600;">RESOURCE</th>
                <th style="padding:8px 12px;font-weight:600;text-align:right;">STATUS</th>
              </tr>
            </thead>
            <tbody>
              ${rowHtml}
            </tbody>
          </table>
        </div>
      </div>
    `;

    return traceabilityTable;
}
"""
    new_js = js[:start_idx] + original_style + js[end_idx:]
    with open('d:/DPI-LS/widget/widget/dpi-ls.js', 'w', encoding='utf-8') as f:
        f.write(new_js)
    print("Fixed dpi-ls.js")

fix_dpi_ls()
