import { useState, type FormEvent } from 'react'
import { api, ApiError } from '../lib/api'
import type { User } from '../lib/types'
import Modal from './Modal'

interface Props {
  reason?: string
  onDone: (result: { token: string; user: User } | null) => void
}

export default function AuthModal({ reason, onDone }: Props) {
  const [mode, setMode] = useState<'login' | 'signup'>('signup')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = mode === 'signup' ? await api.signup(username, password) : await api.login(username, password)
      onDone(result)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={mode === 'signup' ? 'Get a DJ pass' : 'Welcome back'} onClose={() => onDone(null)}>
      <p className="modal-reason">
        {reason ?? 'An account lets you run rooms and be made co-DJ or moderator. Listening never needs one.'}
      </p>
      <div className="seg" role="group" aria-label="Log in or sign up">
        <button type="button" aria-pressed={mode === 'signup'} onClick={() => setMode('signup')}>
          Sign up
        </button>
        <button type="button" aria-pressed={mode === 'login'} onClick={() => setMode('login')}>
          Log in
        </button>
      </div>
      <form onSubmit={submit}>
        <label className="field">
          Username
          <input
            type="text"
            autoFocus
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            minLength={3}
            maxLength={24}
          />
          {mode === 'signup' && <span className="field-hint">3–24 letters, numbers, dots, dashes or underscores.</span>}
        </label>
        <label className="field">
          Password
          <input
            type="password"
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
          />
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="modal-actions">
          <button type="submit" className="btn btn-yellow" disabled={busy}>
            {busy ? 'One sec…' : mode === 'signup' ? 'Create account' : 'Log in'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
