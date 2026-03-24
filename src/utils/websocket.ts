const WS_BASE = import.meta.env.VITE_WS_URL || (window.location.protocol === 'https:' ? 'wss://localhost:8000' : 'ws://localhost:8000')

export interface WebSocketMessage {
  type: string
  [key: string]: any
}

export interface WebSocketHandlers {
  onConnectionEstablished?: (data: any) => void
  onPlay?: (data: any) => void
  onPause?: (data: any) => void
  onSeek?: (data: any) => void
  onSkip?: (data: any) => void
  onSongAdded?: (data: any) => void
  onSongRemoved?: (data: any) => void
  onQueueReordered?: (data: any) => void
  onMessage?: (data: any) => void
  onUserJoined?: (data: any) => void
  onUserLeft?: (data: any) => void
  onError?: (error: any) => void
  onDisconnect?: () => void
}

export class WebSocketManager {
  private ws: WebSocket | null = null
  private handlers: WebSocketHandlers = {}
  private heartbeatInterval: any | null = null
  private roomCode: string = ''
  private userId: string = ''
  private username: string = ''

  connect(roomCode: string, userId: string, username: string, handlers: WebSocketHandlers): Promise<void> {
    return new Promise((resolve, reject) => {
      this.roomCode = roomCode
      this.userId = userId
      this.username = username
      this.handlers = handlers

      const url = `${WS_BASE}/api/ws/${roomCode}/${userId}/${username}`

      try {
        this.ws = new WebSocket(url)

        this.ws.onopen = () => {
          this.setupHeartbeat()
          resolve()
        }

        this.ws.onmessage = (event) => {
          this.handleMessage(JSON.parse(event.data))
        }

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error)
          this.handlers.onError?.(error)
          reject(error)
        }

        this.ws.onclose = () => {
          this.cleanup()
          this.handlers.onDisconnect?.()
        }
      } catch (error) {
        reject(error)
      }
    })
  }

  private handleMessage(message: WebSocketMessage) {
    console.log('WebSocket received:', message.type, message)
    
    switch (message.type) {
      case 'connection_established':
        console.log('Connection established with playback state:', message.playback_state)
        this.handlers.onConnectionEstablished?.(message)
        break
      case 'play':
        console.log('Play event received:', message)
        this.handlers.onPlay?.(message)
        break
      case 'pause':
        console.log('Pause event received:', message)
        this.handlers.onPause?.(message)
        break
      case 'seek':
        console.log('Seek event received:', message)
        this.handlers.onSeek?.(message)
        break
      case 'skip':
        console.log('Skip event received:', message)
        this.handlers.onSkip?.(message)
        break
      case 'song_added':
        console.log('Song added event received:', message)
        this.handlers.onSongAdded?.(message)
        break
      case 'song_removed':
        console.log('Song removed event received:', message)
        this.handlers.onSongRemoved?.(message)
        break
      case 'queue_reordered':
        console.log('Queue reordered event received:', message)
        this.handlers.onQueueReordered?.(message)
        break
      case 'message':
        this.handlers.onMessage?.(message)
        break
      case 'user_joined':
        console.log('User joined:', message)
        this.handlers.onUserJoined?.(message)
        break
      case 'user_left':
        console.log('User left:', message)
        this.handlers.onUserLeft?.(message)
        break
      case 'heartbeat':
        // Keep alive response
        break
      default:
        console.warn('Unknown message type:', message.type)
    }
  }

  private setupHeartbeat() {
    if (this.heartbeatInterval) clearInterval(this.heartbeatInterval)
    this.heartbeatInterval = setInterval(() => {
      this.send({ type: 'heartbeat' })
    }, 30000) // Every 30 seconds
  }

  private cleanup() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
  }

  send(message: WebSocketMessage) {
    console.log('Sending WebSocket message:', message)
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    } else {
      console.error('WebSocket not open. Ready state:', this.ws?.readyState)
    }
  }

  play(currentSongId: string, currentTime: number = 0) {
    this.send({ type: 'play', current_song_id: currentSongId, current_time: currentTime })
  }

  pause(currentTime: number = 0) {
    this.send({ type: 'pause', current_time: currentTime })
  }

  seek(currentTime: number, isPlaying: boolean = false) {
    this.send({ type: 'seek', current_time: currentTime, is_playing: isPlaying })
  }

  skip(currentSongId: string, currentTime: number = 0) {
    this.send({ type: 'skip', current_song_id: currentSongId, current_time: currentTime })
  }

  disconnect() {
    this.cleanup()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }
}
