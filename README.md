# Conversational Agent

A FastAPI conversational agent built on CrewAI with Redis-backed session history, specialist research and data-analysis crews, async request handling, and an optional Streamlit chat UI.

## What It Does

- Handles normal multi-turn chat with per-session Redis history.
- Routes research requests to a CrewAI research workflow backed by `SerperDevTool`.
- Routes data and metrics questions to a CrewAI analysis workflow.
- Passes recent conversation context into workflow tools so sub-crews can use prior turns.
- Uses `kickoff_async()` from the request lifecycle so long-running CrewAI work does not block the FastAPI server.
- Provides HTTP endpoints for chat, SSE progress streaming, session deletion, and health checks.

## Project Layout

```text
app/
  main.py                  FastAPI app, lifespan, routes
  schemas.py               Pydantic request/response models
  agent.py                 Shared CrewAI conversational agent singleton
  session.py               Per-request session lifecycle and history handling
  crews/
    research_crew.py       Researcher + writer crew
    analysis_crew.py       Analyst + reporter crew
  tools/
    research_tool.py       CrewAI tool wrapper for research crew
    analysis_tool.py       CrewAI tool wrapper for analysis crew
  memory/
    redis_store.py         Async Redis transcript store
tests/                     Unit, integration, and deterministic E2E tests
streamlit_app.py           Optional Streamlit frontend
requirements.txt           Python dependencies
```

## Requirements

- Python 3.12 recommended
- Redis running locally or reachable through `REDIS_URL`
- OpenAI-compatible model configuration for CrewAI/LiteLLM
- Serper API key for live research web search

Install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Environment

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL_NAME=gpt-4o
REDIS_URL=redis://localhost:6379
SERPER_API_KEY=...
```

For local Ollama-style usage, the code also reads:

```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=ollama/model-name
```

Redis check:

```bash
redis-cli ping
```

Expected response:

```text
PONG
```
## start ollama
ollama serve

## Run The API

```bash
uv run uvicorn app.main:app --reload
```

The API runs at:

```text
http://localhost:8000
```

## Run the streamlit

```bash
uv run streamlit run streamlit_app.py
```
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
Network URL: http://100.64.0.1:8501

## API Endpoints

### Health

```bash
curl http://localhost:8000/health
```

Response:

```json
{"status":"ok","redis":"connected"}
```

### Chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello"}'
```

Response:

```json
{
  "session_id": "generated-session-id",
  "reply": "assistant reply",
  "status": "ok"
}
```

Continue an existing session:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"abc123","message":"What did I just tell you?"}'
```

### SSE Stream

```bash
curl -N "http://localhost:8000/chat/abc123/stream?message=research%20vector%20databases"
```

The stream emits progress events and a final completion event.

### Delete Session

```bash
curl -X DELETE http://localhost:8000/chat/abc123
```

Response:

```json
{"status":"ok"}
```

## Optional Streamlit UI

Start the FastAPI server first, then run:

```bash
streamlit run streamlit_app.py
```

The Streamlit app sends messages to `http://localhost:8000/chat`.

## How The Conversation Flow Works

1. `POST /chat` receives a `session_id` and message. If no `session_id` is provided, the API generates one.
2. `ConversationalSession` loads the transcript from Redis.
3. The new user message is appended.
4. Older history is summarized when the session exceeds 20 user turns.
5. The last 10 turns are passed as conversation context to the conversational CrewAI task.
6. The agent replies directly or invokes one of the workflow tools.
7. Tool calls receive the last 2 turns as explicit context.
8. The assistant reply is appended and saved back to Redis with a 1-hour TTL.

## Memory And Storage

This project uses two different storage layers. They solve different problems and should not be treated as interchangeable.

### Redis Session History

Redis stores the literal chat transcript for each user session. The key format is:

```text
session:{session_id}:history
```

Each value is a JSON list of messages:

```json
[
  {"role": "user", "content": "My project is Aurora."},
  {"role": "assistant", "content": "Got it."}
]
```

The Redis logic lives in `app/memory/redis_store.py`:

- `get_history(session_id)` loads the transcript and returns `[]` if nothing exists.
- `save_history(session_id, history)` serializes the transcript to JSON and saves it with a TTL.
- `delete_session(session_id)` deletes the transcript immediately.

