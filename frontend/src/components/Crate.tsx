import { useEffect, useRef, useState } from 'react'
import { colorFor, formatTime } from '../lib/session'
import { ROLE_LABEL, ROLE_RANK, type Member, type QueueEntry, type Role, type RoomState, type Track, type You } from '../lib/types'
import AddSong from './AddSong'

interface Props {
  state: RoomState
  you: You
  myRole: Role
  send: (msg: Record<string, unknown>) => boolean
  onNotice: (text: string) => void
  requestLogin: (reason: string) => void
}

type Tab = 'queue' | 'suggestions' | 'crowd'

export default function Crate({ state, you, myRole, send, onNotice, requestLogin }: Props) {
  const [tab, setTab] = useState<Tab>('queue')
  const [showPlayed, setShowPlayed] = useState(false)
  const rank = ROLE_RANK[myRole]
  const isCrew = rank >= ROLE_RANK.codj

  const played = state.queue.slice(0, Math.max(0, state.current))
  const current = state.current >= 0 ? state.queue[state.current] : undefined
  const upcoming = state.queue.slice(state.current + 1)

  const tabs: { id: Tab; label: string; count: number }[] = [
    { id: 'queue', label: 'Up next', count: upcoming.length },
    { id: 'suggestions', label: 'Suggestions', count: state.suggestions.length },
    { id: 'crowd', label: 'Crowd', count: state.members.length },
  ]

  const canRemove = (t: QueueEntry) => t.added_by_key === you.key || rank >= ROLE_RANK.mod

  const entryRow = (t: QueueEntry, kind: 'played' | 'current' | 'upcoming', i = 0) => (
    <li key={t.uid} className={`track ${kind === 'current' ? 'is-current' : ''} ${kind === 'played' ? 'is-played' : ''}`}>
      <img referrerPolicy="no-referrer" className="track-art" src={t.thumb} alt="" loading="lazy" />
      <div className="track-text">
        <div className="track-title">{t.title}</div>
        <div className="track-sub">
          {kind === 'current' ? 'Playing now · ' : ''}
          {t.artist} · added by {t.added_by}
        </div>
      </div>
      <div className="track-actions">
        <span className="track-duration">{formatTime(t.duration)}</span>
        {isCrew && kind !== 'current' && (
          <button className="icon-btn" onClick={() => send({ type: 'jump', uid: t.uid })} aria-label={`Play ${t.title} now`} title="Play now">
            ▶
          </button>
        )}
        {isCrew && kind === 'upcoming' && (
          <>
            <button
              className="icon-btn"
              disabled={i === 0}
              onClick={() => send({ type: 'move', uid: t.uid, to: state.current + i })}
              aria-label={`Move ${t.title} up`}
              title="Move up"
            >
              ↑
            </button>
            <button
              className="icon-btn"
              disabled={i === upcoming.length - 1}
              onClick={() => send({ type: 'move', uid: t.uid, to: state.current + i + 2 })}
              aria-label={`Move ${t.title} down`}
              title="Move down"
            >
              ↓
            </button>
          </>
        )}
        {kind !== 'played' && canRemove(t) && (
          <button className="icon-btn" onClick={() => send({ type: 'remove', uid: t.uid })} aria-label={`Remove ${t.title}`} title="Remove">
            ✕
          </button>
        )}
      </div>
    </li>
  )

  return (
    <section className="panel crate" aria-label="Queue">
      <AddSong send={send} onAdded={(title) => onNotice(`Queued “${title}”`)} />

      <div className="tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t.id} role="tab" className="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>
            {t.label}
            <span className="tab-count">{t.count}</span>
          </button>
        ))}
      </div>

      {tab === 'queue' && (
        <div role="tabpanel">
          {current || upcoming.length ? (
            <ul className="track-list">
              {current && entryRow(current, 'current')}
              {upcoming.map((t, i) => entryRow(t, 'upcoming', i))}
            </ul>
          ) : (
            <div className="empty">
              <strong>The queue is empty</strong>
              Everyone can add songs. Search above to get things going.
            </div>
          )}
          {current && upcoming.length === 0 && state.suggestions.length > 0 && (
            <p className="tab-intro" style={{ marginTop: 12 }}>
              After this, “{state.suggestions[0].title}” moves up from suggestions.
            </p>
          )}
          {played.length > 0 && (
            <>
              <button className="btn-ghost history-toggle" onClick={() => setShowPlayed((v) => !v)}>
                {showPlayed ? 'Hide' : 'Show'} {played.length} played {played.length === 1 ? 'song' : 'songs'}
              </button>
              {showPlayed && <ul className="track-list">{[...played].reverse().map((t) => entryRow(t, 'played'))}</ul>}
            </>
          )}
        </div>
      )}

      {tab === 'suggestions' && (
        <div role="tabpanel">
          <div className="tab-intro">
            <span>When the queue runs out, the top suggestion plays next. Based on what the room has queued.</span>
            {isCrew && (
              <button
                className="btn btn-small btn-yellow"
                onClick={() => send({ type: 'refresh_suggestions' })}
                disabled={state.suggestions_loading || state.queue.length === 0}
              >
                {state.suggestions_loading ? 'Refreshing…' : 'Refresh'}
              </button>
            )}
          </div>
          {state.suggestions.length ? (
            <ul className="track-list">
              {state.suggestions.map((t) => (
                <SuggestionRow key={t.video_id} t={t} isCrew={isCrew} send={send} onNotice={onNotice} />
              ))}
            </ul>
          ) : (
            <div className="empty">
              <strong>{state.suggestions_loading ? 'Finding songs…' : 'No suggestions yet'}</strong>
              {state.suggestions_loading ? 'Asking YouTube Music for songs like yours.' : 'Queue a song and suggestions will appear here.'}
            </div>
          )}
        </div>
      )}

      {tab === 'crowd' && (
        <div role="tabpanel">
          <ul className="crowd-list">
            {state.members.map((m) => (
              <Person key={m.key} m={m} you={you} myRole={myRole} send={send} requestLogin={requestLogin} />
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function SuggestionRow({ t, isCrew, send, onNotice }: { t: Track; isCrew: boolean; send: Props['send']; onNotice: Props['onNotice'] }) {
  return (
    <li className="track">
      <img referrerPolicy="no-referrer" className="track-art" src={t.thumb} alt="" loading="lazy" />
      <div className="track-text">
        <div className="track-title">{t.title}</div>
        <div className="track-sub">{t.artist}</div>
      </div>
      <div className="track-actions">
        <span className="track-duration">{formatTime(t.duration)}</span>
        {isCrew && (
          <button className="icon-btn" onClick={() => send({ type: 'remove_suggestion', video_id: t.video_id })} aria-label={`Drop ${t.title}`} title="Drop">
            ✕
          </button>
        )}
        <button
          className="add-btn"
          onClick={() => send({ type: 'add', video_id: t.video_id, from_suggestions: true }) && onNotice(`Queued “${t.title}”`)}
          aria-label={`Add ${t.title} to the queue`}
        >
          +
        </button>
      </div>
    </li>
  )
}

function Person({
  m,
  you,
  myRole,
  send,
  requestLogin,
}: {
  m: Member
  you: You
  myRole: Role
  send: Props['send']
  requestLogin: Props['requestLogin']
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const isYou = m.key === you.key
  const myRank = ROLE_RANK[myRole]
  const canAssign = myRank >= ROLE_RANK.codj && m.role !== 'dj' && !isYou
  const canKick = myRank >= ROLE_RANK.mod && ROLE_RANK[m.role] < myRank && !isYou
  const canHandOver = myRole === 'dj' && !isYou

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false)
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  const act = (msg: Record<string, unknown>) => {
    send(msg)
    setOpen(false)
  }

  return (
    <li className="person">
      <span className="avatar" style={{ background: colorFor(m.key) }} aria-hidden="true">
        {m.name.slice(0, 1).toUpperCase()}
      </span>
      <span className="person-name">
        {m.name}
        <small>
          {isYou ? 'you' : ''}
          {isYou && !m.is_user ? ', ' : ''}
          {!m.is_user ? 'guest' : ''}
        </small>
      </span>
      <span className={`badge badge-${m.role}`}>{ROLE_LABEL[m.role]}</span>
      {isYou && !m.is_user && (
        <button className="btn btn-small" onClick={() => requestLogin('Log in to be eligible for co-DJ or moderator.')}>
          Log in
        </button>
      )}
      {(canAssign || canKick || canHandOver) && (
        <div className="person-menu" ref={ref}>
          <button className="icon-btn" onClick={() => setOpen((o) => !o)} aria-label={`Options for ${m.name}`} aria-expanded={open}>
            ⋯
          </button>
          {open && (
            <div className="menu" role="menu">
              {canAssign && !m.is_user && <div className="menu-note">Guests need to log in before they can be co-DJ or moderator.</div>}
              {canAssign && (
                <>
                  <button disabled={!m.is_user || m.role === 'codj'} onClick={() => act({ type: 'set_role', key: m.key, role: 'codj' })}>
                    Make co-DJ
                  </button>
                  <button disabled={!m.is_user || m.role === 'mod'} onClick={() => act({ type: 'set_role', key: m.key, role: 'mod' })}>
                    Make moderator
                  </button>
                  <button disabled={m.role === 'listener'} onClick={() => act({ type: 'set_role', key: m.key, role: 'listener' })}>
                    Make listener
                  </button>
                </>
              )}
              {canHandOver && (
                <button disabled={!m.is_user} onClick={() => act({ type: 'transfer_dj', key: m.key })}>
                  Hand over the DJ booth
                </button>
              )}
              {canKick && (
                <button className="menu-danger" onClick={() => act({ type: 'kick', key: m.key })}>
                  Remove from room
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </li>
  )
}
