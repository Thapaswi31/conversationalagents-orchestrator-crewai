import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Bot,
  CheckCircle2,
  Clipboard,
  Download,
  Eraser,
  Gauge,
  Loader2,
  MessageSquarePlus,
  RefreshCw,
  Search,
  Send,
  Settings,
  Sparkles,
  Trash2,
  User,
  WifiOff,
} from "lucide-react";

import {
  createSessionId,
  deleteSession,
  exportMessagesAsMarkdown,
  getHealth,
  sendChatMessage,
  streamChatMessage,
} from "./lib/apiClient.js";
import "./styles.css";

const STORAGE_KEY = "conversational-agent-console";

const quickPrompts = [
  {
    title: "General Chat",
    icon: MessageSquarePlus,
    text: "Help me think through this problem: ",
  },
  {
    title: "Research",
    icon: Search,
    text: "Research and summarize the latest context about ",
  },
  {
    title: "Data Analysis",
    icon: Gauge,
    text: "Analyze this data and identify trends, anomalies, and the main takeaway:\n\n",
  },
  {
    title: "Status Summary",
    icon: Activity,
    text: "Summarize what we have discussed so far and list open questions.",
  },
];

function loadInitialState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    return {
      apiBaseUrl: saved.apiBaseUrl || "/api",
      sessionId: saved.sessionId || createSessionId(),
      messages: Array.isArray(saved.messages) ? saved.messages : [],
      streaming: saved.streaming ?? true,
    };
  } catch {
    return {
      apiBaseUrl: "/api",
      sessionId: createSessionId(),
      messages: [],
      streaming: true,
    };
  }
}

