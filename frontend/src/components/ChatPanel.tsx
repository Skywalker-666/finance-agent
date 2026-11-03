import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ChatMessage, Transaction } from "../types";
import ChartView from "./ChartView";

const SUGGESTIONS = [
  "Where did I spend the most?",
  "How is my food spending trending by month?",
  "What will I spend next month?",
  "Can I afford a ₹15,000 trip?",
];

export default function ChatPanel({ txns }: { txns: Transaction[] }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  // Braces matter: newer browsers return a Promise from scrollIntoView, and React
  // would treat a returned value as the effect's cleanup function and crash.
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    const history = messages;
    setMessages((m) => [...m, { role: "user", content: q }]);
    setInput("");
    setBusy(true);
    try {
      const r = await api.chat(q, txns, history);
      setMessages((m) => [...m, { role: "assistant", content: r.answer, steps: r.steps,
        charts: r.charts, mode: r.mode, notice: r.notice }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant",
        content: `Sorry, that failed: ${e instanceof Error ? e.message : "unknown error"}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card chat" aria-labelledby="chat-title">
      <h2 id="chat-title">3. Ask the agent</h2>
      <div className="messages" aria-live="polite">
        {messages.length === 0 && (
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="chip" disabled={!txns.length || busy} onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <p>{m.content}</p>
            {m.steps && m.steps.length > 0 && (
              <details className="steps">
                <summary>
                  Agent used {m.steps.length} tool{m.steps.length > 1 ? "s" : ""}: {m.steps.map((s) => s.tool).join(" → ")}
                  {m.mode && <span className="badge">{m.mode === "llm" ? "LLM" : "offline"}</span>}
                </summary>
                {m.steps.map((s, j) => (
                  <pre key={j}>{`${s.tool}(${JSON.stringify(s.args)})\n→ ${s.result_preview}`}</pre>
                ))}
              </details>
            )}
            {m.notice && <p className="muted small">{m.notice}</p>}
            {m.charts?.map((c, j) => <ChartView key={j} spec={c} height={200} />)}
          </div>
        ))}
        {busy && <div className="msg assistant muted" role="status">Thinking…</div>}
        <div ref={end} />
      </div>
      <form className="row" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <label htmlFor="chat-input" className="visually-hidden">Your question</label>
        <input
          id="chat-input"
          value={input}
          maxLength={500}
          placeholder={txns.length ? "Ask about your spending…" : "Load a statement first"}
          disabled={!txns.length || busy}
          onChange={(e) => setInput(e.target.value)}
        />
        <button type="submit" disabled={!txns.length || busy || !input.trim()}>Send</button>
      </form>
    </section>
  );
}
