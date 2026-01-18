import type { ProductCard, ToolCall } from "@/lib/ag-ui"

export type TodoItem = {
  content: string
  status?: "pending" | "in_progress" | "completed" | string
}

export type ThinkingState = {
  text: string
  done?: boolean
  toolCalls?: ToolCall[]
  todos?: TodoItem[]
  status?: string
}

export type Message = {
  id: string
  role: "user" | "agent" | "system"
  content: string
  products?: ProductCard[]
  thinking?: ThinkingState
}
