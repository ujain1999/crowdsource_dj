import React from 'react'
import './PlayerControls.css'
import { WebSocketManager } from '../utils/websocket'

interface PlayerControlsProps {
  wsManager: WebSocketManager | null
}

export default function PlayerControls({ wsManager }: PlayerControlsProps) {
  const handleSkip = () => {
    // Admin skip - requires current song context from parent
    // wsManager?.skip('current-song-id', 0)
    console.log('Skip triggered - implement in parent component')
  }

  const handlePauseAll = () => {
    // Admin pause - requires current playback context
    // wsManager?.pause(0)
    console.log('Pause triggered - implement in parent component')
  }

  const handlePlayAll = () => {
    // Admin play - requires current song context
    // wsManager?.play('current-song-id', 0)
    console.log('Play triggered - implement in parent component')
  }

  return (
    <div className="player-controls-admin">
      <p className="admin-label">Admin Controls</p>
      <div className="controls-grid">
        <button onClick={handlePlayAll} title="Play">
          ▶ Play
        </button>
        <button onClick={handlePauseAll} title="Pause">
          ⏸ Pause
        </button>
        <button onClick={handleSkip} className="skip-btn" title="Skip">
          ⏭ Skip
        </button>
      </div>
    </div>
  )
}
