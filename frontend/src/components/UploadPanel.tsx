import { useRef, useState } from "react";
import { api } from "../api";
import type { Transaction } from "../types";

export default function UploadPanel({ onLoaded }: { onLoaded: (t: Transaction[]) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  async function run(p: Promise<{ transactions: Transaction[] }>) {
    setBusy(true);
    setError(null);
    try {
      onLoaded((await p).transactions);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card upload" aria-labelledby="upload-title">
      <h2 id="upload-title">1. Load a statement</h2>
      <p className="muted">
        CSV with <code>date, description, amount</code> (or <code>Date, Narration, Withdrawal, Deposit</code>).
        Your data stays in this browser tab; the server stores nothing.
      </p>
      <div className="row">
        <label className="button">
          Upload CSV
          <input
            ref={input}
            type="file"
            accept=".csv,text/csv"
            className="visually-hidden"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) run(api.upload(f));
              if (input.current) input.current.value = "";
            }}
          />
        </label>
        <button className="secondary" disabled={busy} onClick={() => run(api.sample())}>
          Use sample data
        </button>
        {busy && <span className="muted" role="status">Categorizing…</span>}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}
