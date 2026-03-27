import React, { useState, useEffect, useRef } from 'react'
import './LandingPage.css'
import * as api from '../utils/api'
import { useAuth } from '../contexts/AuthContext'
import ThemeToggle from '../components/ThemeToggle'
import AuthModal from '../components/AuthModal'

interface LandingPageProps {
  onRoomJoined: (roomCode: string) => void
}

export default function LandingPage({ onRoomJoined }: LandingPageProps) {
  const { user, createGuest, logout } = useAuth()
  const [roomCode, setRoomCode] = useState('')
  const [showAuth, setShowAuth] = useState(false)
  const [showCreateRoom, setShowCreateRoom] = useState(false)
  const [roomName, setRoomName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const firstInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!user) {
      createGuest()
    }
    firstInputRef.current?.focus()
  }, [])

  const handleJoinRoom = async (e: React.FormEvent) => {
    e.preventDefault()
    if (roomCode.length !== 12) return
    setError('')
    setLoading(true)

    try {
      if (!user) {
        await createGuest()
      }
      await api.joinRoom(roomCode)
      onRoomJoined(roomCode)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to join room')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateRoom = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      let currentUser = user
      if (!currentUser) {
        await createGuest()
        const savedUser = localStorage.getItem('user')
        if (savedUser) {
          currentUser = JSON.parse(savedUser)
        }
      }
      const result = await api.createRoom(roomName, currentUser?.id)
      setShowCreateRoom(false)
      setRoomName('')
      onRoomJoined(result.code)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create room')
    } finally {
      setLoading(false)
    }
  }

  const formatRoomCode = (value: string) => {
    const cleaned = value.replace(/[^A-Za-z0-9]/g, '').toUpperCase().slice(0, 12)
    setRoomCode(cleaned)
  }

  const extractRoomCode = (text: string): string => {
    const cleaned = text.replace(/[^A-Za-z0-9]/g, '').toUpperCase()
    if (cleaned.length === 12) {
      return cleaned
    }
    const urlMatch = text.match(/\/([A-Za-z0-9]{12})/)
    if (urlMatch) {
      return urlMatch[1].toUpperCase()
    }
    return cleaned.slice(0, 12)
  }

  return (
    <div className="landing-page">
      {showAuth && <AuthModal onClose={() => setShowAuth(false)} />}

      <header className="landing-header">
        <div className="header-spacer" />
        <div className="header-right">
          <ThemeToggle />
          <div className="profile-dropdown">
            <button className="profile-btn" title="Profile">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
            </button>
            <div className="dropdown-menu">
              {user && (
                <div className="dropdown-user-info">
                  <span className="dropdown-username">{user.username}</span>
                  {!user.is_guest && <span className="dropdown-email">{user.email}</span>}
                  {user.is_guest && <span className="dropdown-guest-badge">Guest</span>}
                </div>
              )}
              <div className="dropdown-divider" />
              {!user?.is_guest && (
                <button className="dropdown-item logout" onClick={logout}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                    <polyline points="16 17 21 12 16 7"/>
                    <line x1="21" y1="12" x2="9" y2="12"/>
                  </svg>
                  Logout
                </button>
              )}
              {user?.is_guest && (
                <button className="dropdown-item" onClick={() => setShowAuth(true)}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
                    <polyline points="10 17 15 12 10 7"/>
                    <line x1="15" y1="12" x2="3" y2="12"/>
                  </svg>
                  Login / Signup
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="landing-main">
        <h1 className="landing-title">Crowdsource DJ</h1>
        <p className="landing-subtitle">Escape the tyranny of the AUX authoritarian</p>

        {error && <div className="error-message">{error}</div>}

        <label className="join-label">Join using a Room ID</label>
        <form className="join-form" onSubmit={handleJoinRoom}>
          <div className="room-code-input">
            {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map((index) => (
              <React.Fragment key={index}>
                <input
                  ref={index === 0 ? firstInputRef : undefined}
                  type="text"
                  className="room-code-char"
                  maxLength={1}
                  value={roomCode[index] || ''}
                  onChange={(e) => {
                    const value = e.target.value.toUpperCase()
                    if (value && index < 11) {
                      const nextInput = document.querySelectorAll('.room-code-char')[index + 1] as HTMLInputElement
                      nextInput?.focus()
                    }
                    const newCode = roomCode.slice(0, index) + value + roomCode.slice(index + 1)
                    setRoomCode(newCode)
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Backspace' && !roomCode[index] && index > 0) {
                      const prevInput = document.querySelectorAll('.room-code-char')[index - 1] as HTMLInputElement
                      prevInput?.focus()
                    }
                  }}
                  onPaste={(e) => {
                    e.preventDefault()
                    const pastedText = e.clipboardData.getData('text')
                    const extractedCode = extractRoomCode(pastedText)
                    setRoomCode(extractedCode)
                    const inputs = document.querySelectorAll('.room-code-char')
                    const focusIndex = Math.min(extractedCode.length, 11)
                    const inputToFocus = inputs[focusIndex] as HTMLInputElement
                    inputToFocus?.focus()
                  }}
                  disabled={loading}
                />
                {(index === 3 || index === 7) && <span className="room-code-hyphen">-</span>}
              </React.Fragment>
            ))}
          </div>
          <button 
            type="submit" 
            className="join-btn" 
            disabled={loading || roomCode.length !== 12}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12"/>
              <polyline points="12 5 19 12 12 19"/>
            </svg>
          </button>
        </form>
        <span className="join-divider">or</span>
        <button className="create-room-link" onClick={() => setShowCreateRoom(true)}>
          Create a new room
        </button>
      </main>

      {showCreateRoom && (
        <div className="modal-overlay" onClick={() => setShowCreateRoom(false)}>
          <div className="create-room-modal" onClick={(e) => e.stopPropagation()}>
            <button className="close-btn" onClick={() => setShowCreateRoom(false)}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
            <h2>What's it called?</h2>
            <form onSubmit={handleCreateRoom}>
              <input
                type="text"
                placeholder="Room Name"
                value={roomName}
                onChange={(e) => setRoomName(e.target.value)}
                disabled={loading}
                autoFocus
              />
              <button type="submit" disabled={loading || !roomName.trim()}>
                {loading ? 'Creating...' : 'Create'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
