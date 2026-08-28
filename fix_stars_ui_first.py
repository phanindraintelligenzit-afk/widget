with open('widget/score.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_func = """      async function submitStar(agentId, rating) {
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
                  document.getElementById(`score-text-${agentId}`).innerText = "= " + rating;
                  // Remove the onmouseout listener so it stays yellow
                  document.getElementById(`score-text-${agentId}`).parentElement.onmouseout = null;
                  alert("Success! You gave " + agentId + " a " + rating + "-star rating. The DPI-LS Matrix has been updated.");
              }
          } catch(e) {
              console.error(e);
              alert("Error submitting rating.");
          }
      }"""

new_func = """      async function submitStar(agentId, rating) {
          // Immediately update the UI for instant feedback
          const textEl = document.getElementById(`score-text-${agentId}`);
          if(textEl) {
              textEl.innerText = "= " + rating;
              textEl.parentElement.onmouseout = null; // freeze the stars on mouse out
          }
          hoverStars(agentId, rating); // Force the visual highlight

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
                  // alert("Success! You gave " + agentId + " a " + rating + "-star rating.");
              }
          } catch(e) {
              console.error("Backend error:", e);
          }
      }"""

content = content.replace(old_func, new_func)

with open('widget/score.html', 'w', encoding='utf-8') as f:
    f.write(content)
