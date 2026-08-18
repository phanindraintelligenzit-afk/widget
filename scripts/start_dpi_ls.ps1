$ErrorActionPreference = "Stop"
Write-Host "Starting DPI-LS Services..."

# Navigate to project root
Set-Location "D:\DPI-LS\widget"

# 1. FastAPI (Port 8000)
Write-Host "Starting FastAPI..."
Start-Process -FilePath "uv" -ArgumentList "run uvicorn api.app:app --host 127.0.0.1 --port 8000"

# 2. (Removed MLflow)

# 3. Prometheus (Port 9090)
Write-Host "Starting Prometheus..."
$PromDir = "C:\Users\User\Downloads\prometheus-3.12.0.windows-amd64\prometheus-3.12.0.windows-amd64"
Start-Process -FilePath "$PromDir\prometheus.exe" -ArgumentList "--config.file=D:\DPI-LS\widget\prometheus.yml --web.listen-address=127.0.0.1:9090" -WorkingDirectory $PromDir

# 4. Grafana (Port 3000)
Write-Host "Starting Grafana..."
$GrafDir = "C:\Users\User\Downloads\grafana_13.0.2_26816849631_windows_amd64\grafana-13.0.2\bin"
Start-Process -FilePath "$GrafDir\grafana.exe" -ArgumentList "server --homepath .." -WorkingDirectory $GrafDir

# ================================================================
# 5. Jaeger â€” requires Docker Desktop
# ================================================================
# docker run -d --name jaeger \
#   -e COLLECTOR_ZIPKIN_HOST_PORT=:9411 \
#   -p 5775:5775/udp \
#   -p 6831:6831/udp \
#   -p 6832:6832/udp \
#   -p 5778:5778 \
#   -p 16686:16686 \
#   -p 14268:14268 \
#   -p 14250:14250 \
#   -p 9411:9411 \
#   jaegertracing/all-in-one:latest
#
# ================================================================
# 6. Zipkin â€” requires Docker Desktop
# ================================================================
# docker run -d --name zipkin -p 9411:9411 openzipkin/zipkin:latest
# ================================================================
Write-Host ""
Write-Host "=========================================="
Write-Host " JAEGER & ZIPKIN SETUP"
Write-Host "=========================================="
Write-Host " Jaeger & Zipkin require Docker Desktop."
Write-Host " Run these in a new terminal:"
Write-Host ""
Write-Host "   docker run -d --name jaeger -p 16686:16686 -p 14268:14268 jaegertracing/all-in-one:latest"
Write-Host "   docker run -d --name zipkin -p 9411:9411 openzipkin/zipkin:latest"
Write-Host ""
Write-Host " Then open: http://localhost:16686 (Jaeger)"
Write-Host " Then open: http://localhost:9411 (Zipkin)"
Write-Host "=========================================="
Write-Host ""

# Return to project root
Set-Location "D:\DPI-LS\widget"

Write-Host "Services have been initiated. Use URLs:"
Write-Host "  FastAPI:  http://127.0.0.1:8000"
Write-Host "  Jaeger:   http://localhost:16686 (Docker required)"
Write-Host "  Zipkin:   http://localhost:9411 (Docker required)"
Write-Host ""
Write-Host "Run agent:"
Write-Host "  uv run python examples/test_agent.py"
