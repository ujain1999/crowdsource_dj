import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import Chat from '../components/Chat'
import Crate from '../components/Crate'
import Modal from '../components/Modal'
import SettingsModal from '../components/SettingsModal'
import Stage from '../components/Stage'
import { useAuth } from '../lib/auth'
import { colorFor, formatRoomId, setGuestName } from '../lib/session'
import { useToast } from '../lib/toast'
import { ROLE_LABEL, ROLE_RANK, type Role } from '../lib/types'
import { useRoom } from '../lib/useRoom'

export default function RoomPage() {
  const { roomId = '' } = useParams()
  const letters = roomId.replace(/[^a-z]/gi, '').toUpperCase()
  const pretty = formatRoomId(letters)
  if (letters.length !== 12) return <NotFound />
  // Canonical, readable URL: /ABCD-EFGH-IJKL
  if (roomId !== pretty) return <Navigate to={`/${pretty}`} replace />
  return <LiveRoom key={letters} roomId={letters} pretty={pretty} />
}

function LiveRoom({ roomId, pretty }: { roomId: string; pretty: string }) {
  const navigate = useNavigate()
  const toast = useToast()
  const { user, token, requestLogin, logout } = useAuth()
  const { state, chat, you, status, endedBy, send, serverNow } = useRoom(roomId, { token, onNotice: toast })
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [showVideo, setShowVideo] = useState(false)

  const myRole: Role = useMemo(
    () => state?.members.find((m) => m.key === you?.key)?.role ?? 'listener',
    [state, you],
  )

  useEffect(() => {
    if (state) document.title = `${state.name} · Crowdsource DJ`
    return () => {
      document.title = 'Crowdsource DJ'
    }
  }, [state?.name]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (status === 'deleted') navigate('/', { state: { notice: `${endedBy ?? 'The DJ'} deleted that room.` } })
    if (status === 'kicked') navigate('/', { state: { notice: `${endedBy ?? 'A moderator'} removed you from that room.` } })
    if (status === 'left') navigate('/')
  }, [status, endedBy, navigate])

  if (status === 'not_found') return <NotFound />
  if (!state || !you) {
    return (
      <div className="notice-page">
        <div>
          <h1>Dropping the needle…</h1>
          <p>Joining room {pretty}</p>
        </div>
      </div>
    )
  }

  const isCrew = ROLE_RANK[myRole] >= ROLE_RANK.codj
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(location.href)
      toast('Room link copied. Send it to your friends.')
    } catch {
      toast(`Room code: ${pretty}`)
    }
  }

  const leave = () => {
    if (!send({ type: 'leave' })) navigate('/')
  }

  const doLogout = async () => {
    if (myRole === 'dj' && state.members.length > 1) toast('You logged out, so someone else takes the booth.')
    await logout()
  }

  return (
    <div className="room">
      {status === 'reconnecting' && <div className="reconnecting">Reconnecting…</div>}
      <header className="room-bar">
        <Link to="/" className="brandmark" aria-label="Crowdsource DJ home">
          <span className="brandmark-disc" aria-hidden="true" />
          Crowdsource DJ
        </Link>
        <div className="room-code">
          <span className="room-code-id" aria-label={`Room code ${pretty}`}>
            {pretty}
          </span>
          <button className="btn btn-small" onClick={copyLink} aria-label="Copy room link">
            <span className="copy-long">Copy link</span>
            <span className="copy-short">Copy</span>
          </button>
        </div>
        <span className="room-bar-spacer" />
        <div className="me-chip">
          <span className="avatar" style={{ background: colorFor(you.key) }} aria-hidden="true">
            {you.name.slice(0, 1).toUpperCase()}
          </span>
          <span className="me-name">
            <strong>{you.name}</strong>
            {myRole !== 'listener' && <> · {ROLE_LABEL[myRole]}</>}
          </span>
          {user ? (
            <button className="btn-ghost" onClick={doLogout}>
              Log out
            </button>
          ) : (
            <>
              <button className="btn-ghost" onClick={() => setRenaming(true)}>
                Rename
              </button>
              <button className="btn btn-small btn-yellow" onClick={() => requestLogin()}>
                Log in
              </button>
            </>
          )}
        </div>
        <button
          className="icon-btn bar-icon"
          onClick={() => setShowVideo((v) => !v)}
          aria-pressed={showVideo}
          aria-label={showVideo ? 'Hide video' : 'Show video'}
          title={showVideo ? 'Hide video' : 'Show video'}
        >
          📺
        </button>
        {isCrew && (
          <button className="icon-btn bar-icon" onClick={() => setSettingsOpen(true)} aria-label="Room settings" title="Room settings">
            ⚙
          </button>
        )}
        <button className="btn btn-small leave-btn" onClick={leave}>
          Leave
        </button>
      </header>

      <div className="room-grid">
        <main className="room-main">
          <Stage state={state} canControl={isCrew} send={send} serverNow={serverNow} showVideo={showVideo} />
          <Crate
            state={state}
            you={you}
            myRole={myRole}
            send={send}
            onNotice={toast}
            requestLogin={(reason) => requestLogin(reason)}
          />
        </main>
        <aside className="room-side">
          <Chat chat={chat} state={state} you={you} myRole={myRole} send={send} serverNow={serverNow} />
        </aside>
      </div>

      {settingsOpen && <SettingsModal state={state} myRole={myRole} send={send} onClose={() => setSettingsOpen(false)} />}
      {renaming && (
        <RenameModal
          current={you.name}
          onClose={() => setRenaming(false)}
          onSave={(name) => {
            if (send({ type: 'rename', name })) {
              setGuestName(name)
              setRenaming(false)
            }
          }}
        />
      )}
    </div>
  )
}

function RenameModal({ current, onClose, onSave }: { current: string; onClose: () => void; onSave: (n: string) => void }) {
  const [name, setName] = useState(current)
  return (
    <Modal title="Change your name" onClose={onClose}>
      <p className="modal-reason">This is how you show up in chat and the crowd list.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (name.trim()) onSave(name.trim())
        }}
      >
        <label className="field">
          Name
          <input type="text" autoFocus maxLength={24} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <div className="modal-actions">
          <button type="submit" className="btn btn-yellow">
            Save name
          </button>
        </div>
      </form>
    </Modal>
  )
}

function NotFound() {
  return (
    <div className="notice-page">
      <div>
        <h1>This room is silent</h1>
        <p>There's no room with that code. It may have been deleted, or a letter got mixed up.</p>
        <Link to="/" className="btn btn-pink">
          Back to the lobby
        </Link>
      </div>
    </div>
  )
}
