import { useState, useRef } from 'react'
import { apiClient } from '../api/client'

const TASKS = [
  { id:'describe', label:'🔍 Describe',  hint:'Full image description' },
  { id:'ocr',      label:'📝 OCR',       hint:'Extract all text' },
  { id:'analyze',  label:'📊 Analyze',   hint:'Key information & insights' },
  { id:'code',     label:'💻 Code/Diagram', hint:'Extract code or diagram content' },
  { id:'ui',       label:'🖥 UI',         hint:'Describe interface elements' },
  { id:'data',     label:'📈 Data',       hint:'Extract numbers & data' },
  { id:'qa',       label:'❓ Ask',        hint:'Answer your question about the image' },
]

export default function VisionPanel() {
  const [image, setImage]       = useState(null)   // {data: b64, url: objectURL, name}
  const [task, setTask]         = useState('describe')
  const [question, setQuestion] = useState('')
  const [result, setResult]     = useState('')
  const [loading, setLoading]   = useState(false)
  const [visionAvail, setVisionAvail] = useState(null)
  const fileRef = useRef(null)

  const checkVision = async () => {
    const r = await apiClient.visionTasks()
    setVisionAvail(r.available ? r.model : false)
  }

  useState(() => { checkVision() }, [])

  function handleFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => {
      const b64 = ev.target.result.split(',')[1]
      setImage({ data: b64, url: ev.target.result, name: file.name })
      setResult('')
    }
    reader.readAsDataURL(file)
  }

  function handleDrop(e) {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (file && file.type.startsWith('image/')) {
      const fakeEvent = { target: { files: [file] } }
      handleFile(fakeEvent)
    }
  }

  async function handleAnalyse() {
    if (!image || loading) return
    setLoading(true); setResult('')
    const cancel = apiClient.visionStream(
      image.data, task, task === 'qa' ? question : '',
      chunk => setResult(p => p + chunk),
      () => setLoading(false),
      e => { setResult(`Error: ${e.message}`); setLoading(false) }
    )
  }

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>👁 Vision — Image Analysis</h2>
        <p className="panel-sub">
          {visionAvail
            ? `Model: ${visionAvail} — ready`
            : visionAvail === false
              ? '⚠️ No vision model. Run: ollama pull llava'
              : 'Checking vision model…'}
        </p>
      </div>

      <div className="panel-body">
        {/* Image drop zone */}
        <div className={`vision-dropzone ${image ? 'has-image' : ''}`}
          onDrop={handleDrop}
          onDragOver={e => e.preventDefault()}
          onClick={() => !image && fileRef.current?.click()}>
          <input ref={fileRef} type="file" hidden
            accept="image/*" onChange={handleFile}/>
          {image
            ? <img src={image.url} alt={image.name} className="vision-preview"/>
            : <>
                <div style={{fontSize:40}}>🖼</div>
                <div className="upload-text">Drop image or click to select</div>
                <div className="upload-hint">JPG · PNG · GIF · WebP</div>
              </>
          }
        </div>

        {image && (
          <div className="vision-meta">
            <span>{image.name}</span>
            <button className="btn-sm-ghost" onClick={()=>{setImage(null);setResult('')}}>
              Change image
            </button>
          </div>
        )}

        {/* Task selection */}
        <div className="task-grid">
          {TASKS.map(t => (
            <button key={t.id}
              className={`task-btn ${task===t.id?'active':''}`}
              onClick={() => setTask(t.id)}
              title={t.hint}>
              {t.label}
            </button>
          ))}
        </div>

        {task === 'qa' && (
          <input className="panel-input"
            placeholder="Your question about the image…"
            value={question} onChange={e=>setQuestion(e.target.value)}/>
        )}

        <button className="btn-run" onClick={handleAnalyse}
          disabled={loading || !image || visionAvail === false}>
          {loading ? <><span className="spinner-sm"/> Analysing…</> : '👁 Analyse Image'}
        </button>

        {result && (
          <div className="output-block">
            <pre style={{whiteSpace:'pre-wrap',fontFamily:'inherit',fontSize:13,lineHeight:1.7}}>
              {result}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
