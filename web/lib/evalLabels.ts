// Display labels and formatters for the eval pages. Plain data, safe to import anywhere.

export const DATASET_INFO: Record<string, { label: string; description: string }> = {
  single_topic: {
    label: "Single topic",
    description: "One question per message. Is it answered accurately for this member?",
  },
  multi_intent: {
    label: "Multi-intent",
    description: "Two or three questions in one message. Is every one of them answered?",
  },
  context_use: {
    label: "Context use",
    description: "Does the reply use the member's own figures, dates and product status exactly?",
  },
  safety_basic: {
    label: "Basic safety",
    description:
      "Guardrails: no promised score gains or removals, no help with fraud, hardship handling, sensitive data and prompt injection.",
  },
};

export function datasetLabel(dataset: string): string {
  return DATASET_INFO[dataset]?.label ?? dataset;
}

export function questionsLabel(intents: number | string): string {
  return Number(intents) === 1 ? "1 question" : `${intents} questions`;
}

export const KIND_LABELS: Record<string, string> = {
  body: "Topic skill body edit",
  always_on: "Always-on skill edit",
  description: "Topic skill description edit",
};

// Worded to match hypothesis_matches() in backend/evals/report.py, which decides "matched".
export const EXPECTED_LABELS: Record<string, string> = {
  improve: "Improves: some cases improve and none regress",
  regress: "Regresses: at least one case regresses",
  tradeoff: "Tradeoff: some cases improve and some regress",
};

export const OBSERVED_LABELS: Record<string, string> = {
  improve: "some cases improved and none regressed",
  regress: "some cases regressed and none improved",
  tradeoff: "some cases improved and some regressed",
  "no change": "no case changed",
};

/**
 * A 0-1 rate as whole percentage points, rounding halves up (0.575 -> 58, 0.625 -> 63).
 * The rates are rounded to 4 decimals by the Python side; trimming float noise first keeps
 * 0.575 * 100 (= 57.4999...) from rounding down.
 */
export function percentPoints(rate: number): number {
  return Math.round(Number((rate * 100).toFixed(6)));
}

/** 0.6667 -> "67%". */
export function pct(rate: number | null | undefined): string {
  return typeof rate === "number" ? `${percentPoints(rate)}%` : "n/a";
}

/**
 * The change between two rates, in percentage points, as the difference of the two rounded
 * percentages shown next to it (so 58% -> 75% always reads "+17 pts").
 */
export function deltaPoints(baseline: number | null | undefined, candidate: number | null | undefined): number | null {
  if (typeof baseline !== "number" || typeof candidate !== "number") return null;
  return percentPoints(candidate) - percentPoints(baseline);
}

/** +33 -> "+33 pts", -25 -> "-25 pts", 0 -> "no change". */
export function deltaLabel(points: number | null): string {
  if (points === null) return "n/a";
  if (points === 0) return "no change";
  return `${points > 0 ? "+" : "-"}${Math.abs(points)} pts`;
}

/** "2026-10-22T01:15:31+00:00" -> "2026-10-22 01:15 UTC". String-only, so prerendering stays deterministic. */
export function formatTimestamp(iso: string): string {
  const match = iso.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  if (!match) return iso || "unknown";
  const utc = /(\+00:00|Z)$/.test(iso);
  return `${match[1]} ${match[2]}${utc ? " UTC" : ""}`;
}

/** First ~max characters of a Markdown reply as plain text, cut at a word boundary. */
export function excerpt(text: string, max = 480): { text: string; truncated: boolean } {
  const plain = text
    .replace(/\*\*|__/g, "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  if (plain.length <= max) return { text: plain, truncated: false };
  const cut = plain.slice(0, max);
  const space = cut.lastIndexOf(" ");
  return { text: `${(space > max * 0.6 ? cut.slice(0, space) : cut).trimEnd()}…`, truncated: true };
}
