import re

with open('DPI-LS_Sales_CEO_Client_Presentation (1).html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the Observability Gap / Telemetry slide (if it exists) to "API Interface"
if "Telemetry + API + MCP" in content:
    content = content.replace("Telemetry + API + MCP", "API Interface (OpenTelemetry, REST APIs, and MCP integrations)")

# 2. Update the "Measure, Decide, Improve" slide to "ACTIONABLE INTELLIGENCE"
if "MEASURE &#8594; DECIDE" in content:
    content = content.replace("<h1>Measure", "<h1>Actionable Intelligence: Measure")
if "Measure &#8594; Decide" in content:
    content = content.replace("Measure &#8594; Decide", "Actionable Intelligence: Measure &#8594; Decide")

# 3. Add the speaker notes about PI vs DPI-LS.
# Let's just find the Dashboard slide notes and append the clarification.
notes_pattern = r'(<div class="notes">)(.*?)(</div>)'
def replace_notes(match):
    note = match.group(2)
    if "dashboard" in note.lower() and "score" in note.lower():
        note += " Note: PI is the Target Benchmark. DPI-LS is the Actual Evaluated Score."
    return match.group(1) + note + match.group(3)

content = re.sub(notes_pattern, replace_notes, content)

# 4. Check if we need to replace the image of the dashboard
if "dash" in content:
    pass # If it's an image we might not be able to easily swap it without the new image name, but let's see.

with open('DPI-LS_Sales_CEO_Client_Presentation_Final.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated HTML!")
