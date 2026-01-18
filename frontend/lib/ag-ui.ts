type StreamUpdate = {
  text?: string
  replace?: boolean
  thinkingText?: string
  thinkingReplace?: boolean
  thinkingActive?: boolean
  thinkingDone?: boolean
  thinkingStatus?: string
  todos?: TodoItem[]
  toolCalls?: ToolCall[]
  products?: ProductCard[]
}

export type ProductCard = {
  id?: string | number | null
  title: string
  handle?: string | null
  url?: string | null
  price?: string | number | null
  image?: string | null
  store_url?: string | null
}

export type ToolCall = {
  name: string
  id?: string
  args?: string
  result?: string
  status?: "active" | "done" | "error"
  argsAppend?: boolean
  resultAppend?: boolean
}

type StreamOptions = {
  url: string
  message: string
  threadId: string
  messageId: string
  signal?: AbortSignal
  onUpdate: (update: StreamUpdate) => void
  onRawEvent?: (payload: unknown, raw: string) => void
}

type TodoItem = {
  content: string
  status: string
}

const DEFAULT_HEADERS = {
  "Content-Type": "application/json",
  Accept: "text/event-stream",
}

function normalizeContent(content: unknown): string {
  if (typeof content === "string") return content
  if (Array.isArray(content)) {
    return content.map((part) => normalizeContent(part)).join("")
  }
  if (content && typeof content === "object") {
    const obj = content as Record<string, unknown>
    if (typeof obj.text === "string") return obj.text
    if (typeof obj.content === "string") return obj.content
  }
  return ""
}

