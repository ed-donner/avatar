/** Shared types mirroring the backend models and SSE wire schema (BUILD-SPEC 8/9). */

export type Role = "visitor" | "avatar" | "human";

export interface Message {
  id: number;
  conversation_id: string;
  conversation_name: string | null;
  role: Role;
  content: string;
  tool_calls: unknown[] | null;
  needs_attention: boolean;
  read: boolean;
  created_at: string;
}

export interface ConversationThread {
  conversation_id: string;
  conversation_name: string | null;
  messages: Message[];
}

export interface ConversationSummary {
  conversation_id: string;
  conversation_name: string | null;
  preview: string;
  last_created_at: string;
  last_id: number;
  message_count: number;
  unread: boolean;
  needs_attention: boolean;
}

export interface Config {
  owner_name: string;
}

export interface Instructions {
  instructions: string;
}

/** SSE wire events streamed from POST /api/chat. */
export type ChatEvent =
  | { type: "tool"; phase: "called"; tool: string }
  | { type: "token"; text: string }
  | { type: "instant"; faq: number }
  | { type: "done"; message_id: number; needs_attention: boolean }
  | { type: "error"; message: string };
