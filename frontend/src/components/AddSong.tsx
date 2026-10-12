import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api } from '../lib/api'
import { formatTime } from '../lib/session'
import type { Track } from '../lib/types'
import { CheckIcon, PlusIcon } from './icons'

interface Props {
  send: (msg: Record<string, unknown>) => boolean
  onAdded: (title: string) => void
}

// YouTube, plus the services the server can read songs from (backend/app/links.py). The
// search API also says when a query is a link, which covers anything missing here.
const URL_RE =
  /(^|[/.])(youtube\.com|youtu\.be|youtube-nocookie\.com|open\.spotify\.com|play\.spotify\.com|spotify\.link|spotify\.app\.link|spoti\.fi|music\.apple\.com|itunes\.apple\.com|music\.amazon\.[a-z.]+|tidal\.com|qobuz\.com|jiosaavn\.com|saavn\.com|gaana\.com|wynk\.in|genius\.com|azlyrics\.com|last\.fm|lastfm\.[a-z.]+|musixmatch\.com)\/|^spotify:(track|album|playlist):/i

export default function AddSong({ send, onAdded }: Props) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<Track[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [added, setAdded] = useState<Set<string>>(new Set())
  const [serverUrl, setServerUrl] = useState('') // a query the server recognised as a link
  const box = useRef<HTMLDivElement>(null)
  const isUrl = URL_RE.test(q.trim()) || (serverUrl !== '' && serverUrl === q.trim())

  useEffect(() => {
    const query = q.trim()
    if (!query || isUrl) {
      setResults(null)
      setLoading(false)
      return
    }
    setLoading(true)
    setResults(null) // never leave results for an older query clickable
    let stale = false
    const id = setTimeout(() => {
      api
        .search(query)
        .then((r) => {
          if (stale) return
          if (r.is_url) setServerUrl(query)
          setResults(r.results)
        })
        .catch(() => !stale && setResults([]))
        .finally(() => !stale && setLoading(false))
    }, 350)
    return () => {
      stale = true
      clearTimeout(id)
    }
  }, [q, isUrl])

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (isUrl) {
      if (send({ type: 'add_url', url: q.trim() })) {
        setQ('')
        setOpen(false)
      }
    } else if (results?.[0]) {
      add(results[0])
    }
  }

  const add = (t: Track) => {
    if (send({ type: 'add', video_id: t.video_id })) {
      setAdded((s) => new Set(s).add(t.video_id))
      onAdded(t.title)
    }
  }

  return (
    <div className="add-song" ref={box} onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}>
      <form className="add-song-row" onSubmit={submit}>
        <label className="sr-only" htmlFor="add-song-input">
          Search for a song or paste a link from YouTube, Spotify, Apple Music and more
        </label>
        <input
          id="add-song-input"
          className="add-input"
          placeholder="Search songs, or paste a YouTube, Spotify or Apple Music link"
          value={q}
          autoComplete="off"
          onChange={(e) => {
            setQ(e.target.value)
            setOpen(true)
            setAdded(new Set())
          }}
          onFocus={() => setOpen(true)}
        />
        {isUrl && (
          <button type="submit" className="btn btn-yellow">
            Add link
          </button>
        )}
      </form>

      {open && q.trim() && !isUrl && (
        <div className="results" role="listbox" aria-label="Search results">
          {loading && !results && <div className="results-note">Digging through the crates…</div>}
          {results && results.length === 0 && (
            <div className="results-note">No songs matched “{q.trim()}”. Try the artist's name, or paste a link.</div>
          )}
          {results && results.length > 0 && (
            <ul className="track-list">
              {results.map((t) => (
                <li key={t.video_id} className="track">
                  <img referrerPolicy="no-referrer" className="track-art" src={t.thumb} alt="" loading="lazy" />
                  <div className="track-text">
                    <div className="track-title">{t.title}</div>
                    <div className="track-sub">
                      {t.artist}
                      {t.album ? ` · ${t.album}` : ''}
                    </div>
                  </div>
                  <div className="track-actions">
                    <span className="track-duration">{formatTime(t.duration)}</span>
                    <button
                      className="add-btn"
                      onClick={() => add(t)}
                      aria-label={`Add ${t.title} to the queue`}
                      disabled={added.has(t.video_id)}
                    >
                      {added.has(t.video_id) ? <CheckIcon /> : <PlusIcon />}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
