export default function AgentStatus({ status }) {
  const { role, thinking, strategy } = status

  const roleColors = {
    architect:"#f59e0b", coder:"#10b981",
    analyzer:"#6366f1", researcher:"#06b6d4",
    meta:"#00e5a0", reasoning:"#818cf8",
  }
  const roleIcons = {
    architect:"⬡", coder:"⌨", analyzer:"◉",
    researcher:"◎", meta:"◈", reasoning:"∿",
  }
  const strategyColors = {
    direct:"#10b981", plan:"#6366f1",
    improve:"#f59e0b", research:"#06b6d4",
  }

  if (!role && !thinking) return (
    <div className="agent-status idle">
      <span className="status-dot idle-dot"/>
      <span className="idle-label">Idle</span>
    </div>
  )

  return (
    <div className="agent-status active"
         style={{borderColor: roleColors[role]||"#444"}}>
      <span className="status-dot active-dot"
            style={{background: roleColors[role]||"#888"}}/>
      <div className="agent-info">
        <span className="agent-icon">{roleIcons[role]||"◈"}</span>
        <div className="agent-detail">
          <span className="agent-role">{role?.toUpperCase()||"ROUTING…"}</span>
          {strategy && (
            <span className="agent-strategy"
                  style={{color:strategyColors[strategy]||"#888"}}>
              [{strategy}]
            </span>
          )}
        </div>
      </div>
      {thinking && <div className="agent-thinking">thinking…</div>}
    </div>
  )
}
