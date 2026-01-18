import { ShoppingBag } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import remarkBreaks from "remark-breaks"

import ShinyText from "@/components/ui/shiny-text"
import { cn } from "@/lib/utils"
import type { ProductCard } from "@/lib/ag-ui"
import type { Message } from "@/components/chat/types"
import {
  formatPrice,
  formatStatusLabel,
  formatToolPayload,
  getActiveToolName,
  getStoreLabel,
  getTodoTone,
} from "@/components/chat/utils"
import CheckoutCard, { type CheckoutInfo } from "@/components/chat/CheckoutCard"

type MessageItemProps = {
  message: Message
  expanded?: boolean
  onToggleThinking: (messageId: string) => void
  onProductSelect: (product: ProductCard) => void
  onPaymentComplete?: (checkoutId: string) => void
}

export default function MessageItem({
  message,
  expanded,
  onToggleThinking,
  onProductSelect,
  onPaymentComplete,
}: MessageItemProps) {
  const isThinkingActive = message.thinking?.done === false
  const activeToolName = getActiveToolName(message.thinking?.toolCalls)
  const statusLabel = isThinkingActive
    ? formatStatusLabel(message.thinking?.status, activeToolName)
    : ""
  const hasThinking =
    message.role === "agent" &&
    (message.thinking?.toolCalls?.length ||
      message.thinking?.todos?.length ||
      message.thinking?.text ||
      isThinkingActive)
  const useShiny = Boolean(statusLabel)
  const isExpanded = expanded ?? isThinkingActive

  // --- Checkout Card Detection Logic ---
  let checkoutInfo: CheckoutInfo | null = null
  if (message.role === "agent" && message.thinking?.toolCalls) {
    // Reverse iterate to find the most recent successful checkout creation
    for (let i = message.thinking.toolCalls.length - 1; i >= 0; i--) {
      const tool = message.thinking.toolCalls[i]
      if (
        (tool.name === "ucp_create_checkout" || tool.name === "ucp_create_checkout_from_handle") &&
        tool.result &&
        typeof tool.result === "string"
      ) {
        try {
          // The tool result is a JSON string stringified primarily for the LLM
          // We need to parse it to get the ID and URL
          // Sometimes it might be wrapped or have extra text, but usually it's clean JSON
          const parsed = JSON.parse(tool.result)
          if (parsed.id && parsed.url) {
            // Try to find store_url from args if available, or fallback
            let storeUrl = "https://monos.com" // default fallback
            const args = tool.args as Record<string, any> | undefined
            if (args && typeof args === 'object' && 'store_url' in args) {
              storeUrl = args.store_url as string
            }

            checkoutInfo = {
              checkoutId: parsed.id,
              url: parsed.url,
              storeUrl: storeUrl,
              total: parsed.totals?.find((t: any) => t.type === 'total')?.amount,
              currency: parsed.currency || "USD"
            }
            break
          }
        } catch (e) {
          // ignore parsing errors
        }
      }
    }
  }

  return (
    <motion.div
      initial={{ y: 10 }}
      animate={{ y: 0 }}
      exit={{ y: -10 }}
      transition={{ duration: 0.15 }}
      className={cn(
        "flex gap-3",
        message.role === "user" && "flex-row-reverse",
      )}
    >
      {message.role === "agent" && (
        <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden">
          <img src="/gemini.png" alt="Agent" className="h-full w-full object-cover" />
        </div>
      )}

      <div className={cn("max-w-[80%]", message.role === "user" && "flex justify-end")}>
        <div
          className={cn(
            "text-sm leading-relaxed font-spotlight",
            message.role === "agent" && "text-gray-200",
            message.role === "user" &&
            "rounded-2xl bg-white/10 backdrop-blur-sm border border-white/10 px-4 py-3 text-white",
          )}
        >
          {hasThinking && message.thinking && (
            <div className="mb-3 rounded-xl p-2">
              <button
                type="button"
                onClick={() => onToggleThinking(message.id)}
                className="flex w-full items-start justify-between py-1 text-left"
              >
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "inline-block text-white/70 transition-transform",
                        isExpanded ? "rotate-90" : "",
                      )}
                    >
                      &gt;
                    </span>
                    <span className="text-xs font-medium text-white/70">생각하는 과정</span>
                  </div>
                  {statusLabel && (
                    <div className="ml-4">
                      {useShiny ? (
                        <ShinyText
                          text={statusLabel}
                          speed={2.2}
                          className="text-xs font-medium"
                          color="#94a3b8"
                          shineColor="#0b5fff"
                          spread={120}
                        />
                      ) : (
                        <span className="text-xs font-medium text-white/60">{statusLabel}</span>
                      )}
                    </div>
                  )}
                </div>
                {isThinkingActive && statusLabel && (
                  <span className="text-xs text-white/60">Answer now</span>
                )}
              </button>

              <AnimatePresence>
                {isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="mt-3 space-y-3">
                      {activeToolName && (
                        <div className="text-xs text-white/70">
                          현재 도구: <span className="font-mono text-blue-200">{activeToolName}</span>
                        </div>
                      )}
                      {message.thinking.toolCalls && message.thinking.toolCalls.length > 0 && (
                        <div className="space-y-2">
                          <div className="text-[10px] uppercase tracking-[0.3em] text-white/60 flex items-center gap-1">
                            🛠️ 도구 호출 내역
                          </div>
                          {message.thinking.toolCalls.map((tool, idx) => {
                            const args = formatToolPayload(tool.args)
                            const result = formatToolPayload(tool.result)
                            return (
                              <div
                                key={`${tool.id ?? tool.name}-${idx}`}
                                className="rounded-lg border border-white/5 bg-white/5 px-3 py-2 text-[11px] text-white/80"
                              >
                                <div className="font-mono text-blue-200">{tool.name || "tool"}</div>
                                {args && (
                                  <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap border-l border-white/10 pl-3 font-mono text-[11px] text-white/80">
                                    {args}
                                  </pre>
                                )}
                                {result && (
                                  <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap border-l border-white/10 pl-3 font-mono text-[11px] text-white/80">
                                    {result}
                                  </pre>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      )}

                      {message.thinking.todos && message.thinking.todos.length > 0 && (
                        <div className="space-y-2">
                          <div className="text-[10px] uppercase tracking-[0.3em] text-white/60">
                            To-Do
                          </div>
                          {message.thinking.todos.map((todo, idx) => (
                            <div
                              key={`${todo.content}-${idx}`}
                              className="flex items-center gap-2 rounded-lg border border-white/5 bg-white/5 px-3 py-2 text-[11px]"
                            >
                              <span
                                className={cn(
                                  "rounded-full border px-2 py-0.5 text-[9px] uppercase tracking-[0.2em]",
                                  getTodoTone(todo.status),
                                )}
                              >
                                {todo.status ?? "pending"}
                              </span>
                              <span className="text-white/80">{todo.content}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {message.thinking.text && (
                        <div>
                          <div className="text-[10px] uppercase tracking-[0.3em] text-white/60">
                            Thinking
                          </div>
                          <pre className="mt-2 whitespace-pre-wrap font-sans text-[11px] text-white/80">
                            {message.thinking.text}
                          </pre>
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}

          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkBreaks]}
            className="prose prose-invert prose-sm max-w-none [&_a]:text-blue-300 [&_a]:underline font-spotlight"
          >
            {message.content || ""}
          </ReactMarkdown>

          {/* Checkout Card - Rendered if a checkout was recently created */}
          {checkoutInfo && (
            <CheckoutCard info={checkoutInfo} onPaymentComplete={onPaymentComplete} />
          )}

          {message.role === "agent" && message.products && message.products.length > 0 && (
            <div className="mt-3 grid gap-3">
              {message.products.map((product, idx) => {
                const storeLabel = getStoreLabel(product)
                return (
                  <button
                    key={`${product.id ?? product.handle ?? product.title}-${idx}`}
                    type="button"
                    onClick={() => onProductSelect(product)}
                    className="flex gap-3 rounded-xl border border-white/10 bg-white/5 p-3 text-left transition-all hover:border-blue-500/50 hover:bg-white/10"
                  >
                    <div className="h-16 w-16 flex-shrink-0 overflow-hidden rounded-lg border border-white/10 bg-[#101114]">
                      {product.image ? (
                        <img
                          src={product.image}
                          alt={product.title}
                          className="h-full w-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center">
                          <ShoppingBag className="h-5 w-5 text-white/40" />
                        </div>
                      )}
                    </div>
                    <div className="flex-1">
                      <h4 className="font-semibold text-white">{product.title}</h4>
                      <div className="mt-1 flex items-center gap-2 text-xs text-blue-300">
                        <span>{formatPrice(product.price)}</span>
                        {storeLabel && (
                          <span className="text-[10px] uppercase tracking-wide text-white/50">
                            {storeLabel}
                          </span>
                        )}
                      </div>
                      <div className="mt-2 text-[10px] uppercase tracking-wide text-white/50">
                        선택해서 문의하기
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}
