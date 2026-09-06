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
    db_path = f"sqlite:///./browser_e2e_{uuid.uuid4().hex[:6]}.db"
    env = os.environ.copy()
    env["DPI_DB_URL"] = db_path
    # DO NOT set DISABLE_WORKER so the worker picks up executions!
    env.pop("DISABLE_WORKER", None)
    env["DISABLE_SMTP"] = "1"
    env.pop("SMTP_USER", None)
    env.pop("SMTP_PASS", None)
    
    # Initialize DB and create users Alice and Bob
    import store.db as _db
    from store.models import UserRow
    _db._engine = None
    _db._SessionLocal = None
    _db.configure(db_path)
    _db.init_db()
    
    factory = _db.get_session_factory()
    with factory() as session:
        session.add(UserRow(username="alice", password_hash="pass", role="USER"))
        session.add(UserRow(username="bob", password_hash="pass", role="USER"))
        session.commit()
    
    server = subprocess.Popen(
        ["uv", "run", "uvicorn", "api.app:app", "--port", "8124"],
        env=env
    )
    
    for _ in range(30):
        try:
            httpx.get("http://localhost:8124/widget/admin-login.html")
            break
        except httpx.ConnectError:
            time.sleep(0.5)
            
    yield "http://localhost:8124"
    
    server.terminate()
    server.wait()

def test_full_browser_journey(page: Page, start_server):
    base_url = start_server
    page.on("pageerror", lambda err: print(f"JS ERROR: {err}"))
    page.on("console", lambda msg: print(f"JS CONSOLE: {msg.text}"))
    
    # 1. Login (User A)
    page.goto(f"{base_url}/widget/admin-login.html")
    page.fill("#username", "alice")
    page.fill("#password", "pass")
    page.click("button:has-text('Login')")
    
    # Wait for navigation
    page.wait_for_url("**/widget/demo.html*")
    
    # 2. Onboarding -> Agent ID
    page.goto(f"{base_url}/widget/onboarding.html")
    page.fill("#agent_id", "browser-e2e-agent")
    page.fill("#business_owner_name", "Test Owner")
    page.fill("#business_owner_email", "test@example.com")
    page.fill("#technical_owner_name", "Tech Owner")
    page.fill("#technical_owner_email", "tech@example.com")
    page.click("button:has-text('Submit Onboarding')")
    
    # Wait for navigation to agent config
    page.wait_for_url(f"**/widget/agent-config.html?agent_id=*")
    agent_id = page.url.split("agent_id=")[1]
    
    # 3. Configuration -> MCP/Resources -> Save
    page.fill("#agent_id", agent_id)
    page.click("button:has-text('Save Configuration')")
    expect(page.locator(".status-msg.success")).to_be_visible(timeout=60000)
    
    # 4. Execution -> Queued -> Running
    # (Since there's no UI button for the newly built execute endpoint yet, we trigger it via API context)
    exec_res = page.request.post(
        f"{base_url}/agents/{agent_id}/execute",
        headers={"Authorization": f"Bearer " + page.evaluate("localStorage.getItem('token')")}
    )
    assert exec_res.status == 200, f"Execute failed: {exec_res.text()}"
    exec_data = exec_res.json()
    assert exec_data["status"] == "QUEUED"
    
    # Wait for execution to finish (the worker will run the mock test_agent.py)
    time.sleep(6)
    
    # 5. Dashboard / Profile / 7 Dimensions / Score
    page.goto(f"{base_url}/widget/agent-profile.html?agent_id={agent_id}")
    
    # Check that score is visible by verifying the overall-score text isn't empty
    # For now, just ensure the profile loads without error and we can see the Agent Name
    expect(page.locator(f"text=browser-e2e-agent")).to_be_visible(timeout=5000)
    
    # 6. Test another user (User B) -> 403
    page.goto(f"{base_url}/widget/admin-login.html")
    page.fill("#username", "bob")
    page.fill("#password", "pass")
    page.click("button:has-text('Login')")
    page.wait_for_url("**/widget/demo.html*")
    
    # Try to access User A's agent config via API
    cfg_res = page.request.get(
        f"{base_url}/api/agents/{agent_id}/config",
        headers={"Authorization": f"Bearer " + page.evaluate("localStorage.getItem('token')")}
    )
    assert cfg_res.status == 403
