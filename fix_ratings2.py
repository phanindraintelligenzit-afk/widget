import re

with open('widget/score.html', 'r', encoding='utf-8') as f:
    content = f.read()

new_stars = """<td style="min-width:120px;">
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('', 1)">?</span>
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('', 2)">?</span>
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('', 3)">?</span>
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('', 4)">?</span>
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('', 5)">?</span>
            </td>"""

# robust regex to match the old td block containing edit and delete buttons
pattern = re.compile(r'<td>\s*<button onclick="editAgent\([^>]+>Edit</button>\s*<button onclick="deleteAgent\([^>]+>Delete</button>\s*</td>', re.DOTALL)

content = pattern.sub(new_stars, content)

with open('widget/score.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Stars injected successfully!")
