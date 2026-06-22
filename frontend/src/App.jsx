import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './App.css'

/**
 * ContextChat — AI Companion Interface with Sidebar
 */

function generateSessionId() {
  return 'session_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9)
}

// ── Icons ──

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}

function MessageIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <line x1="10" y1="11" x2="10" y2="17" />
      <line x1="14" y1="11" x2="14" y2="17" />
    </svg>
  )
}

function SparklesIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
      <path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/>
    </svg>
  )
}

const QUICK_ACTIONS = [
  { text: 'Explain a complex topic' },
  { text: 'Recommend a good movie' },
  { text: 'Write a short poem' },
  { text: 'Help me plan a trip' },
  { text: 'Explain how React works' },
  { text: 'Tell me a fun fact' },
]

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState(() => generateSessionId())
  
  // Sidebar states
  const [pastSessions, setPastSessions] = useState([])
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, isLoading, scrollToBottom])

  // Fetch past sessions on mount and whenever a message completes
  const fetchSessions = useCallback(async () => {
    try {
      // Add a timestamp to prevent the browser from caching the GET request
      const res = await fetch(`/sessions?t=${Date.now()}`)
      const data = await res.json()
      setPastSessions(data.sessions || [])
    } catch (err) {
      console.error('Failed to fetch sessions:', err)
    }
  }, [])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  const loadSession = async (id) => {
    try {
      const res = await fetch(`/session/${id}`)
      const data = await res.json()
      setMessages(data.history || [])
      setSessionId(id)
      if (window.innerWidth <= 768) {
        setIsSidebarOpen(false) // auto-close sidebar on mobile after select
      }
    } catch (err) {
      console.error('Failed to load session:', err)
    }
  }

  const startNewChat = () => {
    setMessages([])
    setSessionId(generateSessionId())
    setInput('')
    fetchSessions()
    if (window.innerWidth <= 768) {
      setIsSidebarOpen(false)
    }
  }

  const deleteSession = async (e, id) => {
    e.stopPropagation() // Prevent selecting the chat
    try {
      await fetch('/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: id }),
      })
      if (id === sessionId) {
        startNewChat()
      } else {
        fetchSessions()
      }
    } catch (err) {
      console.error('Failed to delete session:', err)
    }
  }

  const sendMessage = useCallback(async (text) => {
    const trimmed = (text || input).trim()
    if (!trimmed || isLoading) return

    const userMsg = { role: 'user', content: trimmed }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsLoading(true)

    try {
      const response = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: trimmed,
        }),
      })

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`)
      }

      const data = await response.json()
      const botMsg = { role: 'assistant', content: data.response }
      setMessages(prev => [...prev, botMsg])
      
      // Refresh the sidebar to show the updated title if this was the first message
      fetchSessions()
    } catch (err) {
      const errorMsg = {
        role: 'assistant',
        content: "I'm having trouble connecting right now. Please make sure the backend server is running and try again.",
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [input, isLoading, sessionId, fetchSessions])

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }, [sendMessage])

  const hasMessages = messages.length > 0

  return (
    <div className="app-container">
      {/* ─── Sidebar ─── */}
      <aside className={`sidebar ${isSidebarOpen ? 'open' : ''}`}>
        <button className="btn-new-chat-sidebar" onClick={startNewChat}>
          <PlusIcon />
          <span>New Chat</span>
        </button>
        
        <div className="sidebar-history">
          <h3 className="sidebar-title">Recent Chats</h3>
          {pastSessions.length === 0 ? (
            <p className="sidebar-empty">No past conversations</p>
          ) : (
            <div className="session-list">
              {pastSessions.map(session => (
                <div
                  key={session.session_id}
                  className={`session-item ${session.session_id === sessionId ? 'active' : ''}`}
                  onClick={() => loadSession(session.session_id)}
                >
                  <MessageIcon />
                  <span className="session-title">{session.title}</span>
                  <button 
                    className="btn-delete-session" 
                    onClick={(e) => deleteSession(e, session.session_id)}
                    title="Delete chat"
                  >
                    <TrashIcon />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* Overlay for mobile sidebar */}
      {isSidebarOpen && (
        <div className="sidebar-overlay" onClick={() => setIsSidebarOpen(false)} />
      )}

      {/* ─── Main Chat Area ─── */}
      <div className="main-area">
        <header className="header">
          <div className="header-left">
            <button className="btn-menu" onClick={() => setIsSidebarOpen(true)}>
              <MenuIcon />
            </button>
            <div className="header-logo" aria-hidden="true">AI</div>
            <div className="header-info">
              <h1>AI Companion</h1>
              <div className="header-status">
                <span className="status-dot" />
                <span>General Assistant — Online</span>
              </div>
            </div>
          </div>
        </header>

        {hasMessages ? (
          <main className="messages-container" id="messages-area">
            <div className="messages-inner">
              {messages.map((msg, idx) => (
                <div key={idx} className={`message ${msg.role === 'user' ? 'user' : 'bot'}`}>
                  <div className="message-avatar" aria-hidden="true">
                    {msg.role === 'user' ? 'U' : 'AI'}
                  </div>
                  <div className="message-content">
                    {msg.role === 'assistant' || msg.role === 'bot' ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    ) : (
                      msg.content
                    )}
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="typing-indicator" id="typing-indicator">
                  <div className="message-avatar" aria-hidden="true">AI</div>
                  <div className="typing-dots">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </main>
        ) : (
          <main className="welcome">
            <div className="welcome-icon" aria-hidden="true"><SparklesIcon /></div>
            <h2>Welcome to your AI Companion</h2>
            <p>
              I'm your AI assistant for anything you need. Ask me questions,
              get recommendations, write code, or just chat!
            </p>
            <div className="quick-actions">
              {QUICK_ACTIONS.map((action, idx) => (
                <button
                  key={idx}
                  className="quick-action"
                  onClick={() => sendMessage(action.text)}
                >
                  {action.text}
                </button>
              ))}
            </div>
          </main>
        )}

        <footer className="input-bar">
          <div className="input-wrapper">
            <textarea
              ref={inputRef}
              className="input-field"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything..."
              disabled={isLoading}
              rows={1}
            />
            <button
              className="btn-send"
              onClick={() => sendMessage()}
              disabled={!input.trim() || isLoading}
            >
              <SendIcon />
            </button>
          </div>
        </footer>
      </div>
    </div>
  )
}

export default App
