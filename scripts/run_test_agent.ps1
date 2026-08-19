Set-Location "D:\DPI-LS\widget"
$env:DPI_LS_NO_BLOCK = "1"
.venv\Scripts\python.exe examples\test_agent.py > test_agent_run.log 2>&1