# ☕ Mauji Cafe SOS Bribe Board (POC)

Voice-driven, durable, live help desk for hackathons.
React (Vite) + Tailwind · FastAPI · Temporal (Python SDK) · Wispr Flow / Web Speech.

## Prerequisites
- Python 3.10+, Node 18+
- Temporal dev server: `temporal server start-dev` **or** `docker compose up -d`
  (UI at http://localhost:8233)

## Run (3 terminals)
```bash
# 1) Worker
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python worker.py

# 2) API
cd backend && source .venv/bin/activate
uvicorn main:app --port 8000

# 3) Frontend
cd frontend && npm install && npm run dev
```
Or all-in-one: `./run.sh`. Open http://localhost:5173 (use `--host` for phones on the same Wi-Fi).

## Voice
- Mic button uses the browser Speech API (Chrome/Edge/Safari).
- Wispr Flow: focus the textarea and dictate with your Wispr Flow hotkey.

## Flow
`OPEN` → (Claim) → `CLAIMED` → (creator clicks Resolved) → `RESOLVED` (workflow completes).
State lives only in Temporal; the API reads it via workflow queries and sends signals.

## Demo flex
Claim a ticket, kill the FastAPI process (and/or worker), restart it - the ticket is still `CLAIMED`.

## API
- `POST /api/tickets` `{creator_name, raw_transcription}`
- `GET /api/tickets`
- `POST /api/tickets/{id}/claim` `{name}`
- `POST /api/tickets/{id}/resolve` `{name}` (creator only)
