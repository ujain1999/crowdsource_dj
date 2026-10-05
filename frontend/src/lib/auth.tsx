import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from './api'
import { getToken, setToken } from './session'
import type { User } from './types'
import AuthModal from '../components/AuthModal'

interface AuthState {
  user: User | null
  token: string | null
  ready: boolean
  /** Opens the login / sign-up sheet. Resolves true once the person is logged in. */
  requestLogin: (reason?: string) => Promise<boolean>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState>(null as unknown as AuthState)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTok] = useState<string | null>(getToken())
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(!getToken())
  const [prompt, setPrompt] = useState<{ reason?: string; resolve: (ok: boolean) => void } | null>(null)

  useEffect(() => {
    if (!token) return
    api
      .me()
      .then((r) => setUser(r.user))
      .catch(() => {
        setToken(null)
        setTok(null)
      })
      .finally(() => setReady(true))
    // Only validate the token we started with.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const requestLogin = useCallback(
    (reason?: string) => new Promise<boolean>((resolve) => setPrompt({ reason, resolve })),
    [],
  )

  const logout = useCallback(async () => {
    await api.logout().catch(() => {})
    setToken(null)
    setTok(null)
    setUser(null)
  }, [])

  const finish = (result: { token: string; user: User } | null) => {
    if (result) {
      setToken(result.token)
      setTok(result.token)
      setUser(result.user)
    }
    prompt?.resolve(!!result)
    setPrompt(null)
  }

  return (
    <AuthContext.Provider value={{ user, token, ready, requestLogin, logout }}>
      {children}
      {prompt && <AuthModal reason={prompt.reason} onDone={finish} />}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
