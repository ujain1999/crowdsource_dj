import React from 'react'
import './AudioPlayer.css'
import { Song } from '../contexts/RoomContext'
import { WebSocketManager } from '../utils/websocket'

export interface PlaybackEvent {
  type: 'play' | 'pause' | 'seek'
  current_song_id?: string
  current_time: number
}

interface AudioPlayerProps {
  song: Song | null
  wsManager: WebSocketManager | null
  onSongEnd?: () => void
  onPrevious?: () => void
  onNext?: () => void
  queue?: Song[]
  onPlaybackEvent?: (event: PlaybackEvent) => void
  externalPlaybackEvent?: PlaybackEvent | null
  syncPending?: boolean
}

export default function AudioPlayer({ 
  song, 
  wsManager, 
  onSongEnd, 
  onPrevious, 
  onNext, 
  queue,
  onPlaybackEvent,
  externalPlaybackEvent,
  syncPending = false
}: AudioPlayerProps) {
  const [currentTime, setCurrentTime] = React.useState(0)
  const [isPlaying, setIsPlaying] = React.useState(false)
  const audioRef = React.useRef<HTMLAudioElement>(null)
  const isSyncingRef = React.useRef(false)
  const externalSyncRef = React.useRef(false)
  const syncPendingRef = React.useRef(false)
  const lastPlayNotification = React.useRef(0)

  const canGoPrevious = queue && queue.length > 1 && song && queue[0]?.id !== song.id
  const canGoNext = queue && queue.length > 1 && song && queue[queue.length - 1]?.id !== song.id

  React.useEffect(() => {
    syncPendingRef.current = syncPending
  }, [syncPending])

  React.useEffect(() => {
    if (song && audioRef.current) {
      audioRef.current.src = song.url
      if (!syncPendingRef.current) {
        audioRef.current.play().catch((e) => {
          if (e.name !== 'AbortError') {
            console.error('Play error:', e)
          }
        })
        setIsPlaying(true)
        if (!externalSyncRef.current) {
          const now = Date.now()
          if (now - lastPlayNotification.current > 500) {
            console.log('Auto-play detected, notifying backend:', song.id)
            wsManager?.play(song.id, 0)
            lastPlayNotification.current = now
          }
        }
      }
    }
  }, [song])

  // Handle song removal (when song becomes null)
  React.useEffect(() => {
    if (song === null && audioRef.current) {
      console.log('Song removed, pausing audio')
      audioRef.current.pause()
      audioRef.current.src = ''
      setIsPlaying(false)
      setCurrentTime(0)
    }
  }, [song])

  // Handle external playback events from WebSocket
  React.useEffect(() => {
    if (!externalPlaybackEvent || !audioRef.current) {
      console.log('No external playback event or audio ref', { externalPlaybackEvent, hasAudioRef: !!audioRef.current })
      return
    }
    
    console.log('Handling external playback event:', externalPlaybackEvent)
    isSyncingRef.current = true
    
    // Set externalSyncRef BEFORE processing so song effect doesn't send duplicate notifications
    externalSyncRef.current = true
    
    try {
      switch (externalPlaybackEvent.type) {
        case 'play':
          console.log('Syncing: PLAY')
          audioRef.current.play().catch((e) => {
            if (e.name !== 'AbortError') console.error('Play error:', e)
          })
          setIsPlaying(true)
          break
        case 'pause':
          console.log('Syncing: PAUSE')
          audioRef.current.pause()
          setIsPlaying(false)
          break
        case 'seek':
          console.log('Syncing: SEEK to', externalPlaybackEvent.current_time)
          audioRef.current.currentTime = externalPlaybackEvent.current_time
          setCurrentTime(externalPlaybackEvent.current_time)
          break
      }
    } finally {
      isSyncingRef.current = false
      // Delay clearing externalSyncRef to catch any queued events
      setTimeout(() => {
        externalSyncRef.current = false
      }, 50)
    }
  }, [externalPlaybackEvent])

  const handlePlayPause = () => {
    if (audioRef.current && song) {
      if (isPlaying) {
        console.log('USER ACTION: PAUSE at', audioRef.current.currentTime)
        audioRef.current.pause()
        onPlaybackEvent?.({ type: 'pause', current_time: audioRef.current.currentTime })
        wsManager?.pause(audioRef.current.currentTime)
      } else {
        console.log('USER ACTION: PLAY song', song.id, 'at', audioRef.current.currentTime)
        audioRef.current.play()
        onPlaybackEvent?.({ type: 'play', current_song_id: song.id, current_time: audioRef.current.currentTime })
        wsManager?.play(song.id, audioRef.current.currentTime)
      }
      setIsPlaying(!isPlaying)
    }
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value)
    setCurrentTime(time)
    if (audioRef.current) {
      audioRef.current.currentTime = time
      console.log('USER ACTION: SEEK to', time)
    }
    onPlaybackEvent?.({ type: 'seek', current_time: time })
    wsManager?.seek(time, isPlaying)
  }

  const handleTimeUpdate = () => {
    if (audioRef.current && !isSyncingRef.current) {
      setCurrentTime(audioRef.current.currentTime)
    }
  }

  const formatTime = (seconds: number) => {
    if (!seconds || isNaN(seconds)) return '0:00'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div className="audio-player">
      <audio
        ref={audioRef}
        onTimeUpdate={handleTimeUpdate}
        onEnded={() => {
          setIsPlaying(false)
          onSongEnd?.()
        }}
      />

      <div className="now-playing">
        {song ? (
          <>
            {song.thumbnail && (
              <img src={song.thumbnail} alt={song.title} className="thumbnail" />
            )}
            <div className="song-info">
              <h3>{song.title}</h3>
              <p>{song.artist}</p>
            </div>
          </>
        ) : (
          <div className="no-song">No song currently playing</div>
        )}
      </div>

      {song && (
        <div className="player-center">
          <div className="player-controls">
            <button className="prev-btn" onClick={onPrevious} disabled={!canGoPrevious} title="Previous">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M6 6h2v12H6V6zm3.5 6l8.5 6V6l-8.5 6z"/>
              </svg>
            </button>
            <button className="play-pause" onClick={handlePlayPause}>
              {isPlaying ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M8 5v14l11-7z"/>
                </svg>
              )}
            </button>
            <button className="next-btn" onClick={onNext} disabled={!canGoNext} title="Next">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/>
              </svg>
            </button>
          </div>

          <div className="progress">
            <span className="time">{formatTime(currentTime)}</span>
            <input
              type="range"
              className="progress-bar"
              min="0"
              max={song.duration || 0}
              value={currentTime}
              onChange={handleSeek}
            />
            <span className="time">{formatTime(song.duration)}</span>
          </div>
        </div>
      )}
    </div>
  )
}
