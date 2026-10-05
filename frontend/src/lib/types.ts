export type Role = 'dj' | 'codj' | 'mod' | 'listener'

export interface User {
  id: number
  username: string
}

export interface You {
  key: string
  name: string
  user: User | null
}

export interface Track {
  video_id: string
  title: string
  artist: string
  album: string | null
  duration: number
  thumb: string
}

export interface QueueEntry extends Track {
  uid: string
  added_by: string
  added_by_key: string | null
  added_at: number
  failed?: boolean
}

export interface Member {
  key: string
  name: string
  role: Role
  is_user: boolean
}

export interface Poll {
  id: string
  track_uid: string
  track_title: string
  started_by: string
  threshold: number
  status: 'open' | 'passed' | 'failed' | 'cancelled'
  reason: string | null
  ends_at: number
  yes: number
  no: number
  eligible: number
  needed: number
  votes: Record<string, boolean>
}

export interface Playback {
  playing: boolean
  position: number
  updated_at: number
  finished: boolean
}

export interface RoomState {
  id: string
  pretty_id: string
  name: string
  dj_key: string | null
  dj_name: string | null
  dj_online: boolean
  settings: { skip_threshold: number }
  members: Member[]
  queue: QueueEntry[]
  current: number
  playback: Playback
  suggestions: Track[]
  suggestions_loading: boolean
  polls: Record<string, Poll>
  server_time: number
}

export interface ChatMessage {
  id: string
  kind: 'user' | 'system' | 'poll'
  text: string
  ts: number
  key: string | null
  name: string | null
  role: Role | null
  poll_id?: string
  event?: string
}

export const ROLE_RANK: Record<Role, number> = { listener: 0, mod: 1, codj: 2, dj: 3 }
export const ROLE_LABEL: Record<Role, string> = { listener: 'Listener', mod: 'Moderator', codj: 'Co-DJ', dj: 'DJ' }
