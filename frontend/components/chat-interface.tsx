"use client"

import { useEffect, useRef, useState } from "react"
import { Send, Square } from "lucide-react"
import { AnimatePresence } from "framer-motion"

import Iridescence from "@/components/ui/Iridescence"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { streamAgentResponse, type ProductCard } from "@/lib/ag-ui"
import ChatHeader from "@/components/chat/ChatHeader"
import EmptyState from "@/components/chat/EmptyState"
import MessageItem from "@/components/chat/MessageItem"
import type { Message } from "@/components/chat/types"
import { extractProducts, mergeToolCalls } from "@/components/chat/utils"

export default function ChatInterface() {
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState("")
    const [isLoading, setIsLoading] = useState(false)
    const [expandedThinkingIds, setExpandedThinkingIds] = useState<Record<string, boolean>>({})
    const isSendingRef = useRef(false)
    const abortRef = useRef<AbortController | null>(null)
    const scrollRef = useRef<HTMLDivElement>(null)
    const threadIdRef = useRef(crypto.randomUUID())
    const slowTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [messages])

    const clearSlowTimer = () => {
        if (slowTimerRef.current) {
            clearTimeout(slowTimerRef.current)
            slowTimerRef.current = null
        }
    }

    const scheduleSlowNotice = (messageId: string) => {
        clearSlowTimer()
        slowTimerRef.current = setTimeout(() => {
            setMessages((prev) =>
                prev.map((msg) => {
                    if (msg.id !== messageId) return msg
                    const thinking = msg.thinking ?? { text: "" }
                    if (thinking.done) return msg
                    if (thinking.status) return msg
                    return {
                        ...msg,
                        thinking: {
                            ...thinking,
                            status: "timeout",
                            done: false,
                        },
                    }
                }),
            )
        }, 12000)
    }

    const handleSend = async (overrideMessage?: string) => {
        const trimmed = (overrideMessage ?? input).trim()
        if (!trimmed || isSendingRef.current || isLoading) return
        isSendingRef.current = true
        setIsLoading(true)
        abortRef.current?.abort()
        abortRef.current = new AbortController()

        const requestMessageId = crypto.randomUUID()
        const responseMessageId = crypto.randomUUID()

        setInput("")
        setMessages((prev) => [
            ...prev,
            { id: requestMessageId, role: "user", content: trimmed },
            { id: responseMessageId, role: "agent", content: "" },
        ])
        scheduleSlowNotice(responseMessageId)

        try {
            await streamAgentResponse({
                url: "/api/chat",
                message: trimmed,
                threadId: threadIdRef.current,
                messageId: requestMessageId,
                signal: abortRef.current.signal,
                onUpdate: (update) => {
                    scheduleSlowNotice(responseMessageId)
                    if (update.thinkingActive && (update.toolCalls || update.todos || update.thinkingText || update.thinkingStatus)) {
                        setExpandedThinkingIds((prev) =>
                            prev[responseMessageId] ? prev : { ...prev, [responseMessageId]: true },
                        )
                    }

                    setMessages((prev) =>
                        prev.map((msg) => {
                            if (msg.id !== responseMessageId) return msg

                            const next = { ...msg }
                            const existingThinking = msg.thinking ?? { text: "" }
                            const nextThinking = { ...existingThinking }
                            let thinkingChanged = false

                            if (update.text !== undefined) {
                                const parsed = extractProducts(update.text)
                                next.content = parsed.display
                                if (parsed.products) {
                                    next.products = parsed.products
                                }
                            }
                            if (update.products) {
                                next.products = update.products
                            }

                            if (update.thinkingText !== undefined) {
                                nextThinking.text = update.thinkingText
                                thinkingChanged = true
                            }
                            if (update.thinkingStatus !== undefined) {
                                nextThinking.status = update.thinkingStatus
                                if (nextThinking.done === undefined) {
                                    nextThinking.done = false
                                }
                                thinkingChanged = true
                            }
                            if (update.thinkingDone !== undefined) {
                                nextThinking.done = update.thinkingDone
                                thinkingChanged = true
                            }
                            if (update.thinkingActive && nextThinking.done === undefined) {
                                nextThinking.done = false
                                thinkingChanged = true
                            }
                            if (update.toolCalls && update.toolCalls.length > 0) {
                                nextThinking.toolCalls = mergeToolCalls(existingThinking.toolCalls ?? [], update.toolCalls)
                                thinkingChanged = true
                            }
                            if (update.todos) {
                                nextThinking.todos = update.todos
                                thinkingChanged = true
                            }

                            if (thinkingChanged) {
                                next.thinking = nextThinking
                            }

                            return next
                        }),
                    )
                },
            })
            setMessages((prev) =>
                prev.map((msg) =>
                    msg.id === responseMessageId && msg.thinking
                        ? { ...msg, thinking: { ...msg.thinking, done: true } }
                        : msg,
                ),
            )
        } catch (error) {
            const err = error as Error | { name?: string; message?: string }
            const isAbort =
                (err && typeof err === "object" && "name" in err && err.name === "AbortError") ||
                (err && typeof err === "object" && "message" in err && String(err.message).includes("aborted"))
            if (!isAbort) {
                console.error("Stream error:", error)
                const rawMessage = String((err as { message?: string }).message ?? "")
                const lower = rawMessage.toLowerCase()
                let fallback = "죄송합니다. 응답 처리 중 문제가 발생했습니다."
                if (lower.includes("timeout") || lower.includes("timed out")) {
                    fallback = "응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
                } else if (lower.includes("network") || lower.includes("socket") || lower.includes("connection")) {
                    fallback = "네트워크 오류로 응답이 중단되었습니다. 연결 상태를 확인해 주세요."
                }
                setMessages((prev) =>
                    prev.map((msg) =>
                        msg.id === responseMessageId
                            ? { ...msg, content: fallback }
                            : msg,
                    ),
                )
            }
        } finally {
            setIsLoading(false)
            isSendingRef.current = false
            abortRef.current = null
            clearSlowTimer()
            setMessages((prev) =>
                prev.map((msg) =>
                    msg.id === responseMessageId && msg.thinking
                        ? { ...msg, thinking: { ...msg.thinking, done: true } }
                        : msg,
                ),
            )
        }
    }

    const handleProductSelect = (product: ProductCard) => {
        const parts = [`이 상품 재고 확인해줘: ${product.title}`]
        if (product.handle) {
            parts.push(`handle: ${product.handle}`)
        }
        if (product.url) {
            parts.push(`url: ${product.url}`)
        }
        handleSend(parts.join("\n"))
    }

    const toggleThinking = (messageId: string) => {
        setExpandedThinkingIds((prev) => ({
            ...prev,
            [messageId]: !prev[messageId],
        }))
    }

    const handleStop = () => {
        if (abortRef.current) {
            abortRef.current.abort()
        }
        clearSlowTimer()
    }

    const handlePaymentComplete = (checkoutId: string) => {
        handleSend(`[System] Payment successful for checkout ID: ${checkoutId}. Please confirm the order to the user.`)
    }

    const visibleMessages = messages.filter((msg) => {
        if (msg.role === "user") return true
        if (msg.content?.trim()) return true
        if (msg.products && msg.products.length > 0) return true
        const isActive = msg.thinking?.done === false
        if (
            msg.thinking &&
            isActive &&
            (msg.thinking.toolCalls?.length ||
                msg.thinking.todos?.length ||
                msg.thinking.text ||
                msg.thinking.status)
        ) {
            return true
        }
        return false
    })

    return (
        <div className="relative flex h-screen w-full items-center justify-center overflow-hidden bg-[#050505] p-4">
            <div className="absolute inset-0">
                <Iridescence
                    color={[0.4, 0.4, 0.6]}
                    mouseReact={false}
                    amplitude={0.1}
                    speed={1.0}
                />
            </div>

            <div className="relative z-10 flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-3xl border border-white/10 bg-black/40 shadow-2xl backdrop-blur-xl">
                <ChatHeader />

                <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4 custom-scrollbar">
                    <AnimatePresence initial={false}>
                        {visibleMessages.length === 0 ? (
                            <EmptyState key="empty" onPreset={setInput} />
                        ) : (
                            visibleMessages.map((msg) => {
                                return (
                                    <MessageItem
                                        key={msg.id}
                                        message={msg}
                                        expanded={expandedThinkingIds[msg.id]}
                                        onToggleThinking={toggleThinking}
                                        onProductSelect={handleProductSelect}
                                        onPaymentComplete={handlePaymentComplete}
                                    />
                                )
                            })
                        )}
                    </AnimatePresence>
                </div >

                <div className="p-4 pb-6">
                    <form
                        onSubmit={(event) => {
                            event.preventDefault()
                            handleSend()
                        }}
                        className="relative flex items-center"
                    >
                        <Input
                            type="text"
                            value={input}
                            onChange={(event) => setInput(event.target.value)}
                            placeholder="무엇을 도와드릴까요?"
                            className="font-spotlight w-full rounded-full border-white/10 bg-white/5 px-6 py-6 pr-14 text-sm text-white placeholder:text-gray-500 focus-visible:ring-blue-500/30 font-medium backdrop-blur-sm shadow-inner transition-all hover:bg-white/10"
                        />
                        <div className="absolute right-2 top-1/2 -translate-y-1/2">
                            <Button
                                type="submit"
                                disabled={!input.trim() && !isLoading}
                                onClick={(event) => {
                                    if (isLoading) {
                                        event.preventDefault()
                                        handleStop()
                                    }
                                }}
                                className={cn(
                                    "h-10 w-10 rounded-full transition-all duration-200 p-0 flex items-center justify-center",
                                    isLoading
                                        ? "bg-white/20 hover:bg-white/30 text-white border border-white/20"
                                        : "bg-white/10 hover:bg-white/20 text-white border border-white/10"
                                )}
                            >
                                {isLoading ? <Square className="h-3 w-3 fill-current" /> : <Send className="h-4 w-4 ml-0.5" />}
                            </Button>
                        </div>
                    </form>
                    <p className="text-center text-[10px] text-gray-500 mt-3 leading-relaxed">
                        AI가 생성한 정보는 정확하지 않을 수 있습니다. 결제 및 개인정보 관련 사항은 반드시 공식 사이트에서 직접 확인해주세요.
                    </p>
                </div>
            </div >
        </div >
    )
}
