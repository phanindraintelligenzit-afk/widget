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
    env["DATABASE_URL"] = db_path
    
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
            httpx.get("http://localhost:8123/widget/admin-login.html")
            break
        except httpx.ConnectError:
            time.sleep(0.5)
            
    yield "http://localhost:8123"
    
    server.terminate()
    server.wait()

def test_full_user_journey(page: Page, start_server):
    base_url = start_server
    
    # 1. Login
    page.goto(f"{base_url}/widget/admin-login.html")
    page.fill("input[type='text']", "test_user_a")
    page.click("button:has-text('Login')")
    
    # 2. Onboarding
    page.goto(f"{base_url}/widget/onboarding.html")
    # Wait for form
    page.fill("#agent_name", "Browser E2E Agent")
    page.fill("#department", "Engineering")
    page.click("button:has-text('Save & Continue')")
    
    # Extract agent ID from the URL or next page
    page.wait_for_url(f"**/widget/agent-config.html?agent_id=*")
    url = page.url
    agent_id = url.split("agent_id=")[1]
    
    # 3. Configuration
    # Enable some MCPs/Resources
    # The config page has checkboxes
    # Let's just click 'Save Configuration'
    page.click("button:has-text('Save Configuration')")
    expect(page.locator("text=Configuration Saved")).to_be_visible()
    
    # 4. Execution
    # There should be an 'Execute Agent' button or similar on config or profile
    # Let's check where the execute button is. We know from Phase 2 there is POST /agents/{id}/execute
    # If UI doesn't have an execute button, we can just hit the execution page or use the API directly for this step if UI lacks it, but let's try to find it.

