"use client"

import { useState } from "react"
import { Check, CreditCard, Loader2 } from "lucide-react"
import { motion } from "framer-motion"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export type CheckoutInfo = {
    checkoutId: string
    url: string
    storeUrl: string
    total?: string
    currency?: string
}

type CheckoutCardProps = {
    info: CheckoutInfo
    onPaymentComplete?: (checkoutId: string) => void
}

export default function CheckoutCard({ info, onPaymentComplete }: CheckoutCardProps) {
    const [status, setStatus] = useState<"idle" | "processing" | "success" | "error">("idle")
    const [message, setMessage] = useState("")

    const formatCurrency = (amount: string | number | undefined, currency: string = "USD") => {
        if (amount === undefined || amount === null) return ""
        const num = typeof amount === "string" ? parseFloat(amount) : amount

        let val = num
        // Standardize: If currency uses decimals (USD, EUR, etc.), assume backend sends CENTS (integer).
        // Exceptions: KRW, JPY usually don't have decimals in standard APIs, or use integers directly.
        // Given our backend sends 14000 for $140.00, we MUST divide by 100 for USD.
        const zeroDecimalCurrencies = ['KRW', 'JPY', 'VND', 'CLP', 'PYG', 'TWD', 'HUF']
        if (!zeroDecimalCurrencies.includes(currency.toUpperCase())) {
            val = num / 100
        }

        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency,
        }).format(val)
    }

    const handlePayment = async () => {
        setStatus("processing")
        setMessage("")

        try {
            // 1. Mock Payment Token (Google Pay Simulation)
            const mockToken = {
                type: "google_pay",
                token: "tok_visa_debit_mock",
                last4: "4242",
            }

            // 2. Call Backend API
            const res = await fetch("http://localhost:8000/api/pay", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    store_url: info.storeUrl,
                    checkout_id: info.checkoutId,
                    payment_token: mockToken,
                }),
            })

            if (!res.ok) {
                throw new Error("Payment API failed")
            }

            const data = await res.json()
            if (data.status === "complete") {
                setStatus("success")
                setMessage("결제가 완료되었습니다!")

                // Notify parent to trigger AI response
                if (onPaymentComplete) {
                    onPaymentComplete(info.checkoutId)
                }
            } else {
                throw new Error(data.error || "Payment failed")
            }
        } catch (err) {
            console.error(err)
            setStatus("error")
            setMessage("결제 처리 중 오류가 발생했습니다.")
        }
    }

    if (status === "success") {
        return (
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="mt-3 flex flex-col items-center justify-center gap-2 rounded-2xl border border-green-500/20 bg-green-500/10 p-6 text-center backdrop-blur-md"
            >
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-500/20 text-green-400 shadow-[0_0_15px_rgba(74,222,128,0.2)]">
                    <Check className="h-6 w-6" />
                </div>
                <div className="font-semibold text-green-100 font-spotlight">결제 성공!</div>
                <div className="text-xs text-green-200/60 font-spotlight">주문이 성공적으로 접수되었습니다.</div>
                <a
                    href={info.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 text-xs text-green-300 underline underline-offset-4 hover:text-green-200 transition-colors font-spotlight"
                >
                    온라인 영수증 보기
                </a>
            </motion.div>
        )
    }

    return (
        <div className="mt-4 overflow-hidden rounded-2xl border border-white/10 bg-white/5 shadow-2xl backdrop-blur-xl">
            {/* Gradient Accent Line */}
            <div className="h-1 w-full bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 opacity-80" />

            <div className="p-5">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-white/10 to-white/5 border border-white/10 shadow-inner">
                            <CreditCard className="h-5 w-5 text-blue-200" />
                        </div>
                        <div>
                            <div className="text-[10px] uppercase tracking-wider text-white/50 font-semibold font-spotlight">Secure Checkout</div>
                            <div className="font-semibold text-white font-spotlight text-sm">결제 확인</div>
                        </div>
                    </div>
                </div>

                <div className="mt-6 flex items-baseline justify-between border-b border-white/5 pb-6">
                    <span className="text-sm text-white/60 font-spotlight">Total Amount</span>
                    <span className="text-2xl font-bold text-white font-spotlight tracking-tight">
                        {info.total ? formatCurrency(info.total, info.currency) : "Calculate..."}
                    </span>
                </div>

                <div className="mt-6 flex flex-col gap-3">
                    <Button
                        onClick={handlePayment}
                        disabled={status === "processing"}
                        className={cn(
                            "relative w-full overflow-hidden bg-white text-black hover:bg-gray-100 h-12 rounded-xl font-medium shadow-[0_0_20px_rgba(255,255,255,0.1)] transition-all active:scale-[0.98] group",
                            status === "error" && "border-red-500/50 bg-red-500/10 text-red-100 hover:bg-red-500/20"
                        )}
                    >
                        {status === "processing" ? (
                            <div className="flex items-center gap-2">
                                <Loader2 className="h-4 w-4 animate-spin text-black" />
                                <span className="text-black/70">Processing...</span>
                            </div>
                        ) : (
                            <div className="flex items-center justify-center gap-2">
                                {/* Simple Google G Logo SVG */}
                                <svg className="w-5 h-5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" /><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" /><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" /><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" /><path d="M1 1h22v22H1z" fill="none" /></svg>
                                <span className="font-semibold text-lg text-[#5F6368] font-sans">Pay</span>
                            </div>
                        )}
                    </Button>

                    <a
                        href={info.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group flex items-center justify-center gap-2 h-10 w-full rounded-xl border border-white/10 bg-white/5 text-xs text-white/60 hover:bg-white/10 hover:text-white transition-all"
                    >
                        <span>Open in Browser</span>
                        <svg className="w-3 h-3 opacity-50 group-hover:opacity-100 transition-opacity" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                    </a>
                </div>

                {message && status === "error" && (
                    <div className="mt-3 text-center text-xs text-red-300 font-spotlight tracking-wide bg-red-500/10 py-2 rounded-lg border border-red-500/20">
                        {message}
                    </div>
                )}
            </div>
        </div>
    )
}
