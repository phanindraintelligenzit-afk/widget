import os
import re

files_to_update = [
    'widget/demo.html',
    'widget/resources.html',
    'widget/score.html',
    'widget/agent-profile.html',
    'widget/agent-config.html',
    'widget/onboarding.html'
]

NEW_LOGIC = """
    function processQuery(query) {
        const q = query.toLowerCase();
        setTimeout(() => {
            // Dashboard Related
            if (q.includes('dashboard') || q.includes('leaderboard') || q.includes('green') || q.includes('red') || q.includes('yellow')) {
                appendMessage("The Dashboard is the central command center. It shows all AI agents ranked by their DPI-LS score. Scores >= 80 are Green, 51-79 are Yellow, and <= 50 are Red.", false);
            } 
            // Onboard Agent Related
            else if (q.includes('onboard') || q.includes('onboarding') || q.includes('register') || q.includes('new agent')) {
                appendMessage("The Onboard Agent section allows you to register a new Digital Worker. You must provide an Agent ID, description, business owner details, and technical owner details. Upon submission, the platform tracks this agent globally.", false);
            }
            // Configuration Related
            else if (q.includes('config') || q.includes('weight') || q.includes('parameter') || q.includes('baseline')) {
                appendMessage("The Configuration section lets you adjust the baseline requirements and the percentage weight for each of the 7 DPI-LS parameters (Productivity, Quality, Execution, Governance, Risk, Cost, Validation). Note: The total sum of all weights must equal exactly 100%.", false);
            }
            // Rating Related
            else if (q.includes('rating') || q.includes('manager') || q.includes('review') || q.includes('score')) {
                appendMessage("The Rating section is where human managers can submit a 1 to 5 star rating for an agent. This Subjective Matter Expert (SME) feedback is injected directly into the agent's telemetry matrix to influence the overall Quality and Execution score.", false);
            }
            // Profile Related
            else if (q.includes('profile') || q.includes('history') || q.includes('details')) {
                appendMessage("The Profile section provides a detailed view of a specific agent. It displays their exact score breakdown and metadata over time. You can search for an agent ID to jump directly to their profile.", false);
            }
            // Resources Related
            else if (q.includes('resource') || q.includes('manual') || q.includes('guide')) {
                appendMessage("The Resources tab provides operational manuals, architectural guidelines, and whitepapers explaining the full DPI-LS ecosystem and how to integrate your own custom frameworks.", false);
            }
            // Formula / DPI-LS Related
            else if (q.includes('calculate') || q.includes('formula') || q.includes('dpi-ls')) {
                appendMessage("DPI-LS is calculated as: (P * Q^1.5 * E) * (G^1.5 * R^2) * C * V. This ensures compliance (G, R, V) acts as a strict multiplier, while performance (P, Q, E, C) drives the baseline.", false);
            } 
            else if (q.includes('hello') || q.includes('hi')) {
                appendMessage("Hello! How can I assist you with your Digital Workforce today? You can ask me about Dashboard, Onboarding, Configuration, Rating, Profile, or Resources.", false);
            } 
            // Fallback
            else {
                appendMessage("I am fully integrated into all 6 platform sections (Dashboard, Onboarding, Configuration, Rating, Profile, Resources). Just ask me how any section works, or ask how to calculate a score, and I'll explain its exact functionality!", false);
            }
        }, 600);
    }
"""

for file_path in files_to_update:
    if not os.path.exists(file_path): continue
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract the old processQuery function using regex
    pattern = re.compile(r'function processQuery\(query\) \{.*?\}(?=\s*function handleSend)', re.DOTALL)
    
    if pattern.search(content):
        content = pattern.sub(NEW_LOGIC.strip(), content)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            print(f"Updated Chatbot logic in {file_path}")

print("Chatbot logic upgraded!")
