import re

with open('widget/score.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace Actions with SME Rating
content = content.replace('<th>Actions</th>', '<th>SME Rating</th>')

# Replace the buttons
old_buttons = """<td>
              <button onclick="editAgent('')">Edit</button>
              <button onclick="deleteAgent('')">Delete</button>
            </td>"""

new_stars = """<td style="min-width:120px;">
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('', 1)">?</span>
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('', 2)">?</span>
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('', 3)">?</span>
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('', 4)">?</span>
              <span style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="this.style.color='#facc15'" onmouseout="this.style.color='#475569'" onclick="submitStar('', 5)">?</span>
            </td>"""

content = content.replace(old_buttons, new_stars)

# Replace the old JS functions with submitStar
old_funcs_pattern = re.compile(r'async function deleteAgent.*?editAgent\(id\) \{ alert\(\'Not implemented\'\); \}', re.DOTALL)

new_func = """async function submitStar(agentId, rating) {
          const payload = {
              agent_id: agentId,
              manager_id: "sme@intelligenzit.com",
              rating: rating,
              feedback: "Direct star rating via Rating Page"
          };
          
          try {
              const res = await fetch('/api/ratings', {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify(payload)
              });
              
              if(res.ok) {
                  alert("Success! You gave " + agentId + " a " + rating + "-star rating. The DPI-LS Matrix has been updated.");
                  fetchAgents();
              }
          } catch(e) {
              console.error(e);
              alert("Error submitting rating.");
          }
      }"""

content = old_funcs_pattern.sub(new_func, content)

with open('widget/score.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Score page updated with 5-star rating system!")
