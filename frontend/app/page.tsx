import ChatInterface from "@/components/chat-interface"

export default function Home() {
  return (
    <main className="min-h-screen bg-[var(--app-bg)] text-[var(--app-ink)]">
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.18),_transparent_55%)]" />
        <div className="absolute inset-0 opacity-[0.4] [background-image:linear-gradient(rgba(148,163,184,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.08)_1px,transparent_1px)] [background-size:120px_120px]" />
      </div>
      <div className="relative">
        <ChatInterface />
      </div>
    </main>
  )
}
