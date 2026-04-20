import { useMemo } from "react"

function escHtml(s) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")
}

function renderMarkdown(text) {
  if (!text) return ""
  return text
    .replace(/```(\w*)\n?([\s\S]*?)```/g, (_,lang,code) =>
      `<pre class="code-block" data-lang="${lang||'code'}"><code>${escHtml(code.trim())}</code></pre>`)
    .replace(/`([^`]+)`/g, (_,c) => `<code class="inline-code">${escHtml(c)}</code>`)
    .replace(/\*\*(.*?)\*\*/g,"<strong>$1</strong>")
    .replace(/\*(.*?)\*/g,"<em>$1</em>")
    .replace(/^### (.+)$/gm,"<h3>$1</h3>")
    .replace(/^## (.+)$/gm,"<h2>$1</h2>")
    .replace(/^# (.+)$/gm,"<h1>$1</h1>")
    .replace(/^- (.+)$/gm,"<li>$1</li>")
    .replace(/(<li>[\s\S]+?<\/li>)/g,"<ul>$1</ul>")
    .replace(/\*\*\[Tool: ([^\]]+)\]\*\*/g,'<span class="tool-badge">⚙ $1</span>')
    .replace(/\[PLAN\]/g,'<span class="plan-badge">◈ PLAN</span>')
    .replace(/\*\*Step (\d+): ([^*]+)\*\*/g,'<span class="step-badge">Step $1: $2</span>')
    .replace(/\n\n/g,"</p><p>")
    .replace(/\n/g,"<br/>")
}

const strategyColors = {
  direct:"#10b981", plan:"#6366f1", improve:"#f59e0b", research:"#06b6d4"
}
const roleColors = {
  architect:"#f59e0b", coder:"#10b981", analyzer:"#6366f1",
  researcher:"#06b6d4", meta:"#00e5a0", reasoning:"#818cf8"
}

export default function MessageBubble({ message }) {
  const { role, content, agentRole, metaStrategy, timestamp, isStreaming } = message

  const html = useMemo(() => {
    if (role === "user") return escHtml(content)
    return renderMarkdown(content)
  }, [content, role])

  const time = new Date(timestamp).toLocaleTimeString([], { hour:"2-digit", minute:"2-digit" })

  return (
    <div className={`message ${role}`}>
      <div className="message-meta">
        {role === "user"
          ? <span className="msg-label user-label">YOU</span>
          : <span className="msg-label ai-label" style={{color: roleColors[agentRole]||"var(--accent)"}}>
              {metaStrategy && (
                <span className="meta-strategy-tag"
                  style={{color:strategyColors[metaStrategy]||"#888"}}>
                  [{metaStrategy}]
                </span>
              )}
              {agentRole ? ` ◈ ${agentRole.toUpperCase()}` : " ◈ SYNAPSE"}
            </span>
        }
        <span className="msg-time">{time}</span>
      </div>

      <div className={`message-bubble ${isStreaming?"streaming":""}`}
           dangerouslySetInnerHTML={{ __html: role==="user" ? content : html }} />

      {isStreaming && (
        <div className="typing-indicator"><span/><span/><span/></div>
      )}
    </div>
  )
}
