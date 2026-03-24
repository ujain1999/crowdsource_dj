import React, { useState } from 'react'
import './SearchBar.css'
import * as api from '../utils/api'
import { WebSocketManager } from '../utils/websocket'

interface SearchBarProps {
  roomCode: string
  wsManager: WebSocketManager | null
}

export default function SearchBar({ roomCode, wsManager }: SearchBarProps) {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const isUrl = query.includes('youtube.com') || query.includes('youtu.be')
      await api.addSongToQueue(
        roomCode,
        isUrl ? query : undefined,
        !isUrl ? query : undefined
      )
      setQuery('')
      // Song will be added via WebSocket broadcast
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add song')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form className="search-bar" onSubmit={handleSearch}>
      <div className="search-input-group">
        <input
          type="text"
          placeholder="Search for a song or paste YouTube URL..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !query.trim()}>
          Add to Queue
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
        </button>
      </div>
      {error && <div className="search-error">{error}</div>}
    </form>
  )
}
