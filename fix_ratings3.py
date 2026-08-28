import re

with open('widget/score.html', 'r', encoding='utf-8') as f:
    content = f.read()

new_stars = """<td style="min-width:120px;">
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('${a.agent_id}', 1)">?</span>
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('${a.agent_id}', 2)">?</span>
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('${a.agent_id}', 3)">?</span>
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('${a.agent_id}', 4)">?</span>
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('${a.agent_id}', 5)">?</span>
            </td>"""

# Fix the broken empty ones
pattern = re.compile(r'<td style="min-width:120px;">\s*<span.*?</td>', re.DOTALL)
content = pattern.sub(new_stars, content)

with open('widget/score.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Stars fixed correctly!")
