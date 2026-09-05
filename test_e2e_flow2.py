import httpx
import asyncio
import uuid
import time

async def main():
    base_url = 'http://127.0.0.1:8000'
    agent_id = f"test-agent-{uuid.uuid4().hex[:6]}"
    
    print(f"\n--- Testing Onboarding ---")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{base_url}/api/agents", json={
                "id": agent_id,
                "name": "Integration Test Agent",
                "description": "Gap Analysis",
                "team": "QA",
                "type": "custom",
                "environment": "production",
                "business_owner_name": "Bob",
                "business_owner_email": "bob@b.com",
                "technical_owner_name": "Alice",
                "technical_owner_email": "alice@a.com",
                "digital_worker_role": "Analyst"
            })
            print("Onboarding Response:", resp.status_code, resp.json() if resp.status_code == 200 else resp.text)
            
            # Test duplicate
            resp_dup = await client.post(f"{base_url}/api/agents", json={
                "id": agent_id,
                "name": "Integration Test Agent",
                "description": "Gap Analysis"
            })
            print("Duplicate Onboarding Response:", resp_dup.status_code, resp_dup.json() if resp_dup.status_code == 400 else "")
            
    except Exception as e:
        print(f"Connection failed: {e}. Is the server running?")

if __name__ == '__main__':
    asyncio.run(main())
