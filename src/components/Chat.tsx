import React, { useState, useEffect, useRef } from 'react'
import './Chat.css'
import { ChatMessage } from '../contexts/RoomContext'
import { useAuth } from '../contexts/AuthContext'
import { WebSocketManager } from '../utils/websocket'
import * as api from '../utils/api'

interface ChatProps {
  roomCode: string
  wsManager: WebSocketManager | null
  messages: ChatMessage[]
  onShowAuth?: () => void
}

export default function Chat({ roomCode, wsManager, messages, onShowAuth }: ChatProps) {
  const { user, token } = useAuth()
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (!user || !token || user.is_guest) {
        setError('Sign in to send messages')
        setLoading(false)
        return
      }

      await api.sendMessage(roomCode, input, token)
      setInput('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat">
      <h3>Chat</h3>

      <div className="messages">
        {messages.length === 0 ? (
          <div className="empty-chat">No messages yet</div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className="message">
              <div className="message-header">
                <span className="username">{msg.user.username}</span>
                <span className="timestamp">
                  {new Date(msg.created_at).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
              <div className="message-content">{msg.content}</div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {!user || user.is_guest ? (
        <div className="chat-lock">
          {onShowAuth ? (
            <button className="chat-auth-btn" onClick={onShowAuth}>
              Sign in to chat
            </button>
          ) : (
            <p>Sign in to chat</p>
          )}
        </div>
      ) : (
        <form className="chat-input" onSubmit={handleSendMessage}>
          {error && <div className="chat-error">{error}</div>}
          <div className="input-group">
            <input
              type="text"
              placeholder="Type a message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            <button type="submit" disabled={loading || !input.trim()}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"/>
                <polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
