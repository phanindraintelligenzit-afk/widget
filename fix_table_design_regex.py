import re

with open('widget/score.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Delete Add Agent Button
content = re.sub(r'<button onclick="addAgent\(\)">Add Agent</button>\s*', '', content)

# 2. Add Wrapper and Style Table Header
new_table_html = """<div style="background:#020617;border-radius:10px;border:2px solid #334155;overflow:hidden;font-family:'Courier New',Courier,monospace;margin-top:15px;">
    <table id="agent-table" style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="background:#0f172a;color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:1px;">
          <th style="padding:10px 14px;border:1px solid #1e293b;text-align:left;">Agent</th>
          <th style="padding:10px;border:1px solid #1e293b;text-align:center;">Score</th>
          <th style="padding:10px;border:1px solid #1e293b;text-align:center;">P</th>
          <th style="padding:10px;border:1px solid #1e293b;text-align:center;">Q</th>
          <th style="padding:10px;border:1px solid #1e293b;text-align:center;">E</th>
          <th style="padding:10px;border:1px solid #1e293b;text-align:center;">G</th>
          <th style="padding:10px;border:1px solid #1e293b;text-align:center;">R</th>
          <th style="padding:10px;border:1px solid #1e293b;text-align:center;">V</th>
          <th style="padding:10px;border:1px solid #1e293b;text-align:center;">C</th>
          <th style="padding:10px 14px;border:1px solid #1e293b;text-align:left;">SME Rating</th>
        </tr>
      </thead>
      <tbody id="agent-body"></tbody>
    </table>
</div>"""

content = re.sub(r'<table id="agent-table">.*?<tbody id="agent-body"></tbody>\s*</table>', new_table_html, content, flags=re.DOTALL)

# 3. Style JS Rows
pattern_row = re.compile(r'const row = `<tr>\s*<td>\$\{a\.agent_name\}</td>\s*<td>\$\{a\.score\.toFixed\(2\)\}</td>.*?<td style="min-width:120px;" onmouseout="resetStars\(\'\$\{a\.agent_id\}\'\)">', re.DOTALL)

new_js_row = """const row = `<tr style="border-bottom:1px solid #1e293b; transition:background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.02)'" onmouseout="this.style.background='transparent'">
            <td style="padding:12px 14px; color:#38bdf8; font-weight:700;">${a.agent_name}</td>
            <td style="padding:12px; text-align:center; color:#e2e8f0; font-weight:700;">${a.score.toFixed(2)}</td>
            <td style="padding:12px; text-align:center; color:#4ade80;">${a.metrics.P?.toFixed(2) || '0'}</td>
            <td style="padding:12px; text-align:center; color:#4ade80;">${a.metrics.Q?.toFixed(2) || '0'}</td>
            <td style="padding:12px; text-align:center; color:#4ade80;">${a.metrics.E?.toFixed(2) || '0'}</td>
            <td style="padding:12px; text-align:center; color:#4ade80;">${a.metrics.G?.toFixed(2) || '0'}</td>
            <td style="padding:12px; text-align:center; color:#4ade80;">${a.metrics.R?.toFixed(2) || '0'}</td>
            <td style="padding:12px; text-align:center; color:#4ade80;">${a.metrics.V?.toFixed(2) || '0'}</td>
            <td style="padding:12px; text-align:center; color:#4ade80;">${a.metrics.C?.toFixed(2) || '0'}</td>
            <td style="padding:12px 14px; min-width:140px;" onmouseout="resetStars('${a.agent_id}')">"""

content = pattern_row.sub(new_js_row, content)

with open('widget/score.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Table styled using regex!")
