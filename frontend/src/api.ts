import type { ChatMessage, Forecast, ModelInfo, Transaction } from "./types";

// Backend URL. Set VITE_API_URL at build time for the deployed site.
const API = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, init);
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try {
      const body = await r.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return r.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<{ status: string; llm: string }>("/api/health"),
  model: () => request<ModelInfo>("/api/model"),
  sample: () => request<{ transactions: Transaction[] }>("/api/sample"),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{ transactions: Transaction[] }>("/api/upload", { method: "POST", body: fd });
  },
  forecast: (txns: Transaction[]) => request<Forecast>("/api/forecast", json(txns)),
  chat: (message: string, transactions: Transaction[], history: ChatMessage[]) =>
    request<Omit<ChatMessage, "role" | "content"> & { answer: string }>(
      "/api/chat",
      json({
        message,
        transactions,
        history: history.map(({ role, content }) => ({ role, content })),
      }),
    ),
};
