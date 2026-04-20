import { useState, useRef, useEffect } from 'react'
import { apiClient } from '../api/client'

export default function VoicePanel() {
  const [status, setStatus]     = useState(null)
  const [voices, setVoices]     = useState([])
  const [ttsEngine, setTtsEngine] = useState('')
  const [recording, setRecording] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [ttsText, setTtsText]   = useState('')
  const [selVoice, setSelVoice] = useState('')
  const [speed, setSpeed]       = useState(1.0)
  const [audioUrl, setAudioUrl] = useState(null)
  const [loading, setLoading]   = useState(false)
  const [lang, setLang]         = useState('auto')
  const recorderRef = useRef(null)
  const chunksRef   = useRef([])

  useEffect(() => { loadStatus() }, [])

  async function loadStatus() {
    try {
      const r = await apiClient.voiceStatus()
      setStatus(r)
      if (r.tts_available) {
        const v = await apiClient.voiceVoices()
        setVoices(v.voices || [])
        setTtsEngine(v.engine)
        if (v.voices?.length > 0) setSelVoice(v.voices[0].name)
      }
    } catch(e) { console.error(e) }
  }

  // ── Recording ────────────────────────────────────────────────────
  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = e => chunksRef.current.push(e.data)
      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        stream.getTracks().forEach(t => t.stop())
        await transcribeBlob(blob)
      }
      recorder.start()
      recorderRef.current = recorder
      setRecording(true)
    } catch(e) {
      alert(`Microphone error: ${e.message}`)
    }
  }

  function stopRecording() {
    recorderRef.current?.stop()
    setRecording(false)
  }

  async function transcribeBlob(blob) {
    setLoading(true); setTranscript('')
    try {
      const file = new File([blob], 'recording.webm', { type: 'audio/webm' })
      const r = await apiClient.voiceTranscribe(file, lang)
      if (r.success) {
        setTranscript(r.text)
        setTtsText(r.text) // auto-fill TTS box
      } else {
        setTranscript(`Error: ${r.error}`)
      }
    } catch(e) { setTranscript(`Error: ${e.message}`) }
    finally { setLoading(false) }
  }

  async function handleFileUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setLoading(true); setTranscript('')
    try {
      const r = await apiClient.voiceTranscribe(file, lang)
      setTranscript(r.success ? r.text : `Error: ${r.error}`)
    } catch(e) { setTranscript(`Error: ${e.message}`) }
    finally { setLoading(false) }
  }

  async function handleTTS() {
    if (!ttsText.trim() || loading) return
    setLoading(true)
    if (audioUrl) { URL.revokeObjectURL(audioUrl); setAudioUrl(null) }
    try {
      const blob = await apiClient.voiceTTS(ttsText, selVoice, speed)
      const url  = URL.createObjectURL(blob)
      setAudioUrl(url)
    } catch(e) { alert(`TTS error: ${e.message}`) }
    finally { setLoading(false) }
  }

  const sttOk = status?.stt_available
  const ttsOk = status?.tts_available

  return (
    <div className="generic-panel">
      <div className="panel-header">
        <h2>🎙 Voice</h2>
        <p className="panel-sub">
          STT: {sttOk ? `✅ Whisper` : '❌ pip install faster-whisper'} ·
          TTS: {ttsOk ? `✅ ${ttsEngine}` : '❌ pip install edge-tts'}
        </p>
      </div>

      <div className="panel-body">
        {/* ── STT Section ── */}
        <div className="voice-section">
          <div className="section-title">🎤 Speech → Text</div>
          <div className="control-row" style={{marginBottom:8}}>
            <select className="panel-select" value={lang} onChange={e=>setLang(e.target.value)}>
              <option value="auto">Auto-detect language</option>
              <option value="en">English</option>
              <option value="id">Indonesian</option>
              <option value="zh">Chinese</option>
              <option value="es">Spanish</option>
              <option value="fr">French</option>
              <option value="de">German</option>
              <option value="ja">Japanese</option>
            </select>
            <label className="btn-run" style={{cursor:'pointer'}}>
              📁 Upload Audio
              <input type="file" hidden accept="audio/*" onChange={handleFileUpload}/>
            </label>
          </div>

          <div className="voice-record-area">
            <button
              className={`record-btn ${recording ? 'recording' : ''}`}
              onClick={recording ? stopRecording : startRecording}
              disabled={!sttOk || loading}>
              {recording ? '⏹ Stop' : '⏺ Record'}
            </button>
            {recording && <div className="record-pulse">🔴 Recording…</div>}
            {loading && !recording && <div className="record-pulse">⏳ Transcribing…</div>}
          </div>

          {transcript && (
            <div className="transcript-box">
              <div className="section-title" style={{marginBottom:6}}>Transcript</div>
              <p style={{fontSize:13,lineHeight:1.7}}>{transcript}</p>
            </div>
          )}
        </div>

        {/* ── TTS Section ── */}
        <div className="voice-section">
          <div className="section-title">🔊 Text → Speech</div>
          <textarea className="panel-textarea" rows={4}
            placeholder="Enter text to speak…"
            value={ttsText} onChange={e=>setTtsText(e.target.value)}/>

          <div className="control-row">
            <select className="panel-select" value={selVoice}
              onChange={e=>setSelVoice(e.target.value)}>
              {voices.slice(0,30).map(v=>(
                <option key={v.name} value={v.name}>
                  {v.name} ({v.gender || v.lang})
                </option>
              ))}
            </select>
            <div className="speed-ctrl">
              <label className="form-label">Speed</label>
              <input type="range" min="0.5" max="2" step="0.1"
                value={speed} onChange={e=>setSpeed(+e.target.value)}
                style={{width:80}}/>
              <span style={{fontFamily:'var(--font-mono)',fontSize:11}}>{speed}×</span>
            </div>
            <button className="btn-run" onClick={handleTTS}
              disabled={loading || !ttsOk || !ttsText.trim()}>
              {loading ? <span className="spinner-sm"/> : '🔊 Speak'}
            </button>
          </div>

          {audioUrl && (
            <audio controls autoPlay src={audioUrl}
              style={{width:'100%',marginTop:8}}
              onEnded={()=>{URL.revokeObjectURL(audioUrl)}}/>
          )}
        </div>
      </div>
    </div>
  )
}
