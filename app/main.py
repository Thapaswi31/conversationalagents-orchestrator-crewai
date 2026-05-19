from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse

from app import schemas
from app.memory import redis_store
from app.session import ConversationalSession


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
