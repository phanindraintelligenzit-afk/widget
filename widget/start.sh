#!/bin/bash
set -e

# Railway provides PORT, default to 8000
PORT=${PORT:-8000}

# Railway ephemeral SQLite db location
export DATABASE_URL=${DATABASE_URL:-"sqlite:////app/data/dpi_ls.db"}

# Start the uvicorn server
echo "Starting DPI-LS on port $PORT"
exec uvicorn api.app:app --host 0.0.0.0 --port $PORT