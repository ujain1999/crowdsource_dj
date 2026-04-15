import React, { useEffect, useState } from 'react'
import './RoomPage.css'
import { useAuth } from '../contexts/AuthContext'
import { useRoom, Song } from '../contexts/RoomContext'
import { useTheme } from '../contexts/ThemeContext'
import * as api from '../utils/api'
import { WebSocketManager } from '../utils/websocket'
import SearchBar from '../components/SearchBar'
import Queue from '../components/Queue'
import AudioPlayer, { PlaybackEvent } from '../components/AudioPlayer'
import Chat from '../components/Chat'
import ThemeToggle from '../components/ThemeToggle'

interface RoomPageProps {
  roomCode: string
  onLeaveRoom: () => void
  onShowAuth: () => void
}

export default function RoomPage({ roomCode, onLeaveRoom, onShowAuth }: RoomPageProps) {
  const { user, createGuest, logout } = useAuth()
  const {
    queue,
    messages,
    roomUsers,
    currentSong,
    isAdmin,
    setRoomUsers,
    setIsAdmin,
    addToQueue,
    removeFromQueue,
    reorderQueue,
    setCurrentSong,
    addMessage,
    addRoomUser,
  } = useRoom()
  const [wsManager, setWsManager] = useState<WebSocketManager | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [roomName, setRoomName] = useState('')
  const [externalPlaybackEvent, setExternalPlaybackEvent] = useState<PlaybackEvent | null>(null)
  const [lastSkipEvent, setLastSkipEvent] = useState<any>(null)
  const [showCopied, setShowCopied] = useState(false)
  const [syncPending, setSyncPending] = useState(false)
  const wsManagerRef = React.useRef<WebSocketManager | null>(null)
  const initializingRef = React.useRef(false)
  const initialPlaybackStateRef = React.useRef<any>(null)
  const queueRef = React.useRef<Song[]>([])
  const currentSongRef = React.useRef<Song | null>(null)

  useEffect(() => {
    queueRef.current = queue
  }, [queue])

  useEffect(() => {
    currentSongRef.current = currentSong
  }, [currentSong])

  // Sync initial playback state once queue is loaded
  useEffect(() => {
    if (!initialPlaybackStateRef.current || queue.length === 0) {
      return
    }

    const state = initialPlaybackStateRef.current
    console.log('Syncing initial playback state with loaded queue:', state)
    
    if (state.current_song_id) {
      const song = queue.find(s => s.id === state.current_song_id)
      if (song) {
        console.log('Found initial song:', song.title)
        setCurrentSong(song)
        
        // Sync playback position
        setTimeout(() => {
          if (state.current_time > 0) {
            console.log('Seeking to', state.current_time)
            setExternalPlaybackEvent({
              type: 'seek',
              current_time: state.current_time
            })
          }
          
          if (state.is_playing) {
            console.log('Playing from position', state.current_time)
            setExternalPlaybackEvent({
              type: 'play',
              current_song_id: state.current_song_id,
              current_time: state.current_time
            })
          } else if (state.current_time > 0) {
            console.log('Paused at position', state.current_time)
            setExternalPlaybackEvent({
              type: 'pause',
              current_time: state.current_time
            })
          }
        }, 100)
      } else {
        console.error('Initial song not found in queue:', state.current_song_id)
      }
    }
    
    // Clear the ref so we don't sync again
    initialPlaybackStateRef.current = null
  }, [queue])

  // Handle skip events with current queue
  useEffect(() => {
    if (!lastSkipEvent) return
    
    console.log('Processing skip event with current queue:', lastSkipEvent)
    console.log('Queue IDs:', queue.map(s => s.id))
    
    if (lastSkipEvent.current_song_id) {
      const song = queue.find(s => s.id === lastSkipEvent.current_song_id)
      if (song) {
        console.log('Skip: Found song', song.title)
        setCurrentSong(song)
      } else {
        console.error('Skip: Song not found with ID:', lastSkipEvent.current_song_id)
      }
    }
    
    // Clear the skip event
    setLastSkipEvent(null)
  }, [lastSkipEvent, queue])

  // Initialize room connection
  useEffect(() => {
    if (initializingRef.current) return
    initializingRef.current = true

    const initialize = async () => {
      try {
        // Disconnect any existing connection
        if (wsManagerRef.current) {
          wsManagerRef.current.disconnect()
        }

        // Ensure user exists and get updated user
        let currentUser = user
        if (!currentUser) {
          await createGuest()
          // Read the created guest user from localStorage
          const savedUser = localStorage.getItem('user')
          if (savedUser) {
            currentUser = JSON.parse(savedUser)
          }
        }

        if (!currentUser?.id) {
          throw new Error('Failed to get user ID')
        }

        // Get room details
        const roomData = await api.getRoomDetails(roomCode)
        setRoomName(roomData.name)

        // Load existing queue (update ref immediately so WebSocket callback can use it)
        if (roomData.queue && roomData.queue.length > 0) {
          console.log('Loading existing queue:', roomData.queue)
          const queueItems = roomData.queue.map((song: any) => ({
            id: song.id,
            song_id: song.song_id,
            title: song.title,
            artist: song.artist,
            duration: song.duration,
            thumbnail: song.thumbnail,
            url: song.url,
            added_by: song.added_by,
            position: song.position
          }))
          queueRef.current = queueItems
          roomData.queue.forEach((song: any) => addToQueue(song))
        }

        // Determine if current user is admin
        const isCurrentUserAdmin = roomData.admin_id === currentUser.id
        setIsAdmin(isCurrentUserAdmin)
        console.log(`Admin check: roomAdmin=${roomData.admin_id}, currentUser=${currentUser.id}, isAdmin=${isCurrentUserAdmin}`)

        // Get existing messages
        const msgs = await api.getMessages(roomCode)
        msgs.forEach((msg: any) => addMessage(msg))

        // Connect WebSocket
        const ws = new WebSocketManager()
        await ws.connect(roomCode, currentUser.id, currentUser.username, {
          onConnectionEstablished: (data) => {
            console.log('Connected to room:', data)
            setRoomUsers(data.users.map((u: string) => ({ id: u, username: u })))
            
            // Sync immediately if queue is ready (check ref which updates immediately)
            if (data.playback_state && data.playback_state.current_song_id) {
              const state = data.playback_state
              const song = queueRef.current.find(s => s.id === state.current_song_id)
              
              if (song) {
                console.log('Immediate sync: Found song', song.title, 'at time', state.current_time)
                setCurrentSong(song)
                setSyncPending(true)
                
                // Direct DOM manipulation to sync audio - bypass React state
                setTimeout(() => {
                  const audio = document.querySelector('audio') as HTMLAudioElement
                  if (audio) {
                    audio.src = song.url
                    audio.currentTime = state.current_time
                    console.log('Set audio.currentTime to', state.current_time)
                    if (state.is_playing) {
                      audio.play().catch((e: any) => {
                        if (e.name !== 'AbortError') console.error('Play error:', e)
                      })
                      console.log('Playing')
                      // Also set external event so AudioPlayer updates its state
                      setExternalPlaybackEvent({
                        type: 'play',
                        current_song_id: state.current_song_id,
                        current_time: state.current_time
                      })
                    }
                  }
                  setSyncPending(false)
                }, 50)
              } else {
                console.log('Queue not ready in callback, storing for sync effect')
                initialPlaybackStateRef.current = state
              }
            }
          },
          onUserJoined: (data) => {
            console.log('User joined:', data.username)
            addRoomUser({ id: data.username, username: data.username })
          },
          onSongAdded: (data) => {
            console.log('Song added:', data.song)
            addToQueue(data.song)
          },
          onMessage: (data) => {
            console.log('Message:', data)
            addMessage(data)
          },
          onPlay: (data) => {
            console.log('=== ROOM PAGE: Play event received ===', data)
            setExternalPlaybackEvent({
              type: 'play',
              current_song_id: data.current_song_id,
              current_time: data.current_time
            })
          },
          onPause: (data) => {
            console.log('=== ROOM PAGE: Pause event received ===', data)
            setExternalPlaybackEvent({
              type: 'pause',
              current_time: data.current_time
            })
          },
          onSeek: (data) => {
            console.log('=== ROOM PAGE: Seek event received ===', data)
            setExternalPlaybackEvent({
              type: 'seek',
              current_time: data.current_time
            })
          },
          onSkip: (data) => {
            console.log('=== WebSocket: Skip event received ===', data)
            // Store the skip event to be processed with the current queue
            setLastSkipEvent(data)
          },
          onSongRemoved: (data) => {
            console.log('=== Song removed event received ===', data)
            const removedSongId = data.song_id
            const wasPlaying = currentSongRef.current?.id === removedSongId
            
            // Find the index of the removed song in current queue for determining next song
            const removedIndex = queueRef.current.findIndex(s => s.id === removedSongId)
            console.log('Song removed. wasPlaying:', wasPlaying, 'removedIndex:', removedIndex, 'currentSong:', currentSongRef.current?.id)
            
            // Reload room to get fresh queue state from backend
            api.getRoomDetails(roomCode).then(roomData => {
              if (roomData.queue && roomData.queue.length > 0) {
                const newQueue = roomData.queue.map((item: any) => ({
                  id: item.id,
                  song_id: item.song_id,
                  title: item.title,
                  artist: item.artist,
                  duration: item.duration,
                  thumbnail: item.thumbnail,
                  url: item.url,
                  added_by: item.added_by,
                  position: item.position
                }))
                console.log('New queue loaded, setting new queue')
                reorderQueue(newQueue)
                
                // If the removed song was playing, switch to the next song
                if (wasPlaying) {
                  console.log('Removed song was playing, switching to next song')
                  if (removedIndex !== -1 && removedIndex < newQueue.length) {
                    console.log('Setting current song to:', newQueue[removedIndex].title)
                    setCurrentSong(newQueue[removedIndex])
                  } else if (newQueue.length > 0) {
                    console.log('Setting current song to last:', newQueue[newQueue.length - 1].title)
                    setCurrentSong(newQueue[newQueue.length - 1])
                  }
                }
              } else {
                console.log('Queue is empty after removal')
                reorderQueue([])
                if (wasPlaying) {
                  console.log('Was playing, stopping playback')
                  setCurrentSong(null)
                }
              }
            })
          },
          onQueueReordered: (data) => {
            console.log('=== Queue reordered event received ===', data)
            // Reload room to get fresh queue state from backend
            api.getRoomDetails(roomCode).then(roomData => {
              if (roomData.queue) {
                const newQueue = roomData.queue.map((item: any) => ({
                  id: item.id,
                  song_id: item.song_id,
                  title: item.title,
                  artist: item.artist,
                  duration: item.duration,
                  thumbnail: item.thumbnail,
                  url: item.url,
                  added_by: item.added_by,
                  position: item.position
                }))
                reorderQueue(newQueue)
              }
            })
          },
          onError: (error) => {
            console.error('WebSocket error:', error)
            setError('Connection error')
          },
          onDisconnect: () => {
            console.log('Disconnected')
          },
        })

        wsManagerRef.current = ws
        setWsManager(ws)
        setLoading(false)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to initialize room')
        setLoading(false)
        initializingRef.current = false
      }
    }

    initialize()

    return () => {
      wsManagerRef.current?.disconnect()
    }
  }, [roomCode])

  const handleLeaveRoom = () => {
    wsManager?.disconnect()
    onLeaveRoom()
  }

  const handleSongEnd = () => {
    if (queue.length > 1) {
      const currentIndex = queue.findIndex(s => s.id === currentSong?.id)
      if (currentIndex < queue.length - 1) {
        const nextSong = queue[currentIndex + 1]
        console.log('SONG ENDED: Auto-playing next song', nextSong.title)
        setCurrentSong(nextSong)
        wsManager?.skip(nextSong.id, 0)
      }
    }
  }

  const handlePreviousSong = () => {
    const currentIndex = queue.findIndex(s => s.id === currentSong?.id)
    if (currentIndex > 0) {
      const prevSong = queue[currentIndex - 1]
        console.log('USER ACTION: PREVIOUS to', prevSong.title)
      setCurrentSong(prevSong)
      wsManager?.skip(prevSong.id, 0)
    }
  }

  const handleNextSong = () => {
    const currentIndex = queue.findIndex(s => s.id === currentSong?.id)
    if (currentIndex < queue.length - 1) {
      const nextSong = queue[currentIndex + 1]
        console.log('USER ACTION: NEXT to', nextSong.title)
      setCurrentSong(nextSong)
      wsManager?.skip(nextSong.id, 0)
    }
  }

  const handleQueueItemClick = (song: Song) => {
    console.log('USER ACTION: CLICK QUEUE ITEM', song.title)
    setCurrentSong(song)
    wsManager?.skip(song.id, 0)
  }

  const handleQueueReorder = async (newQueue: Song[]) => {
    console.log('USER ACTION: REORDER QUEUE')
    reorderQueue(newQueue)
    
    // Find which song moved
    for (let i = 0; i < queue.length; i++) {
      if (queue[i].id !== newQueue[i].id) {
        // Found the song that moved
        const fromIndex = queue.findIndex(s => s.id === newQueue[i].id)
        console.log(`Sending reorder API call: from ${fromIndex} to ${i}`)
        try {
          await api.reorderQueue(roomCode, fromIndex, i)
        } catch (err) {
          console.error('Failed to reorder queue:', err)
        }
        break
      }
    }
  }

  const handleRemoveFromQueue = async (songId: string) => {
    console.log('USER ACTION: REMOVE SONG', songId)
    removeFromQueue(songId)
    
    try {
      await api.removeSongFromQueue(roomCode, songId)
    } catch (err) {
      console.error('Failed to remove song:', err)
    }
  }

  if (loading) {
    return <div className="room-page"><div className="loading">Loading...</div></div>
  }

  if (error) {
    return <div className="room-page"><div className="error">{error}</div></div>
  }

  return (
    <div className="room-page">
      <div className="room-header">
        <div className="header-left">
          <h1>Crowdsource DJ{roomName ? `: ${roomName}` : ''}</h1>
          <div className="room-code-wrapper">
            <span 
              className="room-code"
              onClick={() => {
                navigator.clipboard.writeText(window.location.href)
                setShowCopied(true)
                setTimeout(() => setShowCopied(false), 2000)
              }}
            >
              {roomCode.slice(0, 4)}-{roomCode.slice(4, 8)}-{roomCode.slice(8, 12)}
            </span>
            <span className={`copy-hint${showCopied ? ' copied' : ''}`}>
              {showCopied ? 'Copied to clipboard' : 'Copy URL'}
            </span>
          </div>
        </div>
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
                <>
                  <button className="dropdown-item" onClick={() => {}}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="3"/>
                      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
                    </svg>
                    Preferences
                  </button>
                </>
              )}
              {user?.is_guest && (
                <button className="dropdown-item" onClick={onShowAuth}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
                    <polyline points="10 17 15 12 10 7"/>
                    <line x1="15" y1="12" x2="3" y2="12"/>
                  </svg>
                  Login / Signup
                </button>
              )}
              <button className="dropdown-item" onClick={handleLeaveRoom}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                  <polyline points="16 17 21 12 16 7"/>
                  <line x1="21" y1="12" x2="9" y2="12"/>
                </svg>
                Leave Room
              </button>
              {!user?.is_guest && (
                <button className="dropdown-item logout" onClick={() => { logout(); handleLeaveRoom(); }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                    <polyline points="16 17 21 12 16 7"/>
                    <line x1="21" y1="12" x2="9" y2="12"/>
                  </svg>
                  Logout
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="room-layout">
        <div className="content-area">
          <div className="left-panel">
            <SearchBar roomCode={roomCode} wsManager={wsManager} />
            <div className="queue-section">
              <Queue
                songs={queue}
                isAdmin={isAdmin}
                currentSong={currentSong}
                onSongClick={handleQueueItemClick}
                onReorder={handleQueueReorder}
                onRemove={handleRemoveFromQueue}
              />
            </div>
          </div>

          <div className="sidebar">
            <Chat roomCode={roomCode} wsManager={wsManager} messages={messages} onShowAuth={onShowAuth} />
          </div>
        </div>

        <div className="player-footer">
          <AudioPlayer
            song={currentSong}
            wsManager={wsManager}
            onSongEnd={handleSongEnd}
            onPrevious={handlePreviousSong}
            onNext={handleNextSong}
            queue={queue}
            externalPlaybackEvent={externalPlaybackEvent}
            syncPending={syncPending}
          />
        </div>
      </div>
    </div>
  )
}