The TTL is currently:

```text
3600 seconds
```

That means inactive sessions expire after about 1 hour. A new message on the same `session_id` saves the latest transcript again and refreshes the TTL.

### Session Lifecycle

`ConversationalSession` is created per request. It is not a long-lived user object.

For every incoming message:

1. Load history from Redis by `session_id`.
2. Append the new user message.
3. If the session has more than 20 user turns, summarize older messages.
4. Send the last 10 turns to the conversational agent as context.
5. Send the last 2 turns as explicit context if a workflow tool is invoked.
6. Await the CrewAI conversation crew through `kickoff_async()`.
7. Append the assistant reply.
8. Save the updated transcript back to Redis.

This keeps session state isolated by `session_id`. Two users with different session IDs get different Redis keys, so their transcript histories do not mix.

### Rolling Summary

Long sessions can become expensive because every turn adds tokens. To control that, `app/session.py` summarizes older history after 20 user turns.

The stored history then becomes:

```json
[
  {"role": "system", "content": "Rolling summary of earlier conversation: ..."},
  {"role": "user", "content": "recent message"},
  {"role": "assistant", "content": "recent reply"}
]
```

The summary preserves earlier facts, preferences, decisions, entities, and open questions while keeping the active context window small.

### CrewAI Storage And ChromaDB

CrewAI can create local storage files for memory, task outputs, embeddings, and related runtime state. In this project, the storage directory is forced into the repository folder:

```text
.crewai-storage/
```

That setting appears in the app modules through:

```python
os.environ.setdefault("CREWAI_STORAGE_DIR", str(_APP_ROOT / ".crewai-storage"))
```

When CrewAI memory or task-output storage is active, CrewAI and its dependencies may create local files there, including SQLite or ChromaDB-related data. ChromaDB is the vector-store layer CrewAI can use for semantic memory and retrieval-style storage.

Important distinction:

- Redis stores exact per-session chat transcripts.
- `.crewai-storage` stores CrewAI runtime artifacts, task outputs, and possible semantic/vector memory data.

Redis is the source of truth for session restore in this app. `.crewai-storage` is local CrewAI runtime storage and should not be relied on as the per-user transcript store.

### What To Commit

Safe to commit:

- `app/`
- `tests/`
- `README.md`
- `requirements.txt`
- `.env.example`
- `.gitignore`

Do not commit:

- `.env`
- `venv/`
- `.crewai-storage/`
- `__pycache__/`
- local database files such as `*.db`, `*.sqlite`, `*.sqlite3`

These are already covered by `.gitignore`.

## Crews

### Research Crew

`app/crews/research_crew.py`

- `Senior Research Analyst`: uses `SerperDevTool` for web search.
- `Technical Content Writer`: turns research notes into concise markdown.
- Standalone kickoff supports missing `context` by defaulting it to an empty string.

### Data Analysis Crew

`app/crews/analysis_crew.py`

- `Data Analyst`: identifies patterns, anomalies, and answers grounded in provided data.
- `Business Reporter`: converts findings into plain-English business insight.
- Standalone kickoff supports missing `context` by defaulting it to an empty string.

## Testing

Run all deterministic tests:

```bash
venv/bin/python -m unittest discover tests
```

Run live research crew tests only when real API keys are configured:

```bash
RUN_LIVE_RESEARCH_CREW=1 venv/bin/python -m unittest tests.test_research_crew_live
```

Run live analysis crew tests:

```bash
RUN_LIVE_ANALYSIS_CREW=1 venv/bin/python -m unittest tests.test_analysis_crew_live
```

The deterministic suite uses fakes for Redis, sessions, and crews where needed so normal CI-style runs do not depend on live LLM calls.

## Notes

- The CrewAI conversational agent in `app/agent.py` is a module-level singleton.
- Session-specific literal transcript memory lives in Redis, keyed by `session_id`.
- CrewAI semantic memory is controlled by the `memory` flag in `app/agent.py`; Redis keeps per-user/session transcript history isolated.
- `CREWAI_STORAGE_DIR` is set to `.crewai-storage` so CrewAI local storage stays inside the project.
