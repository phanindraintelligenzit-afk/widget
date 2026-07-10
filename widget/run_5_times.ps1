Set-Location "d:\Projects\widget\widget"
$env:DPI_LS_NO_BLOCK = "1"
for ($i = 1; $i -le 5; $i++) {
    Write-Host "=== Run $i of 5 ===" -ForegroundColor Cyan
    .venv\Scripts\python.exe examples\test_agent.py 2>&1 | Out-Null
    Write-Host "=== Run $i complete ===" -ForegroundColor Green
    Start-Sleep -Seconds 3
}
Write-Host "All 5 runs complete" -ForegroundColor Cyan