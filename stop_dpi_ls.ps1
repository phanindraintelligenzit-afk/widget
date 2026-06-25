Write-Host "Stopping DPI-LS Services..."

# Stop by exact process names where known
Stop-Process -Name "prometheus" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "grafana" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "uvicorn" -Force -ErrorAction SilentlyContinue

# For MLflow and FastAPI, they run via python/uv. Safest is to stop by port.
$PortsToClose = @(8000, 5000, 6006)

foreach ($Port in $PortsToClose) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            Write-Host "Killing process $($conn.OwningProcess) on port $Port"
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "Services stopped successfully."
