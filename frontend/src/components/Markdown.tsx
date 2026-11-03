import type { ReactNode } from "react";

// Tiny, safe markdown renderer for chat answers: **bold**, bullet and numbered
// lists, and paragraphs. It builds React elements (no innerHTML), so LLM text
// can never inject HTML or scripts.

function inline(text: string, key: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4
      ? <strong key={`${key}-${i}`}>{part.slice(2, -2)}</strong>
      : part,
  );
}

const BULLET = /^\s*[-*•]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;

export default function Markdown({ text }: { text: string }) {
  // LLMs sometimes inline a list ("1. A 2. B"); put each item on its own line.
  const lines = text.replace(/\s+(?=\d+\.\s+\*\*)/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  const flush = () => {
    if (!list) return;
    const k = `l${blocks.length}`;
    const items = list.items.map((it, i) => <li key={i}>{inline(it, `${k}-${i}`)}</li>);
    blocks.push(list.ordered ? <ol key={k}>{items}</ol> : <ul key={k}>{items}</ul>);
    list = null;
  };

  for (const line of lines) {
    const b = BULLET.exec(line);
    const n = NUMBERED.exec(line);
    if (b || n) {
      const ordered = Boolean(n);
      if (!list || list.ordered !== ordered) {
        flush();
        list = { ordered, items: [] };
      }
      list.items.push((n ?? b)![1]);
    } else if (line.trim()) {
      flush();
      blocks.push(<p key={`p${blocks.length}`}>{inline(line.trim(), `p${blocks.length}`)}</p>);
    } else {
      flush();
    }
  }
  flush();
  return <div className="md">{blocks}</div>;
}
