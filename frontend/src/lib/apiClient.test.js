import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  buildStreamUrl,
  createSessionId,
  exportMessagesAsMarkdown,
  parseSseEvents,
  resolveApiBaseUrl,
} from "./apiClient.js";

describe("apiClient helpers", () => {
  it("uses the Vite proxy by default", () => {
    assert.equal(resolveApiBaseUrl(""), "/api");
  });

  it("normalizes configured API base URLs", () => {
    assert.equal(resolveApiBaseUrl("http://localhost:8000/"), "http://localhost:8000");
  });

  it("builds encoded stream URLs", () => {
    const url = buildStreamUrl("/api", "session 1", "research vector databases");
    assert.equal(
      url,
      "/api/chat/session%201/stream?message=research+vector+databases",
    );
  });

  it("parses server-sent event chunks", () => {
    const events = parseSseEvents(
      "event: progress\ndata: Processing message.\n\n" +
        "event: complete\ndata: Done\n\n",
    );

    assert.deepEqual(events, [
      { event: "progress", data: "Processing message." },
      { event: "complete", data: "Done" },
    ]);
  });

  it("parses server-sent events that use CRLF line endings", () => {
    const events = parseSseEvents(
      "event: progress\r\ndata: Processing message.\r\n\r\n" +
        "event: complete\r\ndata: Done\r\n\r\n",
    );

    assert.deepEqual(events, [
      { event: "progress", data: "Processing message." },
      { event: "complete", data: "Done" },
    ]);
  });

  it("creates markdown exports from messages", () => {
    const markdown = exportMessagesAsMarkdown([
      { role: "user", content: "Hello" },
      { role: "assistant", content: "Hi there" },
    ]);

    assert.equal(markdown, "### User\n\nHello\n\n### Assistant\n\nHi there");
  });

  it("creates browser-safe session ids", () => {
    assert.match(createSessionId(), /^session-[a-z0-9-]+$/);
  });
});
