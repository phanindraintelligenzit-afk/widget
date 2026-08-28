import re

with open('widget/score.html', 'r', encoding='utf-8') as f:
    content = f.read()

# We'll replace the entire `<td>` containing the `?` or `?` with a properly generated dynamic star system
# We can do this in the `fetchAgents` javascript block

pattern = re.compile(r'<td style="min-width:120px;">.*?</td>', re.DOTALL)

# Let's write the Javascript to render 5 stars using &#9733;
new_td = """<td style="min-width:120px;" onmouseout="resetStars('${a.agent_id}')">
              <span id="star-${a.agent_id}-1" style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="hoverStars('${a.agent_id}', 1)" onclick="submitStar('${a.agent_id}', 1)">&#9733;</span>
              <span id="star-${a.agent_id}-2" style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="hoverStars('${a.agent_id}', 2)" onclick="submitStar('${a.agent_id}', 2)">&#9733;</span>
              <span id="star-${a.agent_id}-3" style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="hoverStars('${a.agent_id}', 3)" onclick="submitStar('${a.agent_id}', 3)">&#9733;</span>
              <span id="star-${a.agent_id}-4" style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="hoverStars('${a.agent_id}', 4)" onclick="submitStar('${a.agent_id}', 4)">&#9733;</span>
              <span id="star-${a.agent_id}-5" style="cursor:pointer; color:#475569; font-size:22px; transition:color 0.2s;" onmouseover="hoverStars('${a.agent_id}', 5)" onclick="submitStar('${a.agent_id}', 5)">&#9733;</span>
              <span id="score-text-${a.agent_id}" style="margin-left: 10px; font-weight: bold; color: var(--accent);"></span>
            </td>"""

content = pattern.sub(new_td, content)

# Inject the helper JS functions right before submitStar
helpers = """
      function hoverStars(agentId, rating) {
          for(let i=1; i<=5; i++) {
              let el = document.getElementById(`star-${agentId}-${i}`);
              if(el) {
                  el.style.color = i <= rating ? '#facc15' : '#475569';
              }
          }
      }
      function resetStars(agentId) {
          for(let i=1; i<=5; i++) {
              let el = document.getElementById(`star-${agentId}-${i}`);
              if(el) el.style.color = '#475569';
          }
      }
"""
content = content.replace('async function submitStar', helpers + '\n      async function submitStar')

# Change submitStar to also show "= 4" (the equal symbol they requested)
content = content.replace('alert("Success! You gave " + agentId + " a " + rating + "-star rating. The DPI-LS Matrix has been updated.");', 
                          'document.getElementById(`score-text-${agentId}`).innerText = "= " + rating;\n                  alert("Success! You gave " + agentId + " a " + rating + "-star rating. The DPI-LS Matrix has been updated.");')


with open('widget/score.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Star UX injected with HTML entities!")
