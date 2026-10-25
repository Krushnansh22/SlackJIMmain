#!/usr/bin/env bash
# Starts worker + API + frontend. Requires Temporal dev server on localhost:7233
# (run `temporal server start-dev` or `docker compose up -d` first).
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
python worker.py & WORKER=$!
uvicorn main:app --host 0.0.0.0 --port 8000 & API=$!
cd "$ROOT/frontend"
[ -d node_modules ] || npm install
npm run dev -- --host & WEB=$!
trap "kill $WORKER $API $WEB 2>/dev/null" EXIT
wait
