import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { formatRoomId } from '../lib/session'
import Vinyl from '../components/Record'

export default function Landing() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, requestLogin, logout } = useAuth()
  const [code, setCode] = useState('')
  const [joinError, setJoinError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const notice = (location.state as { notice?: string } | null)?.notice

  const start = async () => {
    if (!user && !(await requestLogin('DJs need an account so the room knows who runs it. Listeners never do.'))) return
    setBusy(true)
    try {
      const room = await api.createRoom()
      navigate(`/${room.pretty_id}`)
    } catch (err) {
      setJoinError(err instanceof ApiError ? err.message : 'Could not start a room.')
    } finally {
      setBusy(false)
    }
  }

  const join = async (e: FormEvent) => {
    e.preventDefault()
    setJoinError(null)
    const letters = code.replace(/[^a-z]/gi, '')
    if (letters.length !== 12) {
      setJoinError('Room codes are 12 letters, like ABCD-EFGH-IJKL.')
      return
    }
    try {
      const room = await api.roomInfo(letters)
      navigate(`/${room.pretty_id}`)
    } catch (err) {
      setJoinError(err instanceof ApiError ? err.message : 'Could not find that room.')
    }
  }

  return (
    <main className="landing">
      <div className="landing-record">
        <Vinyl spinning blankLabel="" />
      </div>
      <div className="landing-inner">
        <header className="landing-top">
          <Link to="/" className="brandmark">
            <span className="brandmark-disc" aria-hidden="true" />
            Crowdsource DJ
          </Link>
          {user ? (
            <span>
              Hi, <strong>{user.username}</strong>{' '}
              <button className="btn-ghost" onClick={logout}>
                Log out
              </button>
            </span>
          ) : (
            <button className="btn btn-small" onClick={() => requestLogin()}>
              Log in
            </button>
          )}
        </header>

        <section className="landing-hero">
          <h1 className="poster-title" aria-label="Crowdsource DJ">
            <span aria-hidden="true">Crowd</span>
            <span aria-hidden="true">source</span>
            <span aria-hidden="true" className="word-dj">
              DJ
            </span>
            <span className="ink ink-pink" aria-hidden="true">
              <span>Crowd</span>
              <span>source</span>
              <span className="word-dj">DJ</span>
            </span>
            <span className="ink ink-blue" aria-hidden="true">
              <span>Crowd</span>
              <span>source</span>
              <span className="word-dj">DJ</span>
            </span>
          </h1>
          <p className="lede">because music was always meant to be a communal experience</p>

          {notice && <p className="form-error">{notice}</p>}

          <div className="landing-actions">
            <div className="ticket ticket-start">
              <h2>Host a room</h2>
              <p>You'll be the DJ. Share the code with friends.</p>
              <button className="btn btn-pink" onClick={start} disabled={busy}>
                {busy ? 'Setting up…' : 'Start a room'}
              </button>
            </div>
            <form className="ticket ticket-join" onSubmit={join}>
              <h2>Join a room</h2>
              <p>Got a code from a friend? No account needed.</p>
              <div className="join-form">
                <label htmlFor="code" className="sr-only">
                  Room code
                </label>
                <input
                  id="code"
                  className="code-input"
                  placeholder="ABCD-EFGH-IJKL"
                  value={code}
                  onChange={(e) => setCode(formatRoomId(e.target.value))}
                  autoComplete="off"
                  spellCheck={false}
                />
                <button className="btn btn-yellow" type="submit">
                  Join
                </button>
              </div>
              {joinError && <p className="form-error" role="alert">{joinError}</p>}
            </form>
          </div>
        </section>

      </div>
    </main>
  )
}
