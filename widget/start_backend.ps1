Set-Location "d:\Projects\widget\widget"
.venv\Scripts\python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8000 > backend.log 2>&1