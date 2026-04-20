import { useState } from 'react'
import { apiClient } from '../api/client'

export default function SearchPanel() {
  const [query, setQuery]     = useState('')
  const [results, setResults] = useState([])
  const [summary, setSummary] = useState('')
  const [searching, setSearching] = useState(false)
  const [n, setN]             = useState(8)

  async function handleSearch() {
    if (!query.trim() || searching) return
    setSearching(true); setResults([]); setSummary('')

    const cancel = apiClient.searchStream(
      query, n,
      chunk => {
        if (chunk.startsWith('[SEARCH_RESULTS]')) {
          try {
            const data = JSON.parse(chunk.slice('[SEARCH_RESULTS]'.length))
            setResults(data)
          } catch(e) {}
        } else {
          setSummary(p => p + chunk)
        }
      },
      () => setSearching(false),
      e => { setSummary(`Error: ${e.message}`); setSearching(false) }
    )
  }

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>🌐 Web Search</h2>
        <p className="panel-sub">DuckDuckGo search — no API key needed, fully offline-capable</p>
      </div>

      <div className="panel-body">
        <div className="input-row">
          <input className="panel-input"
            placeholder="Search the web…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
          />
          <select className="panel-select" value={n} onChange={e=>setN(+e.target.value)}>
            {[4,6,8,10].map(v=><option key={v} value={v}>{v} results</option>)}
          </select>
          <button className="btn-run" onClick={handleSearch} disabled={searching||!query.trim()}>
            {searching ? <span className="spinner-sm"/> : '🔍 Search'}
          </button>
        </div>

        {results.length > 0 && (
          <div className="search-results">
            <div className="section-title">Search Results ({results.length})</div>
            {results.map((r, i) => (
              <div key={i} className="search-item">
                <div className="search-item-header">
                  <span className="search-num">[{i+1}]</span>
                  <a href={r.url} target="_blank" rel="noopener noreferrer"
                    className="search-title">{r.title}</a>
                </div>
                <div className="search-url">{r.url?.slice(0, 80)}</div>
                <div className="search-snippet">{r.snippet}</div>
              </div>
            ))}
          </div>
        )}

        {summary && (
          <div className="output-block">
            <div className="section-title" style={{marginBottom:8}}>AI Summary</div>
            <pre style={{whiteSpace:'pre-wrap',fontFamily:'inherit',fontSize:13,lineHeight:1.7}}>
              {summary}
            </pre>
          </div>
        )}

        {!searching && !results.length && !summary && (
          <div className="memory-empty">
            Search the web — results are summarised by AI
          </div>
        )}
      </div>
    </div>
  )
}
