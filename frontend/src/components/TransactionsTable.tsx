import { useState } from "react";
import { CATEGORIES, type Transaction } from "../types";
import { inr } from "./ChartView";

const LOW_CONFIDENCE = 0.6;

/** Lists transactions; the user can correct any category the model got wrong. */
export default function TransactionsTable({ txns, onChange }: {
  txns: Transaction[];
  onChange: (index: number, category: string) => void;
}) {
  const [onlyUnsure, setOnlyUnsure] = useState(false);
  const rows = txns
    .map((t, i) => ({ t, i }))
    .filter(({ t }) => !onlyUnsure || (t.confidence ?? 1) < LOW_CONFIDENCE)
    .reverse();
  const unsure = txns.filter((t) => (t.confidence ?? 1) < LOW_CONFIDENCE).length;

  return (
    <section className="card" aria-labelledby="tx-title">
      <div className="row between">
        <h2 id="tx-title">Transactions ({txns.length})</h2>
        <label className="muted">
          <input type="checkbox" checked={onlyUnsure} onChange={(e) => setOnlyUnsure(e.target.checked)} />{" "}
          Show only low-confidence ({unsure})
        </label>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th scope="col">Date</th><th scope="col">Description</th><th scope="col">Amount</th>
              <th scope="col">Category (ML)</th><th scope="col">Confidence</th></tr>
          </thead>
          <tbody>
            {rows.slice(0, 300).map(({ t, i }) => (
              <tr key={i}>
                <td>{t.date}</td>
                <td className="desc">{t.description}</td>
                <td className={t.amount < 0 ? "neg" : "pos"}>{inr(t.amount)}</td>
                <td>
                  <select
                    aria-label={`Category for ${t.description}`}
                    value={t.category || ""}
                    onChange={(e) => onChange(i, e.target.value)}
                  >
                    {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                  </select>
                </td>
                <td>
                  <span className={`badge${(t.confidence ?? 1) < LOW_CONFIDENCE ? " warn" : ""}`}>
                    {Math.round((t.confidence ?? 1) * 100)}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
