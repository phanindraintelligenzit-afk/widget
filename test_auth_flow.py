import httpx
import asyncio
import jwt
import time
import uuid

SECRET_KEY = "SUPER_SECRET_JWT_KEY_FOR_DPI_LS"
ALGORITHM = "HS256"

def create_token(username: str, role: str = "USER"):
    return jwt.encode({"sub": username, "role": role}, SECRET_KEY, algorithm=ALGORITHM)

async def test_auth():
    base_url = "http://127.0.0.1:8000"
    user_a_token = create_token("user_a")
    user_b_token = create_token("user_b")
    admin_token = create_token("admin", "ADMIN")
    
    agent_id = f"agent-{uuid.uuid4().hex[:6]}"
    
    async with httpx.AsyncClient() as client:
        print("--- 1. User A creates Agent ---")
        res = await client.post(
            f"{base_url}/api/agents",
            json={"agent_id": agent_id, "agent_name": "User A Agent"},
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        print("Create Status:", res.status_code)
        
        print("\n--- 2. User A accesses Agent ---")
        res = await client.get(
            f"{base_url}/api/agents/{agent_id}/config",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        print("User A Get Config Status:", res.status_code)
        
        print("\n--- 3. User B accesses Agent (Should be 403) ---")
        res = await client.get(
            f"{base_url}/api/agents/{agent_id}/config",
            headers={"Authorization": f"Bearer {user_b_token}"}
        )
        print("User B Get Config Status:", res.status_code)
        
        print("\n--- 4. Admin accesses Agent ---")
        res = await client.get(
            f"{base_url}/api/agents/{agent_id}/config",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        print("Admin Get Config Status:", res.status_code)

if __name__ == "__main__":
    asyncio.run(test_auth())
