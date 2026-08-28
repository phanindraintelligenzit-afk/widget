with open('widget/score.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Make stars permanently yellow after click and remove fetchAgents() call so the UI state doesn't reset
# In submitStar:
old_success = """if(res.ok) {
                  document.getElementById(`score-text-${agentId}`).innerText = "= " + rating;
                  alert("Success! You gave " + agentId + " a " + rating + "-star rating. The DPI-LS Matrix has been updated.");
                  fetchAgents();
              }"""

new_success = """if(res.ok) {
                  document.getElementById(`score-text-${agentId}`).innerText = "= " + rating;
                  // Remove the onmouseout listener so it stays yellow
                  document.getElementById(`score-text-${agentId}`).parentElement.onmouseout = null;
                  alert("Success! You gave " + agentId + " a " + rating + "-star rating. The DPI-LS Matrix has been updated.");
              }"""

content = content.replace(old_success, new_success)

with open('widget/score.html', 'w', encoding='utf-8') as f:
    f.write(content)
