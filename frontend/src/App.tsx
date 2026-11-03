import { useEffect, useState } from "react";
import { api } from "./api";
import ChatPanel from "./components/ChatPanel";
import Dashboard from "./components/Dashboard";
import TransactionsTable from "./components/TransactionsTable";
import UploadPanel from "./components/UploadPanel";
import type { Forecast, ModelInfo, Transaction } from "./types";

export default function App() {
  const [txns, setTxns] = useState<Transaction[]>([]);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [llm, setLlm] = useState<string>("checking");

  useEffect(() => {
    api.health().then((h) => setLlm(h.llm)).catch(() => setLlm("unreachable"));
    api.model().then(setModel).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!txns.length) return setForecast(null);
    api.forecast(txns).then(setForecast).catch(() => setForecast(null));
  }, [txns]);

  return (
    <>
      <header className="header">
        <div>
          <h1>Personal Finance Agent</h1>
          <p className="muted">ML categorization · spending forecast · tool-calling AI agent</p>
        </div>
        <div className="pills" aria-label="System status">
          <span className={`badge ${llm === "configured" ? "ok" : "warn"}`}>
            Agent: {llm === "configured" ? "LLM online" : llm === "offline" ? "offline mode" : llm}
          </span>
          {model && (
            <span className="badge" title={model.type}>
              Model accuracy (new shops): {Math.round(model.accuracy_unseen_merchants * 100)}%
            </span>
          )}
        </div>
      </header>
      <main className="layout">
        <div className="left">
          <UploadPanel onLoaded={setTxns} />
          {txns.length > 0 && <Dashboard txns={txns} forecast={forecast} />}
          {txns.length > 0 && (
            <TransactionsTable
              txns={txns}
              onChange={(i, category) =>
                setTxns((all) => all.map((t, j) => (j === i ? { ...t, category, confidence: 1 } : t)))}
            />
          )}
        </div>
        <div className="right">
          <ChatPanel txns={txns} />
        </div>
      </main>
      <footer className="muted small footer">
        Demo project. Sample data is synthetic. General budgeting insights, not financial advice.
      </footer>
    </>
  );
}
