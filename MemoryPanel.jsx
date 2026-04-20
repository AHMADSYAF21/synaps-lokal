import { useState, useEffect } from "react"
import { apiClient } from "../api/client"

export default function MemoryPanel() {
  const [memories, setMemories] = useState([])
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState("recent") // recent | search

  useEffect(() => {
    loadMemories()
  }, [])

  async function loadMemories() {
    setLoading(true)
    try {
      const data = await apiClient.listMemory("default", 30)
      setMemories(data.memories || [])
    } catch (e) {
      console.error("Memory load error:", e)
    } finally {
      setLoading(false)
    }
  }

  async function handleSearch() {
    if (!searchQuery.trim()) return
    setLoading(true)
    try {
      const data = await apiClient.searchMemory(searchQuery, 10)
      setSearchResults(data.results || [])
      setTab("search")
    } catch (e) {
      console.error("Search error:", e)
    } finally {
      setLoading(false)
    }
  }

  async function handleClear() {
    if (!confirm("Clear all conversation memory?")) return
    await apiClient.clearMemory("default")
    setMemories([])
    setSearchResults([])
  }

  const displayList = tab === "search" ? searchResults : memories

  return (
    <div className="memory-panel">
      <div className="memory-header">
        <h2>◎ Memory</h2>
        <button className="btn-danger-sm" onClick={handleClear}>Clear All</button>
      </div>

      {/* Search */}
      <div className="memory-search">
        <input
          type="text"
          placeholder="Semantic search memories…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          className="memory-input"
        />
        <button className="btn-primary-sm" onClick={handleSearch}>Search</button>
        {tab === "search" && (
          <button className="btn-ghost-sm" onClick={() => setTab("recent")}>← Recent</button>
        )}
      </div>

      {/* Tabs */}
      <div className="memory-tabs">
        <button
          className={`mem-tab ${tab === "recent" ? "active" : ""}`}
          onClick={() => setTab("recent")}
        >
          Recent ({memories.length})
        </button>
        <button
          className={`mem-tab ${tab === "search" ? "active" : ""}`}
          onClick={() => setTab("search")}
        >
          Search Results ({searchResults.length})
        </button>
      </div>

      {/* List */}
      {loading ? (
        <div className="memory-loading">Loading…</div>
      ) : displayList.length === 0 ? (
        <div className="memory-empty">
          {tab === "search" ? "No results found" : "No memories yet — start chatting!"}
        </div>
      ) : (
        <div className="memory-list">
          {displayList.map((mem, i) => (
            <div key={i} className="memory-item">
              {mem.relevance !== undefined && (
                <div className="relevance-bar">
                  <div
                    className="relevance-fill"
                    style={{ width: `${mem.relevance * 100}%` }}
                  />
                  <span className="relevance-score">{(mem.relevance * 100).toFixed(0)}%</span>
                </div>
              )}
              <p className="memory-text">{mem.text?.slice(0, 300)}…</p>
              <div className="memory-meta">
                {mem.metadata?.session_id && (
                  <span className="mem-tag">session: {mem.metadata.session_id}</span>
                )}
                {mem.metadata?.timestamp && (
                  <span className="mem-tag">
                    {new Date(mem.metadata.timestamp * 1000).toLocaleString()}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
