import { useCallback, useEffect, useRef, useState } from 'react'
import { formatTime } from '../lib/session'
import type { RoomState } from '../lib/types'
import { loadYouTube, PLAYER_STATE, type YTPlayer } from '../lib/youtube'
import { MuteIcon, NextIcon, PauseIcon, PlayIcon, PrevIcon, Tonearm, VolumeIcon } from './icons'
import Vinyl, { isLetterboxed } from './Record'

interface Props {
  state: RoomState
  canControl: boolean
  send: (msg: Record<string, unknown>) => boolean
  serverNow: () => number
  showVideo: boolean
}

/** Where the room says the song should be right now, in seconds. */
function expectedPosition(state: RoomState, now: number) {
  const pb = state.playback
  const track = state.queue[state.current]
  let pos = pb.position + (pb.playing ? now - pb.updated_at : 0)
  if (track?.duration) pos = Math.min(pos, track.duration)
  return Math.max(0, pos)
}

const DRIFT_PLAYING = 0.3
const DRIFT_PAUSED = 0.75
const SEEK_COOLDOWN_MS = 3000
// A seek or load takes a moment to start playing. We learn how long and aim that far ahead.
const MAX_LEAD = 2

export default function Stage({ state, canControl, send, serverNow, showVideo }: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const player = useRef<YTPlayer | null>(null)
  const ready = useRef(false)
  const latest = useRef(state)
  latest.current = state
  const loadedUid = useRef<string | null>(null)
  const cuedAt = useRef<number | null>(null)
  const lastSeek = useRef(0)
  const lead = useRef(0.25)
  const measuring = useRef(false)
  const reportedEnd = useRef<string | null>(null)

  const [tunedIn, setTunedIn] = useState(false)
  const [volume, setVolume] = useState(80)
  const [muted, setMuted] = useState(false)
  const [scrub, setScrub] = useState<number | null>(null)
  const [, force] = useState(0)

  const track = state.current >= 0 ? state.queue[state.current] : undefined
  const live = !!track && !state.playback.finished
  const spinning = live && state.playback.playing

  // Bring the local player in line with the room. Runs on every state change and on a timer.
  const sync = useCallback(() => {
    const p = player.current
    const s = latest.current
    if (!p || !ready.current) return
    const t = s.current >= 0 ? s.queue[s.current] : undefined
    const ps = p.getPlayerState()
    if (!t || s.playback.finished) {
      if (ps === PLAYER_STATE.PLAYING || ps === PLAYER_STATE.BUFFERING) p.pauseVideo()
      return
    }
    const expected = expectedPosition(s, serverNow())
    const playing = s.playback.playing

    if (loadedUid.current !== t.uid) {
      loadedUid.current = t.uid
      reportedEnd.current = null
      lastSeek.current = performance.now()
      if (playing) {
        cuedAt.current = null
        measuring.current = true
        p.loadVideoById({ videoId: t.video_id, startSeconds: expected + lead.current })
      } else {
        cuedAt.current = expected
        p.cueVideoById({ videoId: t.video_id, startSeconds: expected })
      }
      return
    }

    const nearEnd = t.duration > 0 && expected >= t.duration - 0.8
    if (playing) {
      if (ps === PLAYER_STATE.ENDED || nearEnd) return
      if (ps !== PLAYER_STATE.PLAYING && ps !== PLAYER_STATE.BUFFERING) {
        // Resuming takes a moment too: start a little ahead so we land on the room clock.
        if (ps === PLAYER_STATE.PAUSED) {
          lastSeek.current = performance.now()
          measuring.current = true
          p.seekTo(expected + lead.current, true)
        }
        p.playVideo()
      }
    } else if (ps === PLAYER_STATE.PLAYING || ps === PLAYER_STATE.BUFFERING) {
      p.pauseVideo()
    }

    // A cued video that never started reports 0; re-cue at the right spot instead of seeking.
    if (!playing && ps === PLAYER_STATE.CUED) {
      if (cuedAt.current === null || Math.abs(cuedAt.current - expected) > DRIFT_PAUSED) {
        cuedAt.current = expected
        p.cueVideoById({ videoId: t.video_id, startSeconds: expected })
      }
      return
    }

    const drift = p.getCurrentTime() - expected
    const sinceSeek = performance.now() - lastSeek.current
    if (playing && measuring.current && ps === PLAYER_STATE.PLAYING && sinceSeek > 1500) {
      // Settled after a load/seek: whatever drift is left is our startup latency.
      measuring.current = false
      lead.current = Math.min(MAX_LEAD, Math.max(0, lead.current - drift))
    }
    if (Math.abs(drift) > (playing ? DRIFT_PLAYING : DRIFT_PAUSED) && sinceSeek > SEEK_COOLDOWN_MS) {
      lastSeek.current = performance.now()
      measuring.current = playing
      p.seekTo(playing ? expected + lead.current : expected, true)
    }
  }, [serverNow])

  // Create the YouTube player once the listener has tapped in (browsers need a click before audio).
  useEffect(() => {
    if (!tunedIn || !hostRef.current) return
    let cancelled = false
    const mount = document.createElement('div')
    hostRef.current.appendChild(mount)
    loadYouTube().then((YT) => {
      if (cancelled) return
      player.current = new YT.Player(mount, {
        width: '100%',
        height: '100%',
        playerVars: {
          autoplay: 1,
          controls: 0,
          disablekb: 1,
          playsinline: 1,
          rel: 0,
          fs: 0,
          iv_load_policy: 3,
          origin: location.origin,
        },
        events: {
          onReady: (e) => {
            ready.current = true
            send({ type: 'tuned' })
            if (import.meta.env.DEV) {
              // Lets browser tests compare the real player against the room clock.
              ;(window as unknown as { __cdj: unknown }).__cdj = {
                playerTime: () => e.target.getCurrentTime(),
                playerState: () => e.target.getPlayerState(),
                videoId: () => e.target.getVideoData().video_id,
                expected: () => expectedPosition(latest.current, serverNow()),
                lead: () => lead.current,
              }
            }
            e.target.setVolume(volume)
            sync()
          },
          onStateChange: (e) => {
            const s = latest.current
            const t = s.queue[s.current]
            if (e.data === PLAYER_STATE.ENDED && t && reportedEnd.current !== t.uid) {
              reportedEnd.current = t.uid
              send({ type: 'ended', uid: t.uid })
            }
          },
          onError: (e) => {
            const s = latest.current
            const t = s.queue[s.current]
            // 100: removed/private, 101/150: owner blocked embedding.
            if (t && [100, 101, 150].includes(e.data)) send({ type: 'player_error', uid: t.uid, code: e.data })
          },
        },
      })
    })
    return () => {
      cancelled = true
      ready.current = false
      loadedUid.current = null
      player.current?.destroy()
      player.current = null
      mount.remove()
    }
    // volume is applied separately; the player is created once per tune-in.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tunedIn, send, sync])

  useEffect(() => {
    sync()
  }, [state, sync])

  useEffect(() => {
    const id = window.setInterval(() => {
      sync()
      force((n) => n + 1) // repaint the progress bar
    }, 500)
    return () => clearInterval(id)
  }, [sync])

  useEffect(() => {
    const p = player.current
    if (!p || !ready.current) return
    p.setVolume(volume)
    if (muted) p.mute()
    else p.unMute()
  }, [volume, muted])

  const position = live ? expectedPosition(state, serverNow()) : track?.duration ?? 0
  const shown = scrub ?? position
  const duration = track?.duration ?? 0
  const pct = duration ? Math.min(100, (shown / duration) * 100) : 0

  const commitScrub = () => {
    if (scrub !== null) send({ type: 'seek', position: scrub })
    setScrub(null)
  }

  return (
    <section className="stage" aria-label="Now playing">
      <div className={`deck ${track ? '' : 'is-empty'}`}>
        <div className="sleeve">
          {track ? (
            <img referrerPolicy="no-referrer" src={track.thumb} alt="" className={isLetterboxed(track.thumb) ? 'is-letterboxed' : ''} />
          ) : (
            <div className="sleeve-empty">Queue a song to start the party</div>
          )}
        </div>
        <Vinyl art={track?.thumb} spinning={spinning} />
        <Tonearm className={`tonearm ${spinning ? 'is-down' : ''}`} />
        {!tunedIn && (
          <button className="tap-in" onClick={() => setTunedIn(true)}>
            <span>Tap to listen</span>
          </button>
        )}
      </div>

      <div className="now">
        <div className="now-kicker">
          <span className={`live-dot ${spinning ? '' : 'is-paused'}`} />
          {!track
            ? 'Nothing playing yet'
            : state.playback.finished
              ? 'Queue finished'
              : spinning
                ? `Playing for ${state.members.length} ${state.members.length === 1 ? 'person' : 'people'}`
                : 'Paused'}
        </div>
        <h1 className="now-title">{track ? track.title : 'Silence, for now'}</h1>
        {track ? (
          <>
            <p className="now-artist">{track.artist || 'Unknown artist'}</p>
            <p className="now-meta">Picked by {track.added_by}</p>
          </>
        ) : (
          <p className="now-artist">Search for a song or paste a YouTube link below.</p>
        )}

        <div className="progress">
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${pct}%` }} />
            {canControl && track && duration > 0 && (
              <input
                type="range"
                min={0}
                max={duration}
                step={1}
                value={Math.floor(shown)}
                aria-label="Seek"
                onChange={(e) => setScrub(Number(e.target.value))}
                onMouseUp={commitScrub}
                onTouchEnd={commitScrub}
                onKeyUp={commitScrub}
              />
            )}
          </div>
          <div className="progress-times">
            <span>{formatTime(shown)}</span>
            <span>{formatTime(duration)}</span>
          </div>
        </div>

        <div className="controls">
          {canControl ? (
            <>
              <button className="ctrl" onClick={() => send({ type: 'prev' })} aria-label="Previous song" disabled={!track}>
                <PrevIcon />
              </button>
              <button
                className="ctrl ctrl-main"
                onClick={() => send({ type: spinning ? 'pause' : 'play' })}
                aria-label={spinning ? 'Pause for everyone' : 'Play for everyone'}
                disabled={!track && state.queue.length === 0}
              >
                {spinning ? <PauseIcon /> : <PlayIcon />}
              </button>
              <button className="ctrl" onClick={() => send({ type: 'next' })} aria-label="Next song" disabled={!track}>
                <NextIcon />
              </button>
            </>
          ) : (
            <p className="controls-note">
              The DJ crew runs the decks. Want this song gone? Type <strong>/voteskip</strong> in chat.
            </p>
          )}
          <label className="volume">
            <button className="icon-btn" onClick={() => setMuted((m) => !m)} aria-label={muted ? 'Unmute' : 'Mute'}>
              {muted || volume === 0 ? <MuteIcon /> : <VolumeIcon />}
            </button>
            <span className="sr-only">Your volume</span>
            <input type="range" min={0} max={100} value={volume} onChange={(e) => setVolume(Number(e.target.value))} />
          </label>
        </div>
      </div>

      <div className={`video-box ${showVideo && tunedIn ? '' : 'is-hidden'}`} ref={hostRef} />
    </section>
  )
}
