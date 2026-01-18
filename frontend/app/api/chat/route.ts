import { NextRequest } from "next/server"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function POST(request: NextRequest) {
    try {
        const body = await request.text()

        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"

        const response = await fetch(`${backendUrl}/agent`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "text/event-stream",
            },
            body,
        })

        if (!response.ok) {
            const error = await response.text()
            console.error("Backend error:", error)
            return new Response(error, { status: response.status })
        }

        const contentType = response.headers.get("content-type") ?? "text/event-stream"
        const headers = new Headers()
        headers.set("Content-Type", contentType)
        if (contentType.includes("text/event-stream")) {
            headers.set("Cache-Control", "no-cache")
            headers.set("Connection", "keep-alive")
        }

        return new Response(response.body, {
            status: response.status,
            headers,
        })
    } catch (error) {
        console.error("API Error:", error)
        return new Response(
            JSON.stringify({ error: "Internal server error" }),
            {
                status: 500,
                headers: { "Content-Type": "application/json" },
            }
        )
    }
}