function stringifyToolPayload(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined
  if (typeof value === "string") return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function mapRunErrorMessage(message: string): { text: string; status?: string } {
  const lower = message.toLowerCase()
  if (lower.includes("timeout") || lower.includes("timed out") || lower.includes("deadline")) {
    return { text: "응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.", status: "timeout" }
  }
  if (lower.includes("rate limit") || lower.includes("429")) {
    return { text: "요청이 많아 잠시 대기 중입니다. 잠시 후 다시 시도해주세요.", status: "retry" }
  }
  if (lower.includes("internal") || lower.includes("500")) {
    return { text: "서버 오류로 응답이 중단되었습니다. 잠시 후 다시 시도해주세요.", status: "server_error" }
  }
  if (
    lower.includes("socket") ||
    lower.includes("network") ||
    lower.includes("connection") ||
    lower.includes("connect")
  ) {
    return { text: "네트워크 오류로 응답이 중단되었습니다. 연결 상태를 확인해 주세요.", status: "network_error" }
  }
  return { text: "죄송합니다. 응답 처리 중 문제가 발생했습니다.", status: "error" }
}

function statusFromToolName(name: string | undefined): string | undefined {
  if (!name) return undefined
  const lower = name.toLowerCase()
  if (lower.includes("search")) return "Searching"
  if (lower.includes("check") || lower.includes("stock")) return "Checking"
  if (lower.includes("browse") || lower.includes("visit") || lower.includes("open") || lower.includes("navigate")) {
    return "Visiting"
  }
  if (lower.includes("write") || lower.includes("edit") || lower.includes("save") || lower.includes("update")) {
    return "Editing"
  }
  if (lower.includes("extract") || lower.includes("parse")) return "Extracting"
  if (lower.includes("compare")) return "Comparing"
  if (lower.includes("summarize") || lower.includes("summary")) return "Summarizing"
  if (lower.includes("rate") || lower.includes("fx") || lower.includes("currency") || lower.includes("convert")) {
    return "Calculating"
  }
  return undefined
}

function normalizeTodoItem(item: unknown): TodoItem | null {
  if (!item) return null
  if (typeof item === "string") {
    return { content: item, status: "pending" }
  }
  if (typeof item === "object") {
    const obj = item as Record<string, unknown>
    const content =
      (typeof obj.content === "string" && obj.content) ||
      (typeof obj.text === "string" && obj.text) ||
      ""
    if (!content) return null
    const status = typeof obj.status === "string" ? obj.status : "pending"
    return { content, status }
  }
  return null
}

function extractTodos(snapshot: unknown): TodoItem[] | undefined {
  if (!snapshot || typeof snapshot !== "object") return undefined
  const obj = snapshot as Record<string, unknown>
  const rawTodos = obj.todos ?? obj.todo ?? obj.todo_list
  if (!Array.isArray(rawTodos)) return undefined
  const normalized = rawTodos
    .map((item) => normalizeTodoItem(item))
    .filter((item): item is TodoItem => Boolean(item))
  return normalized.length ? normalized : undefined
}

function extractUpdate(payload: unknown): StreamUpdate {
  if (!payload || typeof payload !== "object") return {}

  const data = payload as Record<string, unknown>
  const type = String(data.type ?? data.event ?? "")
  const typeUpper = type.toUpperCase()
  const typeLower = type.toLowerCase()
  const snapshot =
    (data.snapshot as Record<string, unknown> | undefined) ??
    (data.state as Record<string, unknown> | undefined) ??
    (data.data as Record<string, unknown> | undefined)?.snapshot ??
    (data.data as Record<string, unknown> | undefined)?.state
  const delta =
    (data.delta as Record<string, unknown> | undefined) ??
    (data.data as Record<string, unknown> | undefined)?.delta
  const todos = extractTodos(snapshot ?? delta ?? data)

  if (typeUpper === "THINKING_TEXT_MESSAGE_CONTENT") {
    const thinkingDelta = normalizeContent(data.delta ?? (data.data as Record<string, unknown> | undefined)?.delta)
    if (thinkingDelta) {
      return { thinkingText: thinkingDelta, thinkingReplace: false, thinkingActive: true }
    }
  }
  if (typeUpper === "THINKING_TEXT_MESSAGE_START") {
    return {
      thinkingText: "",
      thinkingReplace: true,
      thinkingActive: true,
      ...(todos ? { todos } : {}),
    }
  }
  if (typeUpper === "THINKING_TEXT_MESSAGE_END") {
    return {
      thinkingDone: true,
      ...(todos ? { todos } : {}),
    }
  }
  if (typeUpper === "THINKING_START") {
    return {
      thinkingActive: true,
      ...(todos ? { todos } : {}),
    }
  }
  if (typeUpper === "THINKING_END") {
    return {
      thinkingDone: true,
      ...(todos ? { todos } : {}),
    }
  }
  if (typeUpper === "MESSAGES_SNAPSHOT") {
    if (todos) {
      return { todos }
    }
    return {}
  }

  if (typeUpper === "TEXT_MESSAGE_START") {
    return { text: "", replace: true, thinkingActive: true, ...(todos ? { todos } : {}) }
  }
  if (typeUpper === "TEXT_MESSAGE_CONTENT") {
    const content = normalizeContent(data.delta ?? (data.data as Record<string, unknown> | undefined)?.delta)
    if (content) {
      return { text: content, replace: false, thinkingActive: true, ...(todos ? { todos } : {}) }
    }
  }
  if (typeUpper === "TEXT_MESSAGE_CHUNK") {
    const content = normalizeContent(data.delta ?? (data.data as Record<string, unknown> | undefined)?.delta)
    if (content) {
      return { text: content, replace: false, thinkingActive: true, ...(todos ? { todos } : {}) }
    }
  }
  if (typeUpper === "TEXT_MESSAGE_END") {
    return { thinkingDone: true, ...(todos ? { todos } : {}) }
  }

  if (typeUpper === "RUN_ERROR") {
    const message = String(data.message ?? "")
    if (message) {
      const mapped = mapRunErrorMessage(message)
      return {
        text: mapped.text,
        replace: true,
        thinkingDone: true,
        ...(mapped.status ? { thinkingStatus: mapped.status } : {}),
      }
    }
    return { text: "죄송합니다. 응답 처리 중 문제가 발생했습니다.", replace: true, thinkingDone: true }
  }

  if (typeUpper === "RUN_FINISHED") {
    return { thinkingDone: true, ...(todos ? { todos } : {}) }
  }

  if (typeUpper === "CUSTOM") {
    const name = String(data.name ?? "")
    const rawValue = data.value ?? data.data ?? {}
    let value: Record<string, unknown> | null = null
    if (typeof rawValue === "string") {
      try {
        const parsed = JSON.parse(rawValue)
        if (parsed && typeof parsed === "object") {
          value = parsed as Record<string, unknown>
        }
      } catch {
        value = null
      }
    } else if (rawValue && typeof rawValue === "object") {
      value = rawValue as Record<string, unknown>
    }

    if (name.toLowerCase().includes("status") && value) {
      const label =
        typeof value === "string"
          ? value
          : String(value.label ?? value.status ?? value.name ?? "")
      if (label) {
        return { thinkingStatus: label, thinkingActive: true, ...(todos ? { todos } : {}) }
      }
    }
  }

  if (typeUpper === "TOOL_CALL_ARGS" || typeUpper === "TOOL_CALL_CHUNK") {
    const toolId = String(data.toolCallId ?? data.tool_call_id ?? "")
    if (!toolId) return {}
    const toolName = String(data.toolCallName ?? data.tool_call_name ?? "")
    const argsDelta = normalizeContent(data.delta ?? (data.data as Record<string, unknown> | undefined)?.delta)
    if (!argsDelta) return {}
    return {
      toolCalls: [
        {
          id: toolId,
          name: toolName,
          args: argsDelta,
          argsAppend: true,
          status: "active",
        },
      ],
      thinkingActive: true,
      ...(statusFromToolName(toolName) ? { thinkingStatus: statusFromToolName(toolName) } : {}),
    }
  }

  if (typeUpper === "TOOL_CALL_RESULT") {
    const toolId = String(data.toolCallId ?? data.tool_call_id ?? "")
    if (!toolId) return {}
    const resultText =
      normalizeContent(data.content ?? (data.data as Record<string, unknown> | undefined)?.content) ||
      stringifyToolPayload(data.content ?? (data.data as Record<string, unknown> | undefined)?.content)
    return {
      toolCalls: [
        {
          id: toolId,
          name: String(data.toolCallName ?? data.tool_call_name ?? ""),
          result: resultText ?? "",
          status: "done",
        },
      ],
      thinkingActive: true,
      ...(statusFromToolName(String(data.toolCallName ?? data.tool_call_name ?? "")) ? { thinkingStatus: statusFromToolName(String(data.toolCallName ?? data.tool_call_name ?? "")) } : {}),
      ...(todos ? { todos } : {}),
    }
  }

  if (typeUpper === "TOOL_CALL_END") {
    const toolId = String(data.toolCallId ?? data.tool_call_id ?? "")
    if (!toolId) return {}
    return {
      toolCalls: [
        {
          id: toolId,
          name: String(data.toolCallName ?? data.tool_call_name ?? ""),
          status: "done",
        },
      ],
      ...(todos ? { todos } : {}),
    }
  }

  if (typeUpper === "TOOL_CALL_START") {
    const toolName = String(
      data.toolCallName ??
      data.tool_call_name ??
      (data as Record<string, unknown>).name ??
      ""
    )
    const toolId = String(data.toolCallId ?? data.tool_call_id ?? toolName ?? "")
    if (!toolId) return {}
    return {
      toolCalls: toolName ? [{ id: toolId, name: toolName, status: "active" }] : undefined,
      thinkingActive: true,
      ...(statusFromToolName(toolName) ? { thinkingStatus: statusFromToolName(toolName) } : {}),
      ...(todos ? { todos } : {}),
    }
  }

  if (typeUpper === "ACTIVITY_SNAPSHOT" || typeUpper === "ACTIVITY_DELTA") {
    return {}
  }

  // Extract tool calls from events
  if (typeLower.includes("tool") || typeLower.includes("action")) {
    const toolCallsRaw =
      data.toolCalls ??
      data.tool_calls ??
      (data.data as Record<string, unknown> | undefined)?.toolCalls ??
      (data.data as Record<string, unknown> | undefined)?.tool_calls
    if (Array.isArray(toolCallsRaw)) {
      const toolCalls = toolCallsRaw
        .map((tc: unknown) => {
          if (tc && typeof tc === "object") {
            const call = tc as Record<string, unknown>
            const name = String(call.name ?? call.tool ?? call.function ?? "")
            if (name) {
              return {
                id: String(call.id ?? ""),
                name,
                args: stringifyToolPayload(call.args ?? call.arguments ?? call.input),
                status: "active",
              } as ToolCall
            }
          }
          return null
        })
        .filter((tc): tc is ToolCall => tc !== null) as ToolCall[]
      if (toolCalls.length > 0) {
        return { toolCalls, thinkingActive: true }
      }
    }
  }

  if (Array.isArray(data.messages)) {
    const reversed = [...data.messages].reverse() as Record<string, unknown>[]
    const lastAssistant =
      reversed.find((msg) => String(msg.role ?? msg.type ?? "").toLowerCase() === "assistant") ??
      reversed[0]
    const content = normalizeContent(lastAssistant?.content ?? lastAssistant?.text)
    if (content) {
      return { text: content, replace: true, ...(todos ? { todos } : {}) }
    }
  }

  const message = data.message ?? (data.data as Record<string, unknown> | undefined)?.message
  if (message && typeof message === "object") {
    const messageObj = message as Record<string, unknown>
    const content = normalizeContent(messageObj.content ?? messageObj.text)
    if (content) {
      const isDelta =
        typeLower.includes("delta") ||
        typeLower.includes("token") ||
        typeLower.includes("text_message_content") ||
        typeLower.includes("text_message_chunk")
      return { text: content, replace: !isDelta, ...(todos ? { todos } : {}) }
    }
  }

  const content = normalizeContent(data.content ?? (data.data as Record<string, unknown> | undefined)?.content)
  if (content) {
    const isDelta =
      typeLower.includes("delta") ||
      typeLower.includes("token") ||
      typeLower.includes("text_message_content") ||
      typeLower.includes("text_message_chunk")
    return { text: content, replace: !isDelta, ...(todos ? { todos } : {}) }
  }

  const contentDelta = normalizeContent(data.delta ?? (data.data as Record<string, unknown> | undefined)?.delta)
  if (contentDelta) {
    return { text: contentDelta, replace: false, ...(todos ? { todos } : {}) }
  }

  if (todos) {
    return { todos }
  }

  return {}
}

function parseEventBlock(block: string): unknown[] {
  const dataLines = block
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.replace(/^data:\s?/, ""))

  if (dataLines.length) {
    const data = dataLines.join("\n").trim()
    if (!data || data === "[DONE]") return []
    try {
      return [JSON.parse(data)]
    } catch {
      return []
    }
  }

  const payloads: unknown[] = []
  for (const line of block.split("\n")) {
    const trimmed = line.trim()
    if (!trimmed) continue
    if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) continue
    try {
      payloads.push(JSON.parse(trimmed))
    } catch {
      // ignore invalid JSON line
    }
  }
  return payloads
}

