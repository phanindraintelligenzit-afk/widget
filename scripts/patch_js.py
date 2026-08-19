import sys

with open('d:/DPI-LS/widget/widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    js = f.read()

traceability_html = """
    const traceRowHtml = filteredIncidents.map(inc => {
      const matchStatus = (inc.severity === 'CRITICAL' || inc.severity === 'HIGH') ? 'FAIL' : 'PASS';
      const statusColor = matchStatus === 'PASS' ? '#4ade80' : '#ef4444';
      return `
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:10px 14px;color:#94a3b8;text-align:left;font-size:12px;">${escapeHtml(inc.name)}</td>
          <td style="padding:10px 14px;color:#e2e8f0;text-align:left;font-size:12px;font-family:monospace;">${escapeHtml(inc.category)}</td>
          <td style="padding:10px 14px;color:#e2e8f0;text-align:left;font-size:12px;">${escapeHtml(inc.severity)} (${inc.severity_weight})</td>
          <td style="padding:10px 14px;color:#e2e8f0;text-align:left;font-size:12px;">${inc.frequency}</td>
          <td style="padding:10px 14px;color:#e2e8f0;text-align:left;font-size:12px;">${escapeHtml(inc.trace_id || 'N/A')}</td>
          <td style="padding:10px 14px;color:${statusColor};text-align:left;font-size:12px;font-weight:bold;">${matchStatus}</td>
          <td style="padding:10px 14px;color:#facc15;text-align:left;font-size:12px;font-weight:600;">${escapeHtml(inc.source)}</td>
        </tr>
      `;
    }).join('');

    const traceabilityTable = `
      <div class="validation-table-wrapper" style="padding:20px;background:#090d16;font-family:'Courier New',Courier,monospace;border:1px solid #334155;border-radius:${resourceFilter ? '8px' : '0 0 8px 8px'};margin-top:20px;">
        <div style="font-size:13px;font-weight:800;color:#facc15;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">
          &#9654; RISK TRACEABILITY & AUDIT
        </div>
        <table style="width:100%;border-collapse:collapse;">
          <thead>
            <tr style="background:#0f172a;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #334155;">
              <th style="padding:10px 14px;text-align:left;">Incident</th>
              <th style="padding:10px 14px;text-align:left;">Category</th>
              <th style="padding:10px 14px;text-align:left;">Severity (Weight)</th>
              <th style="padding:10px 14px;text-align:left;">Frequency</th>
              <th style="padding:10px 14px;text-align:left;">Trace ID</th>
              <th style="padding:10px 14px;text-align:left;">Status</th>
              <th style="padding:10px 14px;text-align:left;">Source</th>
            </tr>
          </thead>
          <tbody>
            ${traceRowHtml || '<tr><td colspan="7" style="padding:10px 14px;color:#64748b;text-align:center;">No incidents reported.</td></tr>'}
          </tbody>
        </table>
      </div>
    `;
"""

old_return = 'return `\n      ${resourceFilter ? \'\' : `'
if old_return in js:
    js = js.replace(old_return, traceability_html + '\n    ' + old_return)
    
    old_end = '</div>\n    `;\n  }\n\n  function renderCostTableHtml'
    if old_end in js:
        js = js.replace(old_end, '${traceabilityTable}\n      ' + old_end)
        with open('d:/DPI-LS/widget/widget/dpi-ls.js', 'w', encoding='utf-8') as f:
            f.write(js)
        print('Updated dpi-ls.js successfully')
    else:
        print('old_end not found')
else:
    print('old_return not found')
