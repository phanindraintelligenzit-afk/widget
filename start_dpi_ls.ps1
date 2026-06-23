$ErrorActionPreference = "Stop"
Write-Host "Starting DPI-LS Services..."

# Navigate to project root
Set-Location "D:\Projects\widget\widget"

# 1. FastAPI (Port 8000)
Write-Host "Starting FastAPI..."
Start-Process -FilePath "uv" -ArgumentList "run uvicorn api.app:app --host 127.0.0.1 --port 8000"

# 2. MLflow (Port 5000)
Write-Host "Starting MLflow..."
Start-Process -FilePath "uv" -ArgumentList "run mlflow server --host 127.0.0.1 --port 5000"

# 3. Prometheus (Port 9090)
Write-Host "Starting Prometheus..."
$PromDir = "C:\Users\User\Downloads\prometheus-3.12.0.windows-amd64\prometheus-3.12.0.windows-amd64"
Start-Process -FilePath "$PromDir\prometheus.exe" -ArgumentList "--config.file=prometheus.yml --web.listen-address=127.0.0.1:9090" -WorkingDirectory $PromDir

# 4. Grafana (Port 3000)
Write-Host "Starting Grafana..."
$GrafDir = "C:\Users\User\Downloads\grafana_13.0.2_26816849631_windows_amd64\grafana-13.0.2\bin"
Start-Process -FilePath "$GrafDir\grafana.exe" -ArgumentList "server --homepath `"..\`"" -WorkingDirectory $GrafDir

# Return to project root
Set-Location "D:\Projects\widget\widget"

Write-Host "Services have been initiated in separate terminal windows."
