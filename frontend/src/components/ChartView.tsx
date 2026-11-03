import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ChartSpec } from "../types";

export const COLORS = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4",
  "#a855f7", "#ec4899", "#84cc16", "#f97316", "#14b8a6"];

export const inr = (v: number) => `₹${Math.round(v).toLocaleString("en-IN")}`;

export default function ChartView({ spec, height = 240 }: { spec: ChartSpec; height?: number }) {
  // Screen-reader summary of the same data the chart shows.
  const summary = spec.data.map((d) => `${d.label}: ${inr(d.value)}`).join(", ");
  return (
    <figure className="chart">
      <figcaption>{spec.title}</figcaption>
      <div role="img" aria-label={`${spec.title}. ${summary}`}>
        <ResponsiveContainer width="100%" height={height}>
          {spec.type === "pie" ? (
            <PieChart>
              <Pie data={spec.data} dataKey="value" nameKey="label" innerRadius="45%" outerRadius="80%">
                {spec.data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip formatter={(v: number) => inr(v)} />
            </PieChart>
          ) : (
            <BarChart data={spec.data}>
              <XAxis dataKey="label" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={(v: number) => `${Math.round(v / 1000)}k`} width={40} />
              <Tooltip formatter={(v: number) => inr(v)} />
              <Bar dataKey="value" fill={COLORS[0]} radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
