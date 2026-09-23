with open('widget/DPI-LS_Sales_CEO_Client_Presentation_Final.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace API Interface
if "Telemetry + API + MCP" in content:
    content = content.replace("Telemetry + API + MCP integrations", "API Interface (OpenTelemetry, REST APIs, and MCP integrations)")

# Replace the text of notes without breaking anything
content = content.replace("First, I will explain what DPI-LS is and why we built it. DPI-LS stands for Digital Performance Index", 
                          "DPI-LS is a scoring dashboard that tells us exactly how well, how safely, and how cost-effectively our AI agents are working in the real world.")

content = content.replace("Today AI agents are doing real business work. We need a simple way to know whether they are performing well",
                          "AI is getting cheaper, but companies are spending way more money because they use large AI agents for complex tasks without tracking the costs. BAF models ensure AI is a secure, reliable tool that actually follows company rules and delivers real business value.")

if "<h1>Works with the existing ecosystem</h1>" in content:
    content = content.replace("<h1>Works with the existing ecosystem</h1>", "<h1>Works with the existing ecosystem (API Interface)</h1>")

with open('widget/DPI-LS_Sales_CEO_Client_Presentation_Final.html', 'w', encoding='utf-8') as f:
    f.write(content)
