import httpx
import sys

def main():
    try:
        r = httpx.post("http://127.0.0.1:8000/ingest", json={"agent_id": "e2e-agent"})
        print(r.status_code)
        print(r.text)
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    main()
