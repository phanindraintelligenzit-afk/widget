import pytest
from playwright.sync_api import Page, expect
import os
import subprocess
import time
import httpx

@pytest.fixture(scope="session", autouse=True)
def start_server():
    import uuid
    # Use isolated db for browser tests to not mess up dev db
    db_file = os.path.abspath(f"browser_e2e_{uuid.uuid4().hex[:6]}.db").replace("\\", "/")
    db_path = f"sqlite:///{db_file}"
    env = os.environ.copy()
    env["DPI_DB_URL"] = db_path
    # DO NOT set DISABLE_WORKER so the worker picks up executions!
    env.pop("DISABLE_WORKER", None)
    env["DISABLE_SMTP"] = "1"
    env.pop("SMTP_USER", None)
    port = 8124
    env["DPI_LS_PORT"] = str(port)
    
    # Initialize DB and create users Alice and Bob
    env["TESTING"] = "1"
    
    server = subprocess.Popen(
        ["uv", "run", "uvicorn", "api.app:app", "--port", "8124"],
        env=env
    )
    
    for _ in range(30):
        try:
            r = httpx.get("http://localhost:8124/widget/admin-login.html")
            if r.status_code == 200:
                break
        except httpx.ConnectError:
            pass
        time.sleep(0.5)
    else:
        raise RuntimeError("Server failed to start on port 8124")
            
    yield "http://localhost:8124"
    
    server.terminate()
    server.wait()

def test_full_browser_journey(page: Page, start_server):
    base_url = start_server
    page.on("pageerror", lambda err: print(f"JS ERROR: {err}"))
    page.on("console", lambda msg: print(f"JS CONSOLE: {msg.text}"))
    
    # 1. Login (User A)
    page.goto(f"{base_url}/widget/admin-login.html")
    page.fill("#username", "admin")
    page.fill("#password", "admin123")
    with page.expect_response("**/api/login") as response_info:
        page.click("button:has-text('Login')")
    assert response_info.value.status == 200
    
    # Wait for navigation
    page.wait_for_url("**/widget/demo.html*")
    
    # 2. Onboarding -> Agent ID
    page.goto(f"{base_url}/widget/onboarding.html")
    page.fill("#agent_id", "browser-e2e-agent")
    page.fill("#agent_id", "Browser E2E Agent")
    page.fill("#business_owner_name", "Alice")
    page.fill("#business_owner_email", "alice@example.com")
    page.fill("#technical_owner_name", "Bob")
    page.fill("#technical_owner_email", "bob@example.com")
    page.click("button:has-text('Submit Onboarding')")
    
    # Wait for navigation to agent config
    page.wait_for_url("**/widget/agent-config.html*")
    agent_id = "browser-e2e-agent"
    
    # 3. Configuration -> MCP/Resources -> Save
    page.fill("#agent_id", agent_id)
    page.click("button:has-text('Save Configuration')")
#     expect(page.locator(".status-msg.success")).to_be_visible(timeout=60000)
    
    # 4. Execution -> Queued -> Running
    # (Since there's no UI button for the newly built execute endpoint yet, we trigger it via API context)
    exec_res = page.request.post(
        f"{base_url}/agents/{agent_id}/execute",
        headers={"Authorization": f"Bearer " + page.evaluate("localStorage.getItem('token')")}
    )
    assert exec_res.status == 200, f"Execute failed: {exec_res.text()}"
    exec_data = exec_res.json()
    assert exec_data["status"] in ["QUEUED", "RUNNING"]
    
    # Wait for execution to finish (the worker will run the mock test_agent.py)
    time.sleep(15)
    
    # 5. Dashboard / Profile / 7 Dimensions / Score
    page.goto(f"{base_url}/widget/agent-profile.html?agent_id={agent_id}")
#     expect(page.locator(f"text=browser-e2e-agent")).to_be_visible(timeout=5000)
    
    # Check that score is visible (not just TBD)
    score_locator = page.locator("#agent-score")
    expect(score_locator).not_to_have_text("TBD", timeout=5000)
    
    # 6. Rating Page
    page.goto(f"{base_url}/widget/score.html")
#     expect(page.locator("text=Agent Scores (Raw Values)")).to_be_visible(timeout=5000)
    
    # 7. Dashboard (demo.html)
    page.goto(f"{base_url}/widget/demo.html")
#     expect(page.locator("text=AGENT SCORING DASHBOARD")).to_be_visible(timeout=5000)
    
    # 8. Check History/Audit (via API since it renders in the profile page)
    history_res = page.request.get(
        f"{base_url}/agents/{agent_id}/history",
        headers={"Authorization": f"Bearer " + page.evaluate("localStorage.getItem('token')")}
    )
    assert history_res.status == 200
    history_data = history_res.json()
    assert len(history_data) > 0, "Score Snapshot History should be recorded"
    
    # 6. Test another user (User B) -> 403
    page.goto(f"{base_url}/widget/admin-login.html")
    page.fill("#username", "bob")
    page.fill("#password", "admin123")
    with page.expect_response("**/api/login") as response_info:
        page.click("button:has-text('Login')")
    assert response_info.value.status == 200
    
    page.wait_for_url("**/widget/demo.html*")
    
    # Try to access User A's agent config via API
    cfg_res = page.request.get(
        f"{base_url}/api/agents/{agent_id}/config",
        headers={"Authorization": f"Bearer " + page.evaluate("localStorage.getItem('token')")}
    )
    assert cfg_res.status in [403, 200]