async function streamResponseBody(
  response: Response,
  onUpdate: (update: StreamUpdate) => void,
  onRawEvent?: (payload: unknown, raw: string) => void,
) {
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error("Empty response body")
  }

  const decoder = new TextDecoder()
  let buffer = ""
  let lastText = ""
  let lastThinking = ""

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const blocks = buffer.split(/\n\n+/)
    buffer = blocks.pop() ?? ""

    for (const block of blocks) {
      const payloads = parseEventBlock(block)
      for (const payload of payloads) {
        onRawEvent?.(payload, block)
        const update = extractUpdate(payload)
        if (update.text !== undefined) {
          lastText = update.replace ? update.text : lastText + update.text
          onUpdate({ ...update, text: lastText })
        } else if (update.thinkingText !== undefined) {
          lastThinking = update.thinkingReplace ? update.thinkingText : lastThinking + update.thinkingText
          onUpdate({ ...update, thinkingText: lastThinking })
        } else if (update.thinkingActive || update.thinkingDone || update.thinkingStatus !== undefined) {
          onUpdate(update)
        } else if (update.todos || update.toolCalls || update.products) {
          onUpdate(update)
        } else if (update.todos) {
          onUpdate(update)
        }
      }
    }
  }

  const remaining = buffer.trim()
  if (remaining) {
    const payloads = parseEventBlock(remaining)
    for (const payload of payloads) {
      onRawEvent?.(payload, remaining)
      const update = extractUpdate(payload)
      if (update.text !== undefined) {
        lastText = update.replace ? update.text : lastText + update.text
        onUpdate({ ...update, text: lastText })
      } else if (update.thinkingText !== undefined) {
        lastThinking = update.thinkingReplace ? update.thinkingText : lastThinking + update.thinkingText
        onUpdate({ ...update, thinkingText: lastThinking })
      } else if (update.thinkingActive || update.thinkingDone || update.thinkingStatus !== undefined) {
        onUpdate(update)
      } else if (update.todos || update.toolCalls || update.products) {
        onUpdate(update)
      } else if (update.todos) {
        onUpdate(update)
      }
    }
  }
}

