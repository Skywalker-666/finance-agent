export interface Transaction {
  date: string;
  description: string;
  amount: number;
  category?: string | null;
  confidence?: number | null;
}

export interface ChartSpec {
  type: "pie" | "bar";
  title: string;
  data: { label: string; value: number }[];
}

export interface AgentStep {
  tool: string;
  args: Record<string, unknown>;
  result_preview: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  steps?: AgentStep[];
  charts?: ChartSpec[];
  mode?: string;
  notice?: string;
}

export interface Forecast {
  months_of_history: number;
  expected_spend_by_category: Record<string, number>;
  expected_total_spend: number;
  expected_income: number;
  expected_savings: number;
}

export interface ModelInfo {
  type: string;
  accuracy_unseen_merchants: number;
  accuracy_seen_merchants: number;
}

export const CATEGORIES = [
  "Food & Dining", "Groceries", "Transport", "Shopping", "Bills & Utilities",
  "Entertainment", "Health", "Rent", "Travel", "Education", "Income",
];
