import { getToken } from './session'
import type { Track, User } from './types'

export class ApiError extends Error {}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let res: Response
  try {
    res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  } catch {
    throw new ApiError("Can't reach the server. Check your connection.")
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiError(typeof data.detail === 'string' ? data.detail : 'Something went wrong.')
  return data as T
}

export const api = {
  signup: (username: string, password: string) =>
    request<{ token: string; user: User }>('POST', '/api/auth/signup', { username, password }),
  login: (username: string, password: string) =>
    request<{ token: string; user: User }>('POST', '/api/auth/login', { username, password }),
  me: () => request<{ user: User }>('GET', '/api/auth/me'),
  logout: () => request<{ ok: boolean }>('POST', '/api/auth/logout'),
  createRoom: () => request<{ id: string; pretty_id: string }>('POST', '/api/rooms', {}),
  roomInfo: (id: string) =>
    request<{
      id: string
      pretty_id: string
      name: string
      listeners: number
      dj_name: string | null
      now_playing: { title: string; artist: string } | null
    }>('GET', `/api/rooms/${encodeURIComponent(id)}`),
  search: (q: string) => request<{ results: Track[]; is_url?: boolean }>('GET', `/api/search?q=${encodeURIComponent(q)}`),
}
