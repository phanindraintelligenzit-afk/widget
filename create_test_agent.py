import sys
import os

# Default agent ID if none is provided
agent_id = sys.argv[1] if len(sys.argv) > 1 else "agent-001"

content = f'''import os
from dpi_ls import monitor

class MockRealAgent:
    """A realistic mock agent to test DPI-LS telemetry."""
    def __init__(self):
        self.model = "gpt-4-turbo"
        
    def invoke(self, prompt: str) -> str:
        print(f"\\n[MockRealAgent] Thinking about: '{prompt}'...")
        return "I have successfully analyzed the financial reports and optimized the cloud architecture. The tasks are completed with 99.9% accuracy."

# 1. Initialize the fake agent
my_agent = MockRealAgent()

# 2. Wrap it with DPI-LS monitoring for the Agent ID you just onboarded!
# This automatically connects to http://127.0.0.1:8000 and sends live telemetry
monitored_agent = monitor(my_agent, agent_id="{agent_id}", agent_name="Custom UI Agent")

# 3. Simulate some work to generate realistic OpenTelemetry traces
print(f"\\n==============================================")
print(f"  Starting Telemetry Run for: {agent_id}")
print(f"==============================================")

response = monitored_agent.invoke("Analyze the Q3 server cost metrics and optimize deployments.")

print(f"\\n[MockRealAgent] Response: {{response}}\\n")
print(f"==============================================")
print(f"  Telemetry dispatched successfully!")
print(f"  Check your Dashboard at http://127.0.0.1:8000")
print(f"==============================================")
'''

with open('examples/test_custom_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
