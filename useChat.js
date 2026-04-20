// src/hooks/useChat.js — v3 with MetaAgent events
import { useState, useCallback, useRef } from "react"
import { apiClient } from "../api/client"

let msgCounter = 0
const newId = () => `msg-${++msgCounter}-${Date.now()}`

export function useChat({ sessionId, onAgentStatus }) {
  const [messages, setMessages] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)
  const cancelRef = useRef(null)

  const sendMessage = useCallback(async (text, useAgent = true) => {
    if (isStreaming) return

    // Add user message
    setMessages(prev => [...prev, {
      id: newId(), role:"user", content:text, timestamp:Date.now()
    }])

    // Streaming assistant placeholder
    const placeholderId = newId()
    setMessages(prev => [...prev, {
      id: placeholderId, role:"assistant", content:"",
      agentRole:null, metaStrategy:null, isStreaming:true, timestamp:Date.now()
    }])
    setIsStreaming(true)
    onAgentStatus?.({ role:null, thinking:true })

    let currentRole = null
    let currentStrategy = null

    const cancel = apiClient.chatStream(
      text, sessionId, useAgent,
      // onChunk
      chunk => {
        // Intercept meta/agent markers from SSE data
        if (chunk.startsWith("[META:")) {
          const parts = chunk.slice(6, chunk.indexOf("]")).split(":")
          currentStrategy = parts[0]
          onAgentStatus?.({ role:currentRole, thinking:true, strategy:currentStrategy })
          return
        }
        if (chunk.startsWith("[AGENT:")) {
          currentRole = chunk.slice(7, chunk.indexOf("]"))
          onAgentStatus?.({ role:currentRole, thinking:true, strategy:currentStrategy })
          return
        }
        setMessages(prev => {
          const next = [...prev]
          for (let i = next.length-1; i >= 0; i--) {
            if (next[i].isStreaming) {
              next[i] = { ...next[i],
                content: next[i].content + chunk,
                agentRole: currentRole,
                metaStrategy: currentStrategy,
              }
              break
            }
          }
          return next
        })
      },
      // onDone
      () => {
        setMessages(prev => {
          const next = [...prev]
          for (let i = next.length-1; i >= 0; i--) {
            if (next[i].isStreaming) {
              next[i] = { ...next[i], isStreaming:false,
                agentRole:currentRole, metaStrategy:currentStrategy }
              break
            }
          }
          return next
        })
        setIsStreaming(false)
        onAgentStatus?.({ role:null, thinking:false })
      },
      // onError
      err => {
        if (err?.name === "AbortError") return
        setMessages(prev => {
          const next = [...prev]
          for (let i = next.length-1; i >= 0; i--) {
            if (next[i].isStreaming) {
              next[i] = { ...next[i],
                content: next[i].content || `❌ Error: ${err.message}`,
                isStreaming:false }
              break
            }
          }
          return next
        })
        setIsStreaming(false)
        onAgentStatus?.({ role:null, thinking:false })
      }
    )
    cancelRef.current = cancel
  }, [isStreaming, sessionId, onAgentStatus])

  const clearMessages = useCallback(() => {
    cancelRef.current?.()
    setMessages([])
    setIsStreaming(false)
    onAgentStatus?.({ role:null, thinking:false })
  }, [onAgentStatus])

  return { messages, isStreaming, sendMessage, clearMessages }
}
