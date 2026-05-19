export function resolveApiBaseUrl(value) {
  const cleaned = String(value || "").trim().replace(/\/+$/, "");
  return cleaned || "/api";
}

export function createSessionId() {
  if (globalThis.crypto?.randomUUID) {
    return `session-${globalThis.crypto.randomUUID()}`;
  }

  return `session-${Date.now().toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 10)}`;
}

export function buildStreamUrl(apiBaseUrl, sessionId, message) {
  const params = new URLSearchParams({ message });
  return `${resolveApiBaseUrl(apiBaseUrl)}/chat/${encodeURIComponent(
    sessionId,
  )}/stream?${params.toString()}`;
}

export function parseSseEvents(text) {
  return String(text || "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split(/\n\n+/)
    .map((chunk) => {
      const lines = chunk.split(/\n/).filter(Boolean);
      if (lines.length === 0) {
        return null;
      }

      const eventLine = lines.find((line) => line.startsWith("event:"));
      const dataLines = lines.filter((line) => line.startsWith("data:"));

      return {
        event: eventLine ? eventLine.replace(/^event:\s*/, "").trim() : "message",
        data: dataLines.map((line) => line.replace(/^data:\s*/, "").trimEnd()).join("\n"),
      };
    })
    .filter(Boolean);
}

export async function getHealth(apiBaseUrl) {
  const response = await fetch(`${resolveApiBaseUrl(apiBaseUrl)}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with HTTP ${response.status}`);
  }
  return response.json();
}

export async function sendChatMessage(apiBaseUrl, { sessionId, message }) {
  const response = await fetch(`${resolveApiBaseUrl(apiBaseUrl)}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id: sessionId || null,
      message,
    }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed with HTTP ${response.status}`);
  }

  return response.json();
}

export async function deleteSession(apiBaseUrl, sessionId) {
  const response = await fetch(
    `${resolveApiBaseUrl(apiBaseUrl)}/chat/${encodeURIComponent(sessionId)}`,
    { method: "DELETE" },
  );

  if (!response.ok) {
    throw new Error(`Delete session failed with HTTP ${response.status}`);
  }

  return response.json();
}

export async function streamChatMessage(apiBaseUrl, { sessionId, message, onEvent }) {
  const response = await fetch(buildStreamUrl(apiBaseUrl, sessionId, message), {
    headers: {
      Accept: "text/event-stream",
    },
  });

  if (!response.ok) {
    throw new Error(`Stream request failed with HTTP ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("This browser does not support streamed response reading.");
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let finalData = "";

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    const chunks = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split(/\n\n+/);
    buffer = done ? "" : chunks.pop() || "";

    for (const event of parseSseEvents(chunks.join("\n\n"))) {
      onEvent?.(event);
      if (event.event === "complete") {
        finalData = event.data;
      }
      if (event.event === "error") {
        throw new Error(event.data);
      }
    }

    if (done) {
      for (const event of parseSseEvents(buffer)) {
        onEvent?.(event);
        if (event.event === "complete") {
          finalData = event.data;
        }
      }
      break;
    }
  }

  return finalData;
}

export function exportMessagesAsMarkdown(messages) {
  return messages
    .map((message) => {
      const role = message.role === "assistant" ? "Assistant" : "User";
      return `### ${role}\n\n${message.content}`;
    })
    .join("\n\n");
}
