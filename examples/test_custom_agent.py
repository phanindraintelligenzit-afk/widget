import os
from dpi_ls import monitor
import time

class MockRealAgent:
    """A realistic mock agent to test DPI-LS telemetry."""
    def __init__(self):
        self.model = "gpt-4-turbo"
        
    def invoke(self, prompt: str) -> str:
        print(f"\n[MockRealAgent] Processing task: {prompt}")
        time.sleep(1)
        return "I have successfully analyzed the financial reports and optimized the cloud architecture. The tasks are completed with 99.9% accuracy."

if __name__ == "__main__":
    import sys
    agent_id = sys.argv[1] if len(sys.argv) > 1 else "agent-001"
    
    # 1. Initialize the fake agent
    my_agent = MockRealAgent()

    # 2. Wrap it with DPI-LS monitoring for the Agent ID you just onboarded!
    monitored_agent = monitor(my_agent, agent_id=agent_id, agent_name="Custom UI Agent")

    # 3. Simulate some work to generate realistic OpenTelemetry traces
    print(f"\n==============================================")
    print(f"  Starting Real Telemetry Run for: {agent_id}")
    print(f"==============================================")

    response = my_agent.invoke("Analyze the Q3 server cost metrics and optimize deployments.")

    print(f"\n[MockRealAgent] Response: {response}\n")
    print(f"==============================================")
    print(f"  Telemetry dispatched successfully!")
    print(f"  Check your Dashboard at http://127.0.0.1:8000")
    print(f"==============================================")
