import os
import sys

def main():
    import uuid
    db_file = f"test_{uuid.uuid4().hex}.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    os.environ["DPI_LS_NO_BLOCK"] = "1"
    
    from dpi_ls import SignalCollector, monitor
    from dpi_ls import _state

    class _FakeAgent:
        def __init__(self):
            self.calls = []
        def invoke(self, prompt: str) -> str:
            self.calls.append(prompt)
            return f"Echo: {prompt}. Contact jane@example.com."

    agent = _FakeAgent()
    collector = monitor(agent, agent_id="e2e-agent", agent_name="E2E")
    
    out1 = agent.invoke("first prompt")
    out2 = agent.invoke("second prompt")
    
    import json
    print("OBSERVATION PAYLOAD:")
    print(json.dumps(collector.to_observation(), indent=2, default=str))

    from dpi_ls.monitor import _finalize
    _state.set_block_on_exit(False)
    _state.set_post_on_exit(True)
    _finalize()

    import httpx
    info = _state.get_server_info()
    r = httpx.get(f"{info.base_url}/agents/e2e-agent/score", timeout=5.0)
    print("STATUS:", r.status_code)
    print("TEXT:", r.text)

if __name__ == "__main__":
    main()
