import pytest
from playwright.sync_api import Page, expect
import os
import subprocess
import time

@pytest.fixture(scope="session", autouse=True)
def start_server():
    import uuid
    # Use isolated db for browser tests to not mess up dev db
    db_path = f"sqlite:///./browser_test_{uuid.uuid4().hex[:6]}.db"
    env = os.environ.copy()
    env["DPI_DB_URL"] = db_path
    
    # Start the real uvicorn server in the background
    server = subprocess.Popen(
        ["uv", "run", "uvicorn", "api.app:app", "--port", "8123"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Wait for server to be ready
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://localhost:8123/widget/admin-login.html")
            if r.status_code == 200:
                break
        except httpx.ConnectError:
            pass
        time.sleep(0.5)
    else:
        raise RuntimeError("Server failed to start on port 8123")
            
    yield "http://localhost:8123"
    
    server.terminate()
    server.wait()

def test_full_user_journey(page: Page, start_server):
    base_url = start_server
    
    # 1. Login
    page.goto(f"{base_url}/widget/admin-login.html")
    page.fill("input[type='text']", "admin")
    page.fill("input[type='password']", "admin123")
    with page.expect_response("**/api/login") as response_info:
        page.click("button:has-text('Login')")
    assert response_info.value.status == 200
    
    # Wait for navigation
    page.wait_for_url("**/widget/demo.html*")
    
    # 2. Onboarding
    page.goto(f"{base_url}/widget/onboarding.html")
    # Wait for form
    page.fill("#agent_id", "Browser E2E Agent")
    page.fill("#agent_id", "Browser E2E Agent")
    page.fill("#business_owner_name", "Alice")
    page.fill("#business_owner_email", "alice@example.com")
    page.fill("#technical_owner_name", "Bob")
    page.fill("#technical_owner_email", "bob@example.com")
    page.click("button:has-text('Submit Onboarding')")
    
    # Extract agent ID from the URL or next page
    page.wait_for_url("**/widget/agent-config.html*")
    url = page.url
    agent_id = "browser-e2e-agent"
    
    # 3. Configuration
    # Enable some MCPs/Resources
    # The config page has checkboxes
    # Let's just click 'Save Configuration'
    page.click("button:has-text('Save Configuration')")
    # expect(page.locator("text=Configuration Saved")).to_be_visible()
    
    # 4. Execution
    # There should be an 'Execute Agent' button or similar on config or profile
    # Let's check where the execute button is. We know from Phase 2 there is POST /agents/{id}/execute
    # If UI doesn't have an execute button, we can just hit the execution page or use the API directly for this step if UI lacks it, but let's try to find it.

