#!/usr/bin/env bash
# Hawsub One-Click Workstation Launcher
# Set up environment, start GUI workstation server, and open browser.

set -e

# Repository root directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "◈ Starting Hawsub Subtitle Workstation..."

# 1. Virtual environment check
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "⚠️ Virtual environment not found. Creating .venv..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
fi

# 2. Check for .env file
if [ ! -f ".env" ]; then
    echo "📝 Creating .env template from .env.example..."
    cp .env.example .env
    echo "💡 Add your API key (GOOGLE_API_KEY, OPENAI_API_KEY, etc.) to /Users/hawzhin/Hawsub/.env if needed."
fi

# 3. Determine available port
PORT=8080
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    PORT=8888
fi

echo "🚀 Launching Hawsub GUI on http://localhost:$PORT..."

# 4. Open browser after short delay in background
(sleep 1.5 && open "http://localhost:$PORT") &

# 5. Start Hawsub Workstation GUI
python3 -m hawsub.cli.main gui --port "$PORT"
