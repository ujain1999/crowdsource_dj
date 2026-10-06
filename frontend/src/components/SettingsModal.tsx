import { useState, type FormEvent } from 'react'
import { useAuth } from '../lib/auth'
import type { Role, RoomState } from '../lib/types'
import Modal from './Modal'

interface Props {
  state: RoomState
  myRole: Role
  send: (msg: Record<string, unknown>) => boolean
  onClose: () => void
}

export default function SettingsModal({ state, myRole, send, onClose }: Props) {
  const [name, setName] = useState(state.name)
  const [threshold, setThreshold] = useState(state.settings.skip_threshold)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const { user } = useAuth()

  const save = (e: FormEvent) => {
    e.preventDefault()
    if (send({ type: 'settings', name, skip_threshold: threshold })) onClose()
  }

  return (
    <Modal title="Room settings" onClose={onClose}>
      <p className="modal-reason">Changes apply to everyone in the room right away.</p>
      <form onSubmit={save}>
        <label className="field">
          Room name
          <input type="text" value={name} maxLength={40} onChange={(e) => setName(e.target.value)} required />
        </label>
        <div className="field">
          <label htmlFor="threshold">Votes needed to skip</label>
          <div className="threshold">
            <input
              id="threshold"
              type="range"
              min={1}
              max={99}
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
            />
            <output htmlFor="threshold">{threshold}%</output>
          </div>
          <span className="field-hint">
            A /voteskip passes when more than {threshold}% of the people in the room vote yes.
          </span>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-yellow">
            Save settings
          </button>
        </div>
      </form>

      {myRole === 'dj' && (
        <div className="danger-zone">
          <p>Deleting the room ends the party for everyone and removes its queue and chat.</p>
          {!user ? (
            <p className="field-hint">Log in to delete the room.</p>
          ) : confirmDelete ? (
            <div className="modal-actions" style={{ justifyContent: 'flex-start' }}>
              <button className="btn btn-danger" onClick={() => send({ type: 'delete_room' })}>
                Yes, delete this room
              </button>
              <button className="btn" onClick={() => setConfirmDelete(false)}>
                Keep it
              </button>
            </div>
          ) : (
            <button className="btn btn-small" onClick={() => setConfirmDelete(true)}>
              Delete room
            </button>
          )}
        </div>
      )}
    </Modal>
  )
}
