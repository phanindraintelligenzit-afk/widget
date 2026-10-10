import re

# Read original template to keep CSS and JS
with open('widget/DPI-LS_Sales_CEO_Client_Presentation_Final.html', 'r', encoding='utf-8') as f:
    content = f.read()

header = content.split('<main>')[0] + '<main>'
footer = '</main>' + content.split('</main>')[1]

slides_html = """
<section class="slide active">
<div class="top"></div><div class="kicker">Intelligenz IT</div><h1>BEYOND AI AGENTS</h1><div class="lead">The Measurable AI Enterprise</div>
<div class="bullets"><div>From agent deployment to performance, efficiency, trust and accountable autonomy.</div></div>
<div class="close">MEASURE INTELLIGENCE BEFORE YOU SCALE AUTONOMY</div>
<div class="notes">Good morning everyone. Today I'll be presenting on how we move beyond just deploying AI agents, to actually measuring them. DPI-LS is a scoring dashboard that tells us exactly how well, how safely, and how cost-effectively our AI agents are working in the real world.</div><div class="num">01 / 14</div></section>

<section class="slide">
<div class="top"></div><div class="kicker">The Problem</div><h1>THE AI COST PARADOX</h1><div class="lead">AI Is Getting Cheaper. But Enterprise Intelligence Is Getting More Expensive.</div>
<div class="three"><div><b>280x</b><span>Fall in the price of a fixed level of AI performance</span></div><div><b>320x</b><span>Growth in token consumption per organization</span></div><div><b>73%</b><span>Of organizations exceeded their AI budgets last year</span></div></div>
<div class="close">The problem is no longer the cost of intelligence. It is the cost of coordinating intelligence at scale.</div>
<div class="notes">AI is getting cheaper, but companies are spending way more money. Why? Because they use large AI agents for complex tasks without tracking the costs. BAF models ensure AI is a secure, reliable tool that actually follows company rules and delivers real business value.</div><div class="num">02 / 14</div></section>

<section class="slide">
<div class="top"></div><div class="kicker">The Gap</div><h1>THE NEW OBSERVABILITY GAP</h1><div class="lead">Every agent produces activity. Proving performance remains a challenge.</div>
<div class="flow"><span>Task outcomes</span><span>Token consumption</span><span>Latency</span><span>Security incidents</span><span>Cloud cost</span></div>
<div class="close">An API Interface collects the raw telemetry. DPI-LS calculates the intelligence.</div>
<div class="notes">Right now, different teams (like security, finance, and engineering) only see small pieces of what the AI is doing. Our solution brings all that messy data together to give us one clear, measurable picture of the agent's health.</div><div class="num">03 / 14</div></section>

<section class="slide">
<div class="top"></div><div class="kicker">The Measurement Model</div><h1>FROM API INTERFACE TO AN AGENT HEALTH SCORE</h1><div class="lead">What if every enterprise agent had a performance score?</div>
<div class="dims">
<div><b>P</b><strong>Performance</strong><small>Is the agent achieving the objective?</small></div>
<div><b>Q</b><strong>Quality</strong><small>Can we trust the output?</small></div>
<div><b>R</b><strong>Reliability</strong><small>Are actions and tools succeeding?</small></div>
<div><b>E</b><strong>Economics</strong><small>What does the outcome cost?</small></div>
</div>
<div class="dims" style="margin-top:16px;">
<div><b>S</b><strong>Security</strong><small>What exposure is being created?</small></div>
<div><b>G</b><strong>Governance</strong><small>Is the agent operating within policy?</small></div>
<div><b>V</b><strong>Validation</strong><small>Are required controls satisfied?</small></div>
</div>
<div class="notes">Instead of just guessing if an agent is doing a good job, we give it a real score based on 7 key things: Productivity, Quality, Execution, Cost, Security, Governance, and Validation.</div><div class="num">04 / 14</div></section>

<section class="slide">
<div class="top"></div><div class="kicker">The Dashboard</div><h1>THE ENTERPRISE AGENT CONTROL TOWER</h1><div class="lead">One enterprise. One view of the AI workforce.</div>
<div class="groups">
<div><b>Procurement Agent</b><span>Overall: 92 | Quality: 94 | Cost: 96</span></div>
<div><b>Cloud Ops Agent</b><span>Overall: 86 | Quality: 91 | Cost: 88</span></div>
<div><b>Claims Agent</b><span>Overall: 85 | Quality: 89 | Cost: 88</span></div>
<div><b>Customer Agent</b><span>Overall: 82 | Quality: 85 | Cost: 84</span></div>
</div>
<div class="close">RECOMMENDED ACTION: Approved to scale autonomy across further deployments.</div>
<div class="notes">This is our master dashboard. It shows all our AI agents in one single view, so managers can instantly see which agents are performing perfectly (in green) and which ones need to be fixed or paused. (Note: PI = Expected Target Benchmark. DPI-LS = Actual Evaluated Score.)</div><div class="num">05 / 14</div></section>

<section class="slide">
<div class="top"></div><div class="kicker">From Insight to Action</div><h1>ACTIONABLE INTELLIGENCE: MEASURE &rarr; DECIDE &rarr; IMPROVE</h1><div class="lead">Measurement should shape agent behaviour and drive continuous improvement.</div>
<div class="flow"><span>Observe</span><i>&rarr;</i><span>Score</span><i>&rarr;</i><span>Explain</span><i>&rarr;</i><span>Decide</span><i>&rarr;</i><span>Improve</span></div>
<div class="bullets"><div>Decisions include: <b>Scale</b>, <b>Optimize</b>, <b>Restrict</b>, <b>Investigate</b>, or <b>Reconfigure</b>.</div></div>
<div class="notes">The goal isn't just to look at scores. The goal is to use these scores to make smart business decisions—like giving a highly-rated agent more work to do, or stopping a failing agent before it makes a costly mistake.</div><div class="num">06 / 14</div></section>

<section class="slide">
<div class="top"></div><div class="kicker">Appendix - Implementation</div><h1>WHERE THE SCORING LAYER SITS</h1><div class="lead">Designed to work with existing observability and cost tooling rather than replacing it.</div>
<div class="flow" style="flex-direction:column; align-items:flex-start;">
<span>Existing AI agents & Orchestration</span><i>&darr;</i>
<span><b>API Interface (OpenTelemetry, REST APIs, and MCP integrations)</b></span><i>&darr;</i>
<span>AGENT SCORING LAYER</span><i>&darr;</i>
<span>Enterprise Agent Dashboard</span>
</div>
<div class="notes">How does this actually work behind the scenes? We use a simple 'API Interface' to silently collect data while the agents are working, and our engine automatically turns that raw data into the dashboard you just saw.</div><div class="num">07 / 14</div></section>

<section class="slide">
<div class="top"></div><div class="kicker">Appendix - Innovation</div><h1>THE AGENT PERFORMANCE CONTRACT</h1><div class="lead">Before an enterprise agent receives responsibility, define its contract.</div>
<div class="three">
<div><b>1. Outcome</b><span>What outcome is expected?</span></div>
<div><b>2. Quality</b><span>What quality is acceptable?</span></div>
<div><b>3. Economics</b><span>What token budget is acceptable?</span></div>
</div>
<div class="close">THEN: The scoring engine measures the agent against the contract.</div>
<div class="notes">Before we let an AI agent do any work for the enterprise, we write a strict 'contract' that defines the exact quality, cost, and security rules it must follow. The engine then scores the agent against those exact rules.</div><div class="num">08 / 14</div></section>

<section class="slide">
<div class="top"></div><div class="kicker">Appendix - Summary</div><h1>THREE IDEAS TO REMEMBER</h1><div class="lead">What the audience should take away.</div>
<div class="bullets">
<div><b>1.</b> Every agent needs a measurable performance contract.</div>
<div><b>2.</b> Agent health must be visible at enterprise level, not buried inside technical telemetry.</div>
<div><b>3.</b> Greater autonomy should be earned through evidence.</div>
</div>
<div class="notes">To summarize: agents need contracts, health must be visible at the top level, and AI autonomy must be earned through evidence, not just given freely.</div><div class="num">09 / 14</div></section>

<section class="slide">
<div class="top"></div><div class="kicker">Conclusion</div><h1>BEYOND AGENTS</h1><div class="lead">The future of enterprise AI will not be measured by how many agents we deploy.</div>
<div class="bullets"><div>It will be measured by how confidently we can decide which agents to trust, optimize, restrict and scale.</div></div>
<div class="close">Measure Intelligence Before You Scale Autonomy.</div>
<div class="notes">The future of business isn't about how many AI agents we can build. It's about knowing exactly which agents we can trust, which ones save us money, and which ones are safe to scale across the company.</div><div class="num">10 / 14</div></section>

<section class="slide">
<div class="top"></div><div class="kicker">End</div><h1>Thank You!</h1><div class="lead">Q&A and Next Steps</div>
<div class="notes">Thank you all. I'm happy to take any questions you have about the architecture, the scoring, or how we can implement this today.</div><div class="num">11 / 14</div></section>
"""

new_content = header + "\n" + slides_html + "\n" + footer

with open('widget/DPI-LS_Sales_CEO_Client_Presentation_Perfect.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Generated perfect HTML presentation!")
