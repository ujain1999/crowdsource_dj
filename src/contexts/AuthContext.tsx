import React, { createContext, useContext, useState, useEffect } from 'react'
import * as authAPI from '../utils/auth'
import { logout as apiLogout } from '../utils/api'

export interface User {
  id: string
  username: string
  email?: string
  is_guest: boolean
}

interface AuthContextType {
  user: User | null
  token: string | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, username: string, password: string) => Promise<void>
  createGuest: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const savedToken = localStorage.getItem('token')
    const savedUser = localStorage.getItem('user')
    if (savedToken && savedUser) {
      setToken(savedToken)
      setUser(JSON.parse(savedUser))
    }
    setIsLoading(false)
  }, [])

  const login = async (email: string, password: string) => {
    setIsLoading(true)
    try {
      const result = await authAPI.login(email, password)
      setToken(result.access_token)
      setUser(result.user)
      localStorage.setItem('token', result.access_token)
      localStorage.setItem('user', JSON.stringify(result.user))
    } finally {
      setIsLoading(false)
    }
  }

  const signup = async (email: string, username: string, password: string) => {
    setIsLoading(true)
    try {
      const result = await authAPI.signup(email, username, password)
      setToken(result.access_token)
      setUser(result.user)
      localStorage.setItem('token', result.access_token)
      localStorage.setItem('user', JSON.stringify(result.user))
    } finally {
      setIsLoading(false)
    }
  }

  const createGuest = async () => {
    const existingUser = localStorage.getItem('user')
    if (existingUser) {
      const parsed = JSON.parse(existingUser)
      if (!parsed.is_guest) {
        return
      }
    }
    setIsLoading(true)
    try {
      const user = await authAPI.createGuest()
      setUser(user)
      localStorage.setItem('user', JSON.stringify(user))
    } finally {
      setIsLoading(false)
    }
  }

  const logout = async () => {
    const currentToken = token
    if (currentToken) {
      apiLogout(currentToken)
    }
    setToken(null)
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    await createGuest()
  }

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, signup, createGuest, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
