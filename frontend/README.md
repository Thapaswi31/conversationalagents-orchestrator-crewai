# Conversational Agent Frontend

React/Vite frontend for the existing FastAPI conversational agent backend.

## Run locally

Start the FastAPI backend from the repository root:

```bash
uv run uvicorn app.main:app --reload
```

Then start this frontend:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

The frontend uses `/api` by default. Vite proxies `/api/*` to `http://localhost:8000/*`, so the browser does not need direct CORS access to the backend during local development.

## Features

- Chat through `POST /chat`
- Stream via `GET /chat/{session_id}/stream`
- Backend health check via `GET /health`
- Delete server-side session via `DELETE /chat/{session_id}`
- Local session persistence
- Quick prompts for chat, research, data analysis, and status summaries
- Export transcript as Markdown or JSON
