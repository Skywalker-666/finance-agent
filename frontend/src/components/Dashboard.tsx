import { useMemo } from "react";
import type { Forecast, Transaction } from "../types";
import ChartView, { inr } from "./ChartView";

export default function Dashboard({ txns, forecast }: { txns: Transaction[]; forecast: Forecast | null }) {
  const { spent, income, byCat, byMonth } = useMemo(() => {
    const byCat: Record<string, number> = {};
    const byMonth: Record<string, number> = {};
    let spent = 0;
    let income = 0;
    for (const t of txns) {
      if (t.amount < 0) {
        spent += -t.amount;
        const c = t.category || "Uncategorized";
        byCat[c] = (byCat[c] || 0) + -t.amount;
        byMonth[t.date.slice(0, 7)] = (byMonth[t.date.slice(0, 7)] || 0) + -t.amount;
      } else income += t.amount;
    }
    return { spent, income, byCat, byMonth };
  }, [txns]);

  const toData = (o: Record<string, number>, sort = true) => {
    const rows = Object.entries(o).map(([label, value]) => ({ label, value }));
    return sort ? rows.sort((a, b) => b.value - a.value) : rows.sort((a, b) => a.label.localeCompare(b.label));
  };

  return (
    <section className="card" aria-labelledby="dash-title">
      <h2 id="dash-title">2. Dashboard</h2>
      <div className="stats">
        <Stat label="Total spent" value={inr(spent)} />
        <Stat label="Total income" value={inr(income)} />
        <Stat label="Saved" value={inr(income - spent)} />
        {forecast && <Stat label="Forecast: next month spend" value={inr(forecast.expected_total_spend)} accent />}
      </div>
      <div className="charts">
        <ChartView spec={{ type: "pie", title: "Spend by category", data: toData(byCat) }} />
        <ChartView spec={{ type: "bar", title: "Spend by month", data: toData(byMonth, false) }} />
      </div>
    </section>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={`stat${accent ? " accent" : ""}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}
