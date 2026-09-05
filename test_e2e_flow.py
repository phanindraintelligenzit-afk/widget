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
            resp = await client.post(f"{base_url}/agents/", json={
                "id": agent_id,
                "name": "Integration Test Agent",
                "description": "Gap Analysis",
                "team": "QA"
            })
            print("Onboarding Response:", resp.status_code, resp.json() if resp.status_code == 200 else resp.text)
            
            # Test duplicate
            resp_dup = await client.post(f"{base_url}/agents/", json={
                "id": agent_id,
                "name": "Integration Test Agent",
                "description": "Gap Analysis",
                "team": "QA"
            })
            print("Duplicate Onboarding Response:", resp_dup.status_code)

            print(f"\n--- Testing Score Preview ---")
            resp_preview = await client.post(f"{base_url}/api/agents/{agent_id}/score/preview", json={
                "P": 1, "Q": 1, "E": 1, "G": 1, "R": 1, "V": 1, "C": 1
            })
            print("Preview Response:", resp_preview.status_code, resp_preview.json() if resp_preview.status_code == 200 else resp_preview.text)
            
            print(f"\n--- Testing Execution ---")
            resp_exec = await client.post(f"{base_url}/agents/{agent_id}/execute")
            print("Execution Start Response:", resp_exec.status_code, resp_exec.json() if resp_exec.status_code == 200 else resp_exec.text)
            
    except Exception as e:
        print(f"Connection failed: {e}. Is the server running?")

if __name__ == '__main__':
    asyncio.run(main())
