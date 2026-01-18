import type { ProductCard, ToolCall } from "@/lib/ag-ui"

const PRODUCTS_OPEN = "<products>"
const PRODUCTS_CLOSE = "</products>"

export const extractProducts = (raw: string): { display: string; products?: ProductCard[] } => {
  const openIndex = raw.indexOf(PRODUCTS_OPEN)
  if (openIndex === -1) return { display: raw }
  const closeIndex = raw.indexOf(PRODUCTS_CLOSE, openIndex)
  if (closeIndex === -1) return { display: raw.slice(0, openIndex).trimEnd() }
  const jsonText = raw.slice(openIndex + PRODUCTS_OPEN.length, closeIndex).trim()
  let products: ProductCard[] | undefined
  try {
    const parsed = JSON.parse(jsonText)
    if (parsed && Array.isArray(parsed.products)) {
      products = parsed.products
    } else if (Array.isArray(parsed)) {
      products = parsed
    }
  } catch {
    products = undefined
  }
  const display = (raw.slice(0, openIndex) + raw.slice(closeIndex + PRODUCTS_CLOSE.length)).trim()
  return { display, products }
}

export const formatPrice = (price?: string | number | null) => {
  if (price === null || price === undefined || price === "") return "Price unavailable"
  const numeric = typeof price === "number" ? price : Number(String(price).replace(/[^0-9.]/g, ""))
  if (!Number.isNaN(numeric) && Number.isFinite(numeric)) {
    return `$${numeric.toLocaleString()}`
  }
  return String(price)
}

export const getStoreLabel = (product: ProductCard) => {
  const url = product.url ?? product.store_url
  if (!url) return undefined
  try {
    return new URL(url).hostname.replace("www.", "")
  } catch {
    return undefined
  }
}

export const formatToolPayload = (value?: string) => {
  if (!value) return undefined
  try {
    return JSON.stringify(JSON.parse(value), null, 2)
  } catch {
    return value
  }
}

export const mergeToolCalls = (existing: ToolCall[], updates: ToolCall[]): ToolCall[] => {
  const next = [...existing]
  updates.forEach((update) => {
    const { argsAppend, resultAppend, ...rest } = update
    const key = rest.id ?? rest.name
    if (!key) return
    const index = next.findIndex((item) =>
      rest.id ? item.id === rest.id : item.name === rest.name && !item.id,
    )
    const base = index >= 0 ? next[index] : { name: rest.name || rest.id || "tool", id: rest.id }
    const args = rest.args
      ? argsAppend
        ? `${base.args ?? ""}${rest.args}`
        : rest.args
      : base.args
    const result = rest.result
      ? resultAppend
        ? `${base.result ?? ""}${rest.result}`
        : rest.result
      : base.result
    const name = rest.name || base.name || rest.id || "tool"
    const merged: ToolCall = { ...base, ...rest, name, args, result }
    if (index >= 0) {
      next[index] = merged
    } else {
      next.push(merged)
    }
  })
  return next
}

export const getActiveToolName = (toolCalls?: ToolCall[]) => {
  if (!toolCalls || toolCalls.length === 0) return undefined
  const active = [...toolCalls].reverse().find((tool) => tool.status !== "done")
  return active?.name
}

export const formatStatusLabel = (status?: string, toolName?: string) => {
  const normalized = (status || "").toLowerCase()
  if (normalized.includes("timeout") || normalized.includes("delay")) {
    return "응답이 지연되고 있어요... 다시 시도 중입니다."
  }
  if (normalized.includes("retry")) return "재시도 중입니다..."
  if (normalized.includes("network_error")) return "네트워크 상태를 확인하고 있어요..."
  if (normalized.includes("server_error") || normalized.includes("internal")) {
    return "서버에서 문제를 해결하고 있어요..."
  }
  if (status && /[가-힣]/.test(status)) return status
  if (normalized.includes("search")) return "지금 검색 중입니다..."
  if (normalized.includes("check")) return "지금 확인 중입니다..."
  if (normalized.includes("visit") || normalized.includes("browse")) return "페이지를 확인하고 있어요..."
  if (normalized.includes("edit") || normalized.includes("write")) return "정보를 정리하고 있어요..."
  if (normalized.includes("extract")) return "정보를 추출하고 있어요..."
  if (normalized.includes("compare")) return "비교하고 있어요..."
  if (normalized.includes("summar")) return "요약하고 있어요..."
  if (normalized.includes("calculat") || normalized.includes("rate") || normalized.includes("fx")) {
    return "계산 중입니다..."
  }
  if (toolName) return `${toolName} 실행 중입니다...`
  return status ? `${status} 중입니다...` : ""
}

export const getTodoTone = (status?: string) => {
  switch (status) {
    case "completed":
      return "text-emerald-200 border-emerald-500/30 bg-emerald-500/10"
    case "in_progress":
      return "text-blue-200 border-blue-500/30 bg-blue-500/10"
    default:
      return "text-gray-200 border-white/15 bg-white/5"
  }
}
