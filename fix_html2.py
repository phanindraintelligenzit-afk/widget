import re

with open('DPI-LS_Sales_CEO_Client_Presentation (1).html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Speaker Notes to match the "Human sentences"
# Slide 1 (What is DPI-LS)
content = re.sub(
    r'(<div class="notes">)(.*?)(</div><div class="num">01 / 10</div>)',
    r'\1DPI-LS is a scoring dashboard that tells us exactly how well, how safely, and how cost-effectively our AI agents are working in the real world.\3',
    content, flags=re.DOTALL
)

# Slide 2 (Why DPI-LS)
content = re.sub(
    r'(<div class="notes">)(.*?)(</div><div class="num">02 / 10</div>)',
    r'\1AI is getting cheaper, but companies are spending way more money because they use large AI agents for complex tasks without tracking the costs. BAF models ensure AI is a secure, reliable tool that actually follows company rules and delivers real business value.\3',
    content, flags=re.DOTALL
)

# Slide 6 (The Dashboard)
content = re.sub(
    r'(<div class="notes">)(.*?)(</div><div class="num">06 / 10</div>)',
    r'\1This is our master dashboard. It shows all our AI agents in one place, so managers can instantly see which ones are performing perfectly and which ones need to be paused.\nNote for audience: PI = Expected Target Benchmark. DPI-LS = Actual Evaluated Score.\3',
    content, flags=re.DOTALL
)

# Slide 10 (Why use DPI-LS)
content = re.sub(
    r'(<div class="notes">)(.*?)(</div><div class="num">10 / 10</div>)',
    r'\1The goal isn\'t just to score agents. The goal is to use that score to make decisions—like giving a good agent more work, or stopping a bad agent before it makes mistakes. The future isn\'t about how many agents we have, but knowing exactly which ones we can trust.\3',
    content, flags=re.DOTALL
)

# Integration (Slide 9) - add API Interface wording
if "API Interface" not in content:
    content = content.replace("<h1>Works with the existing ecosystem</h1>", "<h1>Works with the existing ecosystem (API Interface)</h1>")

with open('DPI-LS_Sales_CEO_Client_Presentation_Final.html', 'w', encoding='utf-8') as f:
    f.write(content)
