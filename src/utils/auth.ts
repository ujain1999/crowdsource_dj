const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface AuthResponse {
  access_token: string
  token_type: string
  user: {
    id: string
    username: string
    is_guest: boolean
    created_at: string
  }
}

export interface UserResponse {
  id: string
  username: string
  is_guest: boolean
  created_at: string
}

export async function signup(email: string, username: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE}/api/auth/signup`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, username, password }),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Signup failed')
  }

  return await response.json()
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Login failed')
  }

  return await response.json()
}

export async function createGuest(): Promise<UserResponse> {
  const response = await fetch(`${API_BASE}/api/auth/guest`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to create guest')
  }

  return await response.json()
}
