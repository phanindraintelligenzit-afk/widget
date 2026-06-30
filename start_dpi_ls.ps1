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
Start-Process -FilePath "$GrafDir\grafana.exe" -ArgumentList "server --homepath .." -WorkingDirectory $GrafDir

# ================================================================
# 5. SigNoz — requires Docker Desktop to be running
# ================================================================
# SigNoz does NOT run as a standalone Windows binary.
# It requires Docker. To start SigNoz:
#
#   docker run -d --name signoz \
#     -p 8080:3301 \
#     -p 4317:4317 \
#     -p 4318:4318 \
#     signoz/signoz:latest
#
# OR use the official Docker Compose:
#   git clone https://github.com/SigNoz/signoz.git C:\signoz
#   cd C:\signoz\deploy
#   docker-compose up -d
#
# Once running, SigNoz UI is at: http://localhost:8080
# OTel traces (from test_agent.py) go to: http://localhost:4317
# ================================================================
Write-Host ""
Write-Host "=========================================="
Write-Host " SIGNOZ SETUP"
Write-Host "=========================================="
Write-Host " SigNoz requires Docker Desktop."
Write-Host " Run this in a new terminal:"
Write-Host ""
Write-Host "   docker run -d --name signoz -p 8080:3301 -p 4317:4317 -p 4318:4318 signoz/signoz:latest"
Write-Host ""
Write-Host " Then open: http://localhost:8080"
Write-Host "=========================================="
Write-Host ""

# Return to project root
Set-Location "D:\Projects\widget\widget"

Write-Host "Services have been initiated. Use URLs:"
Write-Host "  FastAPI:  http://127.0.0.1:8000"
Write-Host "  MLflow:   http://localhost:5000"
Write-Host "  Grafana:  http://localhost:3000"
Write-Host "  SigNoz:   http://localhost:8080 (Docker required)"
Write-Host ""
Write-Host "Run agent:"
Write-Host "  uv run python examples/test_agent.py"
