import os
import glob
import re

new_process_query = """    function processQuery(query) {
        // Keep raw query for some basic checks
        const rawQ = query.toLowerCase();
        // Remove all spaces, dashes, and punctuation for super robust matching against typos
        const q = rawQ.replace(/[^a-z0-9]/g, '');
        
        // Helper function: if any of the provided words are closely found in the stripped query
        const match = (...words) => {
            return words.some(w => {
                const strippedW = w.toLowerCase().replace(/[^a-z0-9]/g, '');
                return q.includes(strippedW);
            });
        };

        setTimeout(() => {
            // 1. Dashboard
            if (match('dashboard', 'leaderboard', 'green', 'red', 'yellow')) {
                appendMessage("The Dashboard is the central command center. It shows all AI agents ranked by their DPI score. Scores >= 80 are Green, 51-79 are Yellow, and <= 50 are Red.", false);
            } 
            // 2. Onboard Agent
            else if (match('onboard', 'register', 'newagent', 'agentid', 'agenttype', 'fillup', 'on boarding')) {
                appendMessage("To Onboard an Agent, fill out the required fields: Agent ID (unique identifier), Description, Agent Type (e.g. Finance), Environment (Production/Dev), Business & Technical Owner emails, and Role. This registers the digital worker in our global tracking database.", false);
            }
            // 3. Configuration
            else if (match('config', 'weight', 'parameter', 'baseline')) {
                appendMessage("In the Configuration section, you allocate exactly 100% weightage across the 7 DPI parameters (Productivity, Quality, Efficiency, Governance, Risk, Cost, Validation). This allows dynamic, custom scoring logic for each specific agent type.", false);
            }
            // 4. Rating
            else if (match('rating', 'review', 'sme', 'stars')) {
                appendMessage("The Rating page allows Subject Matter Experts (SMEs) to evaluate agents on a 1-5 star scale. Submitting a review instantly updates the Governance (G) and Execution (E) multipliers in the database.", false);
            }
            // 5. Profile
            else if (match('profile', 'history', 'details')) {
                appendMessage("The Profile section provides a detailed, historical view of a specific agent. It displays their exact score breakdown and telemetry history over time.", false);
            }
            // 6. Resources
            else if (match('resource', 'manual', 'guide')) {
                appendMessage("The Resources tab provides operational manuals, architectural guidelines, and whitepapers explaining the full DPI-LS ecosystem and how to integrate your own custom frameworks.", false);
            }
            // 7. Formula / DPI-LS
            else if (match('calculate', 'formula', 'dpils', 'dpi ls', 'math')) {
                appendMessage("DPI-LS is calculated as: (P * Q^1.5 * E) * (G^1.5 * R^2) * C * V. This ensures compliance (G, R, V) acts as a strict multiplier, while performance (P, Q, E, C) drives the baseline.", false);
            }
            // 8. Technical: OpenTelemetry (Handles typos like 'open telementry', 'open telmetry')
            else if (match('opentelemetry', 'telemetry', 'telementry', 'opentelementry', 'opentel')) {
                appendMessage("OpenTelemetry is used in our platform for real-time observability. We use it to ingest latency, success rates, and efficiency metrics directly from the AI agents executing in production. It provides vendor-agnostic traces and metrics to calculate the 'E' (Efficiency) parameter.", false);
            }
            // 9. Technical: MCP (Model Context Protocol)
            else if (match('mcp', 'modelcontext', 'model context protocol')) {
                appendMessage("MCP (Model Context Protocol) is utilized to standardise how our evaluation engine communicates with different AI models. It ensures that when we evaluate Governance (G) or Quality (Q), the context and prompts are securely and consistently delivered across various LLM backends.", false);
            }
            // 10. Technical: REST API & FastAPI
            else if (match('restapi', 'api', 'fastapi', 'backend endpoint')) {
                appendMessage("Our REST API is built with FastAPI (Python). It handles endpoints like `GET /ratings` to populate the dashboard, and `POST /api/agents/{id}/execute` to trigger background asynchronous evaluations. It uses SQLite for fast, lightweight data persistence.", false);
            }
            // 11. Project History, Architecture, & Code Wise (From Start to Now)
            else if (match('history', 'architecture', 'codewise', 'code wise', 'from starting', 'what we did', 'functionality', 'everything', 'codebase', 'deep research')) {
                appendMessage("Here is the complete architectural history from start to now:\\n\\n" +
                              "1. Database Architecture: We migrated from mocked JSON data to a fully persistent SQLite database (`dpi_ls.db`) using SQLAlchemy ORM (models.py/repo.py).\\n" + 
                              "2. API Layer: We built a high-performance Python FastAPI backend (`api/app.py`) with full CORS support and asynchronous endpoint routing.\\n" +
                              "3. Scoring Engine: We engineered a mathematical DPI-LS scoring engine (`api/scoring.py`) that strictly enforces the P*Q*E*G*R*C*V baseline multipliers without frontend manipulation.\\n" +
                              "4. Telemetry Pipeline: We built an ingestion script (`test_agent.py`) that generates realistic mock telemetry using ThreadPoolExecutors and saves it directly to the database.\\n" +
                              "5. System Stability: We solved critical backend crashes (Uvicorn deadlocks) by removing blocking SMTP code, and built a robust frontend Search Bar with Javascript Promises and version tracking to fix async race conditions.\\n" + 
                              "6. UI Integration: We fully wired the Dashboard, Configuration (100% weight validations), Profile, Rating, and Onboarding screens into the Live APIs using Fetch calls.\\n\\n" +
                              "We have successfully built a full-stack, enterprise-grade AI monitoring platform!", false);
            }
            // 12. Technical: Resources per Parameter & Stack
            else if (match('resourcesused', 'parameter resource', 'stack', 'tech stack', 'python', 'javascript')) {
                appendMessage("Our technical stack relies on Python/FastAPI for the backend and HTML/JS/CSS for the frontend. For parameters: Productivity (P) uses AgentOps; Quality (Q) uses DeepEval/Ragas; Efficiency (E) uses OpenTelemetry; Governance (G) uses MCP; Risk (R) uses security scanners; Cost (C) integrates AWS Cost Explorer APIs; and Validation (V) uses our custom algorithms.", false);
            }
            else if (match('hello', 'hi ', 'hey ', 'greetings')) {
                appendMessage("Hello! I am your DPI-LS Technical Assistant. You can ask me about any of the 6 platform sections, deep technical questions (OpenTelemetry, MCP, APIs), or even ask for the full architectural code history of what we built from the start!", false);
            } 
            // Fallback (Exact phrasing requested)
            else {
                appendMessage("its a out of questions and it is not related to our dpi-ls related also so so sryyy . meet you soons for asking thankyou.", false);
            }
        }, 600);
    }"""

import re
pattern = re.compile(r"\s*function processQuery\(query\) \{.*?^\s*\}", re.DOTALL | re.MULTILINE)

for filepath in glob.glob("widget/*.html"):
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()
    
    # We find the exact start of processQuery and the exact start of handleSend
    start_idx = html.find("function processQuery(query)")
    end_idx = html.find("function handleSend()")
    
    if start_idx != -1 and end_idx != -1:
        # Find the whitespace preceding function processQuery to keep indentation
        preceding_whitespace = html.rfind('\n', 0, start_idx)
        if preceding_whitespace != -1:
            start_idx = preceding_whitespace + 1
            
        html = html[:start_idx] + new_process_query + "\n    " + html[end_idx:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Updated Advanced Robust Chatbot logic in {filepath}")
    else:
        print(f"Could not find boundaries in {filepath}")