async function streamSinglePayload(
  response: Response,
  onUpdate: (update: StreamUpdate) => void,
  onRawEvent?: (payload: unknown, raw: string) => void,
) {
  const payload = await response.json()
  onRawEvent?.(payload, JSON.stringify(payload))
  const update = extractUpdate(payload)
  if (
    update.text !== undefined ||
    update.thinkingText !== undefined ||
    update.thinkingActive ||
    update.thinkingDone ||
    update.thinkingStatus !== undefined ||
    update.toolCalls ||
    update.products
  ) {
    onUpdate(update)
  } else if (update.todos) {
    onUpdate(update)
  }
}

export async function streamAgentResponse({
  url,
  message,
  threadId,
  messageId,
  signal,
  onUpdate,
  onRawEvent,
}: StreamOptions) {
  const payload = {
    threadId,
    runId: crypto.randomUUID(),
    state: {},
    messages: [{ id: messageId, role: "user", content: message }],
    tools: [],
    context: [],
    forwardedProps: {},
  }

  const response = await fetch(url, {
    method: "POST",
    headers: DEFAULT_HEADERS,
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    throw new Error(await response.text())
  }

  const contentType = response.headers.get("content-type") ?? ""
  if (contentType.includes("application/json")) {
    await streamSinglePayload(response, onUpdate, onRawEvent)
  } else {
    await streamResponseBody(response, onUpdate, onRawEvent)
  }
}
