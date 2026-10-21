import type { Routing, Usage } from "@/lib/api";

export interface UserTurn {
  role: "user";
  content: string;
}

export interface AssistantTurn {
  role: "assistant";
  content: string;
  routing: Routing;
  model: string;
  usage: Usage;
}

export type Turn = UserTurn | AssistantTurn;

export interface ColumnState {
  turns: Turn[];
  pending: boolean;
  error: { message: string; retryable: boolean; text: string } | null;
  // After bot only: the previous reply's routing.selected, sent back as carry_skills.
  carry: string[];
}

export const EMPTY_COLUMN: ColumnState = { turns: [], pending: false, error: null, carry: [] };
