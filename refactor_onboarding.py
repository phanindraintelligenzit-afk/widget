import re

with open('widget/onboarding.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Make the page-body wider to accommodate 2 columns
content = content.replace('.page-body { max-width: 800px; }', '.page-body { max-width: 1200px; width: 100%; }')

# Replace the HTML structure
# We wrap the form inside a grid container
form_start = '<form id="onboardingForm">'
grid_start = '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 40px; align-items: start;">\n      <form id="onboardingForm">'
content = content.replace(form_start, grid_start)

# After </form>, close the grid container and inject the preview box
form_end = '</form>'
grid_end = """</form>
      
      <div id="onboarding-preview" style="background:#020617; border-radius:10px; border:2px solid #334155; padding: 24px; font-family:'Courier New',Courier,monospace; display: none; height: 100%; box-sizing: border-box;">
         <h3 style="color:#facc15; margin-top:0; font-size: 16px; border-bottom: 1px solid #334155; padding-bottom: 12px; margin-bottom: 16px; letter-spacing: 1px;">AGENT ONBOARDED</h3>
         <div id="preview-content" style="color: #e2e8f0; font-size: 13px; line-height: 1.8;"></div>
      </div>
      </div>"""
content = content.replace(form_end, grid_end)

# Modify the javascript so instead of appending a raw div to the body, it populates #preview-content
# Find the part in res.ok where it builds the DOM element
pattern = re.compile(r'let div = document\.createElement\(\'div\'\);.*?document\.body\.appendChild\(div\);', re.DOTALL)

new_js = """
            const previewBox = document.getElementById('onboarding-preview');
            const previewContent = document.getElementById('preview-content');
            
            let htmlStr = `<div style="display: flex; flex-direction: column; gap: 10px;">
              <div><strong style="color: #64748b; width: 150px; display: inline-block;">Agent ID:</strong> <span style="color: #38bdf8; font-weight: bold;">${agentIdVal}</span></div>
              <div><strong style="color: #64748b; width: 150px; display: inline-block;">Type:</strong> ${typeVal}</div>
              <div><strong style="color: #64748b; width: 150px; display: inline-block;">Environment:</strong> <span style="color: #4ade80;">${envVal}</span></div>
              <div><strong style="color: #64748b; width: 150px; display: inline-block;">Role:</strong> ${roleVal}</div>
              <div style="border-top: 1px dashed #334155; margin: 10px 0;"></div>
              <div><strong style="color: #64748b; display: block; margin-bottom: 4px;">Business Owner:</strong> ${bizOwnerName} &lt;${bizEmail}&gt;</div>
              <div><strong style="color: #64748b; display: block; margin-bottom: 4px;">Technical Owner:</strong> ${techOwnerName} &lt;${techEmail}&gt;</div>
              <div style="border-top: 1px dashed #334155; margin: 10px 0;"></div>
              <div><strong style="color: #64748b; display: block; margin-bottom: 4px;">Description:</strong> ${descVal}</div>
            </div>`;
            
            previewContent.innerHTML = htmlStr;
            previewBox.style.display = 'block';
"""
content = pattern.sub(new_js, content)

with open('widget/onboarding.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Onboarding layout updated!")
