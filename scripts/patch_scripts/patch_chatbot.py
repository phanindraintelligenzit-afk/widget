import os
import glob
import re

new_process_query = """      function processQuery(query) {
          const q = query.toLowerCase();
          setTimeout(() => {
              // 1. Dashboard
              if (q.includes('dashboard') || q.includes('leaderboard') || q.includes('green') || q.includes('red') || q.includes('yellow')) {
                  appendMessage("The Dashboard is the central command center. It shows all AI agents ranked by their DPI score. Scores >= 80 are Green, 51-79 are Yellow, and <= 50 are Red.", false);
              } 
              // 2. Onboard Agent
              else if (q.includes('onboard') || q.includes('register') || q.includes('new agent') || q.includes('agent id') || q.includes('agent type') || q.includes('fillup')) {
                  appendMessage("To Onboard an Agent, fill out the required fields: Agent ID (unique identifier), Description, Agent Type (e.g. Finance), Environment (Production/Dev), Business & Technical Owner emails, and Role. This registers the digital worker in our global tracking database.", false);
              }
              // 3. Configuration
              else if (q.includes('config') || q.includes('weight') || q.includes('parameter') || q.includes('baseline')) {
                  appendMessage("In the Configuration section, you allocate exactly 100% weightage across the 7 DPI parameters (Productivity, Quality, Efficiency, Governance, Risk, Cost, Validation). This allows dynamic, custom scoring logic for each specific agent type.", false);
              }
              // 4. Rating
              else if (q.includes('rating') || q.includes('review') || q.includes('sme')) {
                  appendMessage("The Rating page allows Subject Matter Experts (SMEs) to evaluate agents on a 1-5 star scale. Submitting a review instantly updates the Governance (G) and Execution (E) multipliers in the database.", false);
              }
              // 5. Profile
              else if (q.includes('profile') || q.includes('history') || q.includes('details')) {
                  appendMessage("The Profile section provides a detailed, historical view of a specific agent. It displays their exact score breakdown and telemetry history over time.", false);
              }
              // 6. Resources
              else if (q.includes('resource') || q.includes('manual') || q.includes('guide')) {
                  appendMessage("The Resources tab provides operational manuals, architectural guidelines, and whitepapers explaining the full DPI-LS ecosystem and how to integrate your own custom frameworks.", false);
              }
              // 7. Formula / DPI-LS
              else if (q.includes('calculate') || q.includes('formula') || q.includes('dpi-ls') || q.includes('dpi ls')) {
                  appendMessage("DPI-LS is calculated as: (P * Q^1.5 * E) * (G^1.5 * R^2) * C * V. This ensures compliance (G, R, V) acts as a strict multiplier, while performance (P, Q, E, C) drives the baseline.", false);
              }
              // 8. Technical: OpenTelemetry
              else if (q.includes('opentelemetry') || q.includes('telemetry')) {
                  appendMessage("OpenTelemetry is used in our platform for real-time observability. We use it to ingest latency, success rates, and efficiency metrics directly from the AI agents executing in production. It provides vendor-agnostic traces and metrics to calculate the 'E' (Efficiency) parameter.", false);
              }
              // 9. Technical: MCP (Model Context Protocol)
              else if (q.includes('mcp') || q.includes('model context')) {
                  appendMessage("MCP (Model Context Protocol) is utilized to standardise how our evaluation engine communicates with different AI models. It ensures that when we evaluate Governance (G) or Quality (Q), the context and prompts are securely and consistently delivered across various LLM backends.", false);
              }
              // 10. Technical: REST API
              else if (q.includes('rest api') || q.includes('api')) {
                  appendMessage("Our REST API is built with FastAPI (Python). It handles endpoints like `GET /ratings` to populate the dashboard, and `POST /api/agents/{id}/execute` to trigger background asynchronous evaluations. It uses SQLite for fast, lightweight data persistence.", false);
              }
              // 11. Technical: Resources per Parameter & Coding
              else if (q.includes('resources used') || q.includes('parameter') || q.includes('coding') || q.includes('code') || q.includes('stack')) {
                  appendMessage("Our technical stack relies on Python/FastAPI for the backend and HTML/JS/CSS for the frontend. For parameters: Productivity (P) uses AgentOps; Quality (Q) uses DeepEval/Ragas; Efficiency (E) uses OpenTelemetry; Governance (G) uses MCP; Risk (R) uses security scanners; Cost (C) integrates AWS Cost Explorer APIs; and Validation (V) uses our custom algorithms.", false);
              }
              else if (q.includes('hello') || q.includes('hi')) {
                  appendMessage("Hello! I am your DPI-LS Technical Assistant. You can ask me about any of the 6 platform sections, or deep technical questions about OpenTelemetry, MCP, REST APIs, and our architectural code!", false);
              } 
              // Fallback
              else {
                  appendMessage("its a out of questions and it is not related to our dpi-ls related also so so sryyy . meet you soons for asking thankyou.", false);
              }
          }, 600);
      }"""

# Regex to find the processQuery block and replace it
pattern = re.compile(r"      function processQuery\(query\) \{.*?^      \}", re.DOTALL | re.MULTILINE)

for filepath in glob.glob("widget/*.html"):
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()
    
    if pattern.search(html):
        html = pattern.sub(new_process_query, html)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Updated Chatbot logic in {filepath}")
    else:
        print(f"No Chatbot logic found in {filepath}")
