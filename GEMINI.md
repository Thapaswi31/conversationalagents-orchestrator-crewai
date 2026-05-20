# Conversational Agent

## Project Overview
This project is a FastAPI-based conversational agent built on CrewAI. It features a Redis-backed session history for multi-turn chat, specialist research and data-analysis crews, and async request handling. An optional Streamlit chat UI is also provided.

Key Technologies:
- **Python**: >=3.12
- **Framework**: FastAPI (API server), Streamlit (Frontend UI)
- **Agent/LLM**: CrewAI, LiteLLM, Langchain, OpenAI
- **Storage/Memory**: Redis (for session transcripts), ChromaDB/CrewAI local storage (for semantic/vector memory)
- **Package Management**: `uv` (via `uv run` and `pyproject.toml`)

Architecture highlights:
- **API (FastAPI)**: Exposes endpoints for chat, health checks, and Server-Sent Events (SSE) streams (`app/main.py`).
- **Session Management**: Per-request session lifecycle handling using Redis for transcript storage (`app/session.py`, `app/memory/redis_store.py`).
- **CrewAI Crews**: Includes distinct workflows for research (backed by SerperDevTool) and data analysis (`app/crews/`).
- **Tools**: Wrapper tools to enable the main agent to interact with the specialized sub-crews (`app/tools/`).

## Building and Running

### Prerequisites
- Python 3.12+
- Redis server running locally or accessible via `REDIS_URL`.
- An OpenAI-compatible model API key (e.g., `OPENAI_API_KEY`) and a Serper API key (`SERPER_API_KEY`) for live web search capabilities.

### Environment Setup
Create a `.env` file in the root:
```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL_NAME=gpt-4o
REDIS_URL=redis://localhost:6379
SERPER_API_KEY=...
# Optional Ollama usage:
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=ollama/model-name
```

### Running the Application

**Run the API Server (FastAPI):**
```bash
uv run uvicorn app.main:app --reload
```
The API will be available at `http://localhost:8000`.

**Run the Streamlit UI:**
Ensure the FastAPI server is running first, then start the frontend:
```bash
uv run streamlit run streamlit_app.py
```
The UI will be accessible in the browser at `http://localhost:8501`.

## Development Conventions & Testing

- **Testing Strategy**: The project utilizes both deterministic unit/integration tests (using fakes/mocks) and live end-to-end tests (which require real API keys).
- **Run Unit Tests**:
  ```bash
  python -m unittest discover tests
  ```
- **Run Live Tests**:
  ```bash
  RUN_LIVE_RESEARCH_CREW=1 python -m unittest tests.test_research_crew_live
  RUN_LIVE_ANALYSIS_CREW=1 python -m unittest tests.test_analysis_crew_live
  ```
- **Architecture & Design Notes**:
  - The primary CrewAI conversational agent (`app/agent.py`) operates as a module-level singleton.
  - Per-user/session history is strictly managed and isolated in Redis, bypassing local CrewAI memory for session restoration.
  - Long sessions summarize history after 20 user turns to minimize token usage.
  - CrewAI's local runtime storage is forcefully routed to `.crewai-storage/` inside the project root and is ignored in git.
