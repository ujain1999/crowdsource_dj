import { useCallback, useEffect, useRef, useState } from 'react'
import { getClientId, getGuestName } from './session'
import type { ChatMessage, RoomState, You } from './types'

export type RoomStatus = 'connecting' | 'open' | 'reconnecting' | 'not_found' | 'deleted' | 'kicked' | 'left'

const TERMINAL: RoomStatus[] = ['not_found', 'deleted', 'kicked', 'left']

interface Options {
  token: string | null
  onNotice: (text: string, tone?: 'info' | 'error') => void
}

/**
 * The live connection to a room. Keeps the latest server state, the chat log,
 * who "you" are, and an estimate of the server clock so playback lines up.
 */
export function useRoom(roomId: string, { token, onNotice }: Options) {
  const [state, setState] = useState<RoomState | null>(null)
  const [chat, setChat] = useState<ChatMessage[]>([])
  const [you, setYou] = useState<You | null>(null)
  const [status, setStatus] = useState<RoomStatus>('connecting')
  const [endedBy, setEndedBy] = useState<string | null>(null)

  const ws = useRef<WebSocket | null>(null)
  const statusRef = useRef<RoomStatus>('connecting')
  const tokenRef = useRef(token)
  const noticeRef = useRef(onNotice)
  useEffect(() => {
    noticeRef.current = onNotice
  }, [onNotice])
  // Server clock = Date.now()/1000 + offset. Keep the samples with the lowest round trip.
  const clock = useRef<{ offset: number; samples: { rtt: number; offset: number }[] }>({ offset: 0, samples: [] })

  const setStat = (s: RoomStatus) => {
    statusRef.current = s
    setStatus(s)
  }

  const send = useCallback((msg: Record<string, unknown>) => {
    const sock = ws.current
    if (sock && sock.readyState === WebSocket.OPEN) {
      sock.send(JSON.stringify(msg))
      return true
    }
    noticeRef.current('Reconnecting… try again in a second.', 'error')
    return false
  }, [])

  const serverNow = useCallback(() => Date.now() / 1000 + clock.current.offset, [])

  useEffect(() => {
    let closedByUs = false
    let retry = 0
    let pingTimer: number | undefined
    let retryTimer: number | undefined

    const ping = () => {
      const sock = ws.current
      if (sock?.readyState === WebSocket.OPEN) sock.send(JSON.stringify({ type: 'ping', t: Date.now() / 1000 }))
    }

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const params = new URLSearchParams({ client_id: getClientId(), name: getGuestName() })
      if (tokenRef.current) params.set('token', tokenRef.current)
      const sock = new WebSocket(`${proto}://${location.host}/ws/${roomId}?${params}`)
      ws.current = sock

      sock.onopen = () => {
        retry = 0
        setStat('open')
        // A quick burst of pings to learn the clock offset, then a slow heartbeat.
        for (let i = 0; i < 5; i++) setTimeout(ping, i * 200)
        clearInterval(pingTimer)
        pingTimer = window.setInterval(ping, 15000)
      }

      sock.onmessage = (ev) => {
        const msg = JSON.parse(ev.data)
        switch (msg.type) {
          case 'hello':
            setYou(msg.you)
            setChat(msg.chat)
            break
          case 'identity':
            setYou(msg.you)
            break
          case 'state':
            setState(msg.state)
            break
          case 'chat':
            setChat((c) => [...c.slice(-199), msg.message])
            break
          case 'chat_delete':
            setChat((c) => c.filter((m) => m.id !== msg.id))
            break
          case 'pong': {
            const now = Date.now() / 1000
            const rtt = now - msg.t
            const sample = { rtt, offset: msg.server_time - (msg.t + rtt / 2) }
            const c = clock.current
            c.samples = [...c.samples, sample].slice(-10)
            const best = [...c.samples].sort((a, b) => a.rtt - b.rtt).slice(0, 3)
            c.offset = best.reduce((s, x) => s + x.offset, 0) / best.length
            break
          }
          case 'error':
            noticeRef.current(msg.message, 'error')
            break
          case 'toast':
            noticeRef.current(msg.text)
            break
          case 'not_found':
            setStat('not_found')
            break
          case 'room_deleted':
            setEndedBy(msg.by)
            setStat('deleted')
            break
          case 'kicked':
            setEndedBy(msg.by)
            setStat('kicked')
            break
          case 'left':
            setStat('left')
            break
        }
      }

      sock.onclose = () => {
        clearInterval(pingTimer)
        if (closedByUs || TERMINAL.includes(statusRef.current)) return
        setStat('reconnecting')
        retry = Math.min(retry + 1, 6)
        retryTimer = window.setTimeout(connect, Math.min(500 * 2 ** (retry - 1), 8000))
      }
    }

    connect()
    return () => {
      closedByUs = true
      clearInterval(pingTimer)
      clearTimeout(retryTimer)
      ws.current?.close()
    }
  }, [roomId])

  // Logging in or out while in the room switches identity on the live socket.
  useEffect(() => {
    if (tokenRef.current === token) return
    tokenRef.current = token
    const sock = ws.current
    if (sock?.readyState === WebSocket.OPEN) {
      sock.send(JSON.stringify({ type: 'auth', token, client_id: getClientId(), name: getGuestName() }))
    }
  }, [token])

  return { state, chat, you, status, endedBy, send, serverNow }
}
