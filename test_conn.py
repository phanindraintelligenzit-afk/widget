import os
import httpx
import logging

def check_langfuse():
    host = os.environ.get("LANGFUSE_HOST")
    pk = os.environ.get("LANGFUSE_PUBLIC_KEY")
    sk = os.environ.get("LANGFUSE_SECRET_KEY")
    
    if not host or not pk or not sk:
        return "BLOCKED", "Missing LANGFUSE_HOST, PUBLIC_KEY or SECRET_KEY in environment"
    if "rotated" in pk or "rotated" in sk:
        return "BLOCKED", "Found dummy/rotated credentials. Cannot authenticate."
        
    try:
        url = f"{host.rstrip('/')}/api/public/health"
        r = httpx.get(url, timeout=5.0)
        r.raise_for_status()
        return "REAL", "Connection successful"
    except Exception as e:
        return "FAILED", f"Connection failed: {str(e)}"

def check_sentry():
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return "NOT_CONFIGURED", "Missing SENTRY_DSN"
    if "rotated" in dsn:
        return "BLOCKED", "Found dummy/rotated credentials."
    return "FAILED", "Sentry connection check requires active client"

print("Langfuse check:", check_langfuse())
print("Sentry check:", check_sentry())
