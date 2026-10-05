import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from 'react'
import { colorFor } from '../lib/session'
import { ROLE_LABEL, ROLE_RANK, type ChatMessage, type Poll, type Role, type RoomState, type You } from '../lib/types'

interface Props {
  chat: ChatMessage[]
  state: RoomState
  you: You
  myRole: Role
  send: (msg: Record<string, unknown>) => boolean
  serverNow: () => number
}

export default function Chat({ chat, state, you, myRole, send, serverNow }: Props) {
  const [text, setText] = useState('')
  const log = useRef<HTMLDivElement>(null)
  const stick = useRef(true)
  const canModerate = ROLE_RANK[myRole] >= ROLE_RANK.mod

  useLayoutEffect(() => {
    const el = log.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  }, [chat, state.polls])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const t = text.trim()
    if (t && send({ type: 'chat', text: t })) setText('')
  }

  return (
    <section className="panel chat" aria-label="Chat">
      <header className="chat-head">
        <h2>Chat</h2>
        <span>{state.members.length} here</span>
      </header>
      <div
        className="chat-log"
        ref={log}
        onScroll={(e) => {
          const el = e.currentTarget
          stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60
        }}
      >
        {chat.length === 0 && <div className="msg-system">Say hi. Type /voteskip if a song isn't landing.</div>}
        {chat.map((m) => {
          if (m.kind === 'poll' && m.poll_id) {
            const poll = state.polls[m.poll_id]
            return poll ? <PollCard key={m.id} poll={poll} you={you} send={send} serverNow={serverNow} /> : null
          }
          if (m.kind === 'system') {
            const loud = m.event === 'dj_change' || m.event?.startsWith('poll_')
            return (
              <div key={m.id} className={`msg-system ${loud ? 'is-event' : ''}`}>
                {m.text}
              </div>
            )
          }
          return (
            <div key={m.id} className="msg">
              <span className="avatar" style={{ background: colorFor(m.key) }} aria-hidden="true">
                {(m.name ?? '?').slice(0, 1).toUpperCase()}
              </span>
              <div>
                <div className="msg-name" style={{ color: colorFor(m.key) }}>
                  {m.name}
                  {m.role && m.role !== 'listener' && <span className={`badge badge-${m.role}`}>{ROLE_LABEL[m.role]}</span>}
                </div>
                <div className="msg-text">{m.text}</div>
              </div>
              {canModerate && (
                <button className="icon-btn msg-del" onClick={() => send({ type: 'delete_message', id: m.id })} aria-label="Delete message">
                  ✕
                </button>
              )}
            </div>
          )
        })}
      </div>
      <form className="chat-form" onSubmit={submit}>
        <label className="sr-only" htmlFor="chat-input">
          Message
        </label>
        <input
          id="chat-input"
          className="chat-input"
          placeholder={`Say something, ${you.name.split(' ')[0]}`}
          value={text}
          maxLength={500}
          onChange={(e) => setText(e.target.value)}
          autoComplete="off"
        />
        <button className="btn btn-pink btn-small" type="submit" disabled={!text.trim()}>
          Send
        </button>
      </form>
      <div className="chat-hint">
        Not feeling this one? Type <code>/voteskip</code>
      </div>
    </section>
  )
}

function PollCard({ poll, you, send, serverNow }: { poll: Poll; you: You; send: Props['send']; serverNow: () => number }) {
  const [, tick] = useState(0)
  const open = poll.status === 'open'
  useEffect(() => {
    if (!open) return
    const id = setInterval(() => tick((n) => n + 1), 1000)
    return () => clearInterval(id)
  }, [open])

  const myVote = poll.votes[you.key]
  const left = Math.max(0, Math.ceil(poll.ends_at - serverNow()))
  const eligible = Math.max(poll.eligible, 1)
  const yesPct = Math.min(100, (poll.yes / eligible) * 100)

  return (
    <div className={`poll-card ${open ? '' : 'is-closed'}`} aria-live="polite">
      <p className="poll-q">Skip “{poll.track_title}”?</p>
      <p className="poll-sub">
        {poll.started_by} asked. Skips when more than {poll.threshold}% say yes
        {open ? ` · ${left}s left` : ''}.
      </p>
      <div className="poll-meter" role="img" aria-label={`${poll.yes} of ${poll.eligible} voted to skip`}>
        <div className="poll-meter-yes" style={{ width: `${yesPct}%` }} />
        <div className="poll-meter-line" style={{ left: `${poll.threshold}%` }} />
      </div>
      <div className="poll-counts">
        <span>
          {poll.yes} skip · {poll.no} keep
        </span>
        <span>
          {open ? `${poll.needed} of ${poll.eligible} needed` : ''}
        </span>
      </div>
      {open ? (
        myVote === undefined ? (
          <div className="poll-actions">
            <button className="btn btn-small btn-pink" onClick={() => send({ type: 'vote', poll_id: poll.id, yes: true })}>
              Skip it
            </button>
            <button className="btn btn-small" onClick={() => send({ type: 'vote', poll_id: poll.id, yes: false })}>
              Keep it
            </button>
          </div>
        ) : (
          <div className="poll-result">You voted {myVote ? 'skip' : 'keep'}.</div>
        )
      ) : (
        <div className="poll-result">
          {poll.status === 'passed' ? 'Skipped. ' : poll.status === 'failed' ? 'Kept. ' : 'Closed. '}
          {poll.reason}
        </div>
      )}
    </div>
  )
}
