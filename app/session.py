from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from dotenv import load_dotenv
from litellm import acompletion

from app.agent import conversational_agent
from app.memory import redis_store
from app import agents as agent_manager


_APP_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_APP_ROOT / ".env")
os.environ.setdefault("CREWAI_STORAGE_DIR", str(_APP_ROOT / ".crewai-storage"))

_redis_url = os.environ.pop("REDIS_URL", None)
from crewai import Crew, Process, Task

if _redis_url is not None:
    os.environ["REDIS_URL"] = _redis_url


Message = dict[str, str]
Summarizer = Callable[[list[Message]], Awaitable[str]]


class HistoryStore(Protocol):
    async def get_history(self, session_id: str) -> list[Message]: ...

    async def save_history(self, session_id: str, history: list[Message]) -> None: ...


@dataclass
class RedisHistoryStore:
    async def get_history(self, session_id: str) -> list[Message]:
        return await redis_store.get_history(session_id)

    async def save_history(self, session_id: str, history: list[Message]) -> None:
        await redis_store.save_history(session_id, history)


class ConversationalSession:
    """Per-request session lifecycle backed by Redis transcript history."""

    def __init__(
        self,
        session_id: str,
        *,
        store: HistoryStore | None = None,
        crew_factory: Callable[[], Crew] | None = None,
        summarizer: Summarizer | None = None,
    ) -> None:
        self.session_id = session_id
        self.store = store or RedisHistoryStore()
        self.crew_factory = crew_factory or self._create_conversation_crew
        self.summarizer = summarizer or summarize_history

    async def process_message(self, message: str, agent_id: str | None = None) -> str:
        history = await self.store.get_history(self.session_id)
        history.append({"role": "user", "content": message})

        history = await self._summarize_if_needed(history)
        conversation_window = self._last_turns(history, turns=10)
        tool_context_window = self._last_turns(history, turns=2)

        # If an explicit agent_id is provided, instantiate a Crew that uses
        # that agent. Otherwise use the configured crew_factory.
        if agent_id:
            definition = await agent_manager.get_agent_definition(agent_id)
            if definition:
                # instantiate a single-agent crew for this conversation
                inst_agent = agent_manager.instantiate_agent_from_definition(definition)
                task = Task(
                    description=(
                        "Recent conversation context:\n{conversation_context}\n\n"
                        "Current user message:\n{user_message}\n\n"
                        "{tool_context_instruction}\n\n"
                        "Last 2 turns to pass to workflow tools when needed:\n"
                        "{tool_context}\n\n"
                        "IMPORTANT: Use attached tools when appropriate."
                    ),
                    expected_output="A helpful conversational reply to the user.",
                    agent=inst_agent,
                )
                crew = Crew(
                    agents=[inst_agent],
                    tasks=[task],
                    process=Process.sequential,
                    verbose=True,
                )
            else:
                crew = self.crew_factory()
        else:
            crew = self.crew_factory()
        result = await crew.kickoff_async(
            inputs={
                "user_message": message,
                "conversation_context": format_history(conversation_window),
                "tool_context": format_history(tool_context_window),
                "tool_context_instruction": (
                    "If you invoke research_workflow or data_analysis_workflow, "
                    "pass the last 2 turns via the tool's context parameter."
                ),
            }
        )

        reply = str(result)
        history.append({"role": "assistant", "content": reply})
        await self.store.save_history(self.session_id, history)
        return reply

    async def _summarize_if_needed(self, history: list[Message]) -> list[Message]:
        if count_turns(history) <= 20:
            return history

        keep_messages = self._last_turns(history, turns=10)
        older_messages = history[: len(history) - len(keep_messages)]
        summary = await self.summarizer(older_messages)
        return [
            {
                "role": "system",
                "content": f"Rolling summary of earlier conversation: {summary}",
            },
            *keep_messages,
        ]

    @staticmethod
    def _last_turns(history: list[Message], *, turns: int) -> list[Message]:
        message_count = turns * 2
        if len(history) <= message_count:
            return list(history)

        summary_messages = [
            message for message in history if message.get("role") == "system"
        ]
        recent_messages = history[-message_count:]
        return [*summary_messages, *recent_messages]

    @staticmethod
    def _create_conversation_crew() -> Crew:
        task = Task(
            description=(
                "Recent conversation context:\n{conversation_context}\n\n"
                "Current user message:\n{user_message}\n\n"
                "{tool_context_instruction}\n\n"
                "Last 2 turns to pass to workflow tools when needed:\n"
                "{tool_context}\n\n"
                "IMPORTANT RULES:\n"
                "- If the user asks to research, find facts, or summarize a topic: "
                "you MUST call the research_workflow tool. Do NOT answer from your own knowledge.\n"
                "- If the user provides data/numbers and asks for analysis: "
                "you MUST call the data_analysis_workflow tool. Do NOT analyze it yourself.\n"
                "- For casual chat (greetings, opinions, simple questions): respond directly without tools."
            ),
            expected_output="A helpful conversational reply to the user.",
            agent=conversational_agent,
        )
        return Crew(
            agents=[conversational_agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )


def count_turns(history: list[Message]) -> int:
    return sum(1 for message in history if message.get("role") == "user")


def format_history(history: list[Message]) -> str:
    if not history:
        return "(no previous conversation)"

    return "\n".join(
        f"{message.get('role', 'unknown')}: {message.get('content', '')}"
        for message in history
    )


async def summarize_history(history: list[Message]) -> str:
    model_name = os.getenv("OLLAMA_MODEL") or os.getenv("OPENAI_MODEL_NAME", "gpt-4o")
    response = await acompletion(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": (
                    "Compress this older chat history into a concise rolling "
                    "summary. Preserve user preferences, decisions, facts, "
                    "entities, and open questions."
                ),
            },
            {"role": "user", "content": format_history(history)},
        ],
    )
    return str(response.choices[0].message.content)