function App() {
  const initialState = useMemo(loadInitialState, []);
  const [apiBaseUrl, setApiBaseUrl] = useState(initialState.apiBaseUrl);
  const [sessionId, setSessionId] = useState(initialState.sessionId);
  const [messages, setMessages] = useState(initialState.messages);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(initialState.streaming);
  const [health, setHealth] = useState({ status: "checking", redis: "unknown" });
  const [progress, setProgress] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState("");
  const [copyState, setCopyState] = useState("");
  const transcriptRef = useRef(null);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ apiBaseUrl, sessionId, messages, streaming }),
    );
  }, [apiBaseUrl, sessionId, messages, streaming]);

  useEffect(() => {
    transcriptRef.current?.scrollTo({
      top: transcriptRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, progress]);

  useEffect(() => {
    void refreshHealth();
  }, [apiBaseUrl]);

  async function refreshHealth() {
    try {
      setHealth({ status: "checking", redis: "unknown" });
      const result = await getHealth(apiBaseUrl);
      setHealth(result);
    } catch (healthError) {
      setHealth({ status: "error", redis: "unreachable" });
      setError(healthError.message);
    }
  }

  async function submitMessage(messageText = input) {
    const trimmed = messageText.trim();
    if (!trimmed || isBusy) {
      return;
    }

    setInput("");
    setError("");
    setProgress("");
    setIsBusy(true);

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
      createdAt: new Date().toISOString(),
    };
    setMessages((current) => [...current, userMessage]);

    try {
      if (streaming) {
        const reply = await streamChatMessage(apiBaseUrl, {
          sessionId,
          message: trimmed,
          onEvent: (event) => {
            if (event.event === "progress") {
              setProgress(event.data);
            }
          },
        });

        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: reply || "Stream completed without a reply.",
            createdAt: new Date().toISOString(),
          },
        ]);
      } else {
        const response = await sendChatMessage(apiBaseUrl, {
          sessionId,
          message: trimmed,
        });

        setSessionId(response.session_id || sessionId);
        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: response.reply,
            status: response.status,
            createdAt: new Date().toISOString(),
          },
        ]);
      }
    } catch (requestError) {
      setError(requestError.message);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `Request failed: ${requestError.message}`,
          status: "error",
          createdAt: new Date().toISOString(),
        },
      ]);
    } finally {
      setProgress("");
      setIsBusy(false);
    }
  }

  function startNewSession() {
    setSessionId(createSessionId());
    setMessages([]);
    setProgress("");
    setError("");
  }

  async function removeServerSession() {
    setError("");
    try {
      await deleteSession(apiBaseUrl, sessionId);
      startNewSession();
    } catch (deleteError) {
      setError(deleteError.message);
    }
  }

  function retryLastUserMessage() {
    const lastUserMessage = [...messages].reverse().find((message) => message.role === "user");
    if (lastUserMessage) {
      void submitMessage(lastUserMessage.content);
    }
  }

  async function copySessionId() {
    await navigator.clipboard.writeText(sessionId);
    setCopyState("Copied");
    window.setTimeout(() => setCopyState(""), 1200);
  }

  function exportTranscript(format) {
    const content =
      format === "json"
        ? JSON.stringify({ sessionId, messages }, null, 2)
        : exportMessagesAsMarkdown(messages);
    const blob = new Blob([content], {
      type: format === "json" ? "application/json" : "text/markdown",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `conversation-${sessionId}.${format === "json" ? "json" : "md"}`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const healthOk = health.status === "ok";

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Bot size={22} />
          </div>
          <div>
            <h1>Agent Console</h1>
            <p>FastAPI workspace</p>
          </div>
        </div>

        <section className="panel compact">
          <div className="panel-title">
            {healthOk ? <CheckCircle2 size={18} /> : <WifiOff size={18} />}
            <span>Backend</span>
          </div>
          <div className={`status-pill ${healthOk ? "ok" : "warn"}`}>
            API {health.status} · Redis {health.redis}
          </div>
          <button className="secondary-button" type="button" onClick={refreshHealth}>
            <RefreshCw size={16} />
            Refresh
          </button>
        </section>

        <section className="panel">
          <div className="panel-title">
            <Settings size={18} />
            <span>Session</span>
          </div>
          <label className="field">
            <span>Session ID</span>
            <input value={sessionId} onChange={(event) => setSessionId(event.target.value)} />
          </label>
          <div className="button-row">
            <button className="secondary-button" type="button" onClick={copySessionId}>
              <Clipboard size={16} />
              {copyState || "Copy"}
            </button>
            <button className="secondary-button" type="button" onClick={startNewSession}>
              <MessageSquarePlus size={16} />
              New
            </button>
          </div>
          <button className="danger-button" type="button" onClick={removeServerSession}>
            <Trash2 size={16} />
            Delete Server Session
          </button>
        </section>

        <section className="panel">
          <div className="panel-title">
            <Sparkles size={18} />
            <span>Quick Prompts</span>
          </div>
          <div className="prompt-list">
            {quickPrompts.map((prompt) => {
              const Icon = prompt.icon;
              return (
                <button
                  className="prompt-button"
                  key={prompt.title}
                  type="button"
                  onClick={() => setInput(prompt.text)}
                >
                  <Icon size={16} />
                  <span>{prompt.title}</span>
                </button>
              );
            })}
          </div>
        </section>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Conversational Agent</p>
            <h2>Chat, stream, inspect, and manage sessions</h2>
          </div>
          <div className="topbar-actions">
            <label className="toggle">
              <input
                checked={streaming}
                type="checkbox"
                onChange={(event) => setStreaming(event.target.checked)}
              />
              <span>Streaming</span>
            </label>
            <button
              className="icon-button"
              type="button"
              title="Export Markdown"
              onClick={() => exportTranscript("md")}
              disabled={messages.length === 0}
            >
              <Download size={18} />
            </button>
            <button
              className="icon-button"
              type="button"
              title="Clear local transcript"
              onClick={() => setMessages([])}
              disabled={messages.length === 0}
            >
              <Eraser size={18} />
            </button>
          </div>
        </header>

        {error ? <div className="error-banner">{error}</div> : null}

        <div className="transcript" ref={transcriptRef}>
          {messages.length === 0 ? (
            <div className="empty-state">
              <Bot size={42} />
              <h3>Start a conversation</h3>
              <p>
                Ask directly, use a quick prompt, or switch streaming off to compare the
                standard chat endpoint.
              </p>
            </div>
          ) : (
            messages.map((message) => <MessageBubble key={message.id} message={message} />)
          )}

          {isBusy ? (
            <div className="thinking">
              <Loader2 className="spin" size={18} />
              <span>{progress || "Agent is thinking..."}</span>
            </div>
          ) : null}
        </div>

        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault();
            void submitMessage();
          }}
        >
          <textarea
            value={input}
            placeholder="Type a message, paste data, or ask for research..."
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void submitMessage();
              }
            }}
          />
          <div className="composer-actions">
            <button
              className="secondary-button"
              type="button"
              onClick={() => exportTranscript("json")}
              disabled={messages.length === 0}
            >
              <Download size={16} />
              JSON
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={retryLastUserMessage}
              disabled={isBusy || !messages.some((message) => message.role === "user")}
            >
              <RefreshCw size={16} />
              Retry
            </button>
            <button className="primary-button" type="submit" disabled={isBusy || !input.trim()}>
              {isBusy ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
              Send
            </button>
          </div>
        </form>
      </section>

      <aside className="inspector">
        <section className="panel">
          <div className="panel-title">
            <Settings size={18} />
            <span>API Settings</span>
          </div>
          <label className="field">
            <span>Base URL</span>
            <input value={apiBaseUrl} onChange={(event) => setApiBaseUrl(event.target.value)} />
          </label>
          <p className="hint">
            Use <code>/api</code> with Vite proxy for local development against FastAPI.
          </p>
        </section>

        <section className="panel">
          <div className="panel-title">
            <Activity size={18} />
            <span>Endpoint Map</span>
          </div>
          <dl className="endpoint-list">
            <div>
              <dt>Health</dt>
              <dd>GET /health</dd>
            </div>
            <div>
              <dt>Chat</dt>
              <dd>POST /chat</dd>
            </div>
            <div>
              <dt>Stream</dt>
              <dd>GET /chat/:id/stream</dd>
            </div>
            <div>
              <dt>Delete</dt>
              <dd>DELETE /chat/:id</dd>
            </div>
          </dl>
        </section>

        <section className="panel">
          <div className="panel-title">
            <Sparkles size={18} />
            <span>Transcript</span>
          </div>
          <div className="metric-grid">
            <div>
              <strong>{messages.filter((message) => message.role === "user").length}</strong>
              <span>User turns</span>
            </div>
            <div>
              <strong>{messages.filter((message) => message.role === "assistant").length}</strong>
              <span>Replies</span>
            </div>
          </div>
        </section>
      </aside>
    </main>
  );
}

function MessageBubble({ message }) {
  const isAssistant = message.role === "assistant";
  return (
    <article className={`message ${isAssistant ? "assistant" : "user"}`}>
      <div className="avatar">{isAssistant ? <Bot size={18} /> : <User size={18} />}</div>
      <div className="message-body">
        <div className="message-meta">
          <span>{isAssistant ? "Assistant" : "You"}</span>
          {message.status === "error" ? <span className="error-text">Error</span> : null}
        </div>
        <p>{message.content}</p>
      </div>
    </article>
  );
}

createRoot(document.getElementById("root")).render(<App />);
