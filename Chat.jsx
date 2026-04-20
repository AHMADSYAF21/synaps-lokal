import { useState, useRef, useEffect } from "react"
import MessageBubble from "./MessageBubble"
import { useChat } from "../hooks/useChat"

export default function Chat({ onAgentStatus }) {
  const [input, setInput]     = useState("")
  const [useMeta, setUseMeta] = useState(true)   // MetaAgent toggle
  const [sessionId]           = useState(() => `sess-${Date.now().toString(36)}`)
  const bottomRef             = useRef(null)

  const { messages, isStreaming, sendMessage, clearMessages } = useChat({
    sessionId, onAgentStatus,
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior:"smooth" })
  }, [messages])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || isStreaming) return
    setInput("")
    await sendMessage(text, useMeta)
  }

  const handleKey = e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  return (
    <div className="chat-container">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-title">
          <span>SESSION</span>
          <code>{sessionId.slice(-8)}</code>
        </div>
        <div className="chat-controls">
          <label className="meta-toggle" title="Route through MetaAgent (smarter, slower) or direct orchestrator">
            <input type="checkbox" checked={useMeta} onChange={e=>setUseMeta(e.target.checked)}/>
            <span>Meta-AI</span>
          </label>
          <button className="btn-ghost" onClick={clearMessages}>Clear</button>
        </div>
      </div>

      {/* Messages */}
      <div className="messages-area">
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">◈</div>
            <p>Synapse Local v3 — Fully Autonomous</p>
            <p className="empty-sub">
              {useMeta
                ? "Meta-AI active — auto-routes to best strategy"
                : "Direct agent mode — routes by task type"}
            </p>
            <div className="empty-hints">
              <span className="hint-pill">💡 Ask to build something complex</span>
              <span className="hint-pill">🔧 Ask to fix broken code</span>
              <span className="hint-pill">🧠 Ask a hard reasoning question</span>
            </div>
          </div>
        )}
        {messages.map(msg => <MessageBubble key={msg.id} message={msg} />)}
        <div ref={bottomRef}/>
      </div>

      {/* Input */}
      <div className="input-area">
        <div className="input-wrapper">
          <textarea
            className="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder={isStreaming
              ? "AI is thinking…"
              : "Message Synapse… (Enter to send, Shift+Enter for newline)"}
            rows={1}
            disabled={isStreaming}
          />
          <button
            className={`send-btn ${isStreaming?"streaming":""}`}
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
          >
            {isStreaming ? <span className="spinner"/> : "▶"}
          </button>
        </div>
        <div className="input-hint">
          {isStreaming
            ? "Processing…"
            : useMeta
              ? "Meta-AI · Auto-picks: direct | plan | improve | research"
              : "Direct mode · Agent: architect | coder | analyzer | researcher"}
        </div>
      </div>
    </div>
  )
}
