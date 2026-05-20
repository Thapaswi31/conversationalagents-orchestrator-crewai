from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse

from app import schemas
from app.memory import redis_store
from app.session import ConversationalSession
from app import agents as agent_manager


SessionFactory = Callable[[str], ConversationalSession]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        await redis_store.redis_client.ping()
        app.state.redis_connected = True
    except Exception:
        app.state.redis_connected = False

    yield

    await redis_store.redis_client.aclose()


app = FastAPI(lifespan=lifespan)


def _session_factory() -> SessionFactory:
    return getattr(app.state, "session_factory", ConversationalSession)


@app.post("/chat", response_model=schemas.ChatResponse)
async def chat(request: schemas.ChatRequest) -> schemas.ChatResponse:
    session_id = request.session_id or str(uuid4())
    session = _session_factory()(session_id)

    try:
        try:
            reply = await session.process_message(request.message, agent_id=request.agent_id)
        except TypeError:
            # fallback for session implementations that expect only (message,)
            reply = await session.process_message(request.message)
        return schemas.ChatResponse(session_id=session_id, reply=reply, status="ok")
    except Exception as exc:
        return schemas.ChatResponse(
            session_id=session_id,
            reply=f"Chat processing failed: {exc}",
            status="error",
        )


@app.get("/chat/{session_id}/stream")
async def stream_chat(session_id: str, message: str | None = None) -> EventSourceResponse:
    async def events() -> AsyncIterator[dict[str, str]]:
        yield {
            "event": "progress",
            "data": f"Connected to stream for session {session_id}.",
        }

        if message is not None:
            yield {
                "event": "progress",
                "data": "Processing message.",
            }
                try:
                    session = _session_factory()(session_id)
                    try:
                        reply = await session.process_message(message)
                    except TypeError:
                        # fallback if older session expects only one arg
                        reply = await session.process_message(message)
                yield {
                    "event": "complete",
                    "data": reply,
                }
                return
            except Exception as exc:
                yield {
                    "event": "error",
                    "data": f"Chat processing failed: {exc}",
                }
                return

        yield {
            "event": "complete",
            "data": "Stream ready.",
        }

    return EventSourceResponse(events())


@app.post("/agents", response_model=schemas.AgentCreateResponse)
async def create_agent(request: schemas.AgentCreateRequest) -> schemas.AgentCreateResponse:
    try:
        definition = {
            "role": request.role,
            "goal": request.goal,
            "backstory": request.backstory or "",
            "tools": request.tools or [],
        }
        agent_id = await agent_manager.create_agent(definition)
        return schemas.AgentCreateResponse(agent_id=agent_id, status="ok")
    except Exception as exc:
        return schemas.AgentCreateResponse(agent_id="", status="error")


@app.get("/agents")
async def list_agents() -> dict:
    ids = await agent_manager.list_agent_ids()
    return {"agents": ids}


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict:
    definition = await agent_manager.get_agent_definition(agent_id)
    if not definition:
        return {"status": "not_found"}
    return {"status": "ok", "definition": definition}


@app.delete("/chat/{session_id}")
async def delete_chat(session_id: str) -> dict[str, str]:
    await redis_store.delete_session(session_id)
    return {"status": "ok"}


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        await redis_store.redis_client.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    return {"status": "ok", "redis": redis_status}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
