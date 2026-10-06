# Developing Crowdsource DJ

- **Backend:** Python, FastAPI, WebSockets, SQLite (`backend/`)
- **Frontend:** React + TypeScript + Vite (`frontend/`)
- **Music:** `ytmusicapi` for search and suggestions, `yt_dlp` for pasted links and playlists.
  Nothing is downloaded; each browser streams the song from YouTube's embedded player.

## Running it

Needs Python 3.13+ with [uv](https://docs.astral.sh/uv/) and Node 20+.

```sh
# backend (http://localhost:8000)
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000

# frontend dev server (http://localhost:5173), proxies /api and /ws to :8000
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** (use `localhost`, not `127.0.0.1`: YouTube refuses to play
embeds on bare-IP origins and reports error 150).

For a single-server setup, `npm run build` in `frontend/`, then the backend serves the
built app at http://localhost:8000.

### Docker

```sh
docker compose up --build    # http://localhost:8000
```

One image builds the frontend and serves it from the backend. The SQLite database lives in
the `cdj-data` volume (mounted at `/data`), so accounts and rooms survive rebuilds;
`docker compose down -v` wipes it. Set the variables under [Configuration](#configuration) in
`docker-compose.yml`.

## How it works

**Sync.** The server owns the room clock. Playback is `{playing, position, updated_at}` and
every client computes the live position as `position + (server_now − updated_at)`. Clients
estimate their offset to the server clock with ping/pong (best of the lowest-latency
samples). Each client's YouTube player is checked twice a second and corrected when it drifts
more than 0.3s. The player also learns its own start-up latency after loads and seeks and aims
that far ahead, so listeners land within a few hundredths of a second of each other. Every
change is broadcast as a full state snapshot, so a client that misses a message converges on
the next one.

**Songs end on the server.** The server schedules the next song from the track's duration
(clients also report "ended" as a backup), so a room keeps playing even if the DJ's tab is
closed. When the queue runs out, the top suggestion is promoted into the queue.

**Suggestions** come from YouTube Music's free "radio" mix for songs in the queue. The DJ crew
can refresh them for a fresh batch, drop individual ones, and anyone can pull one into the queue.

**Roles**

| | Listen, chat, add songs, /voteskip | Remove any song, delete messages, remove people | Play/pause/seek/next/prev, reorder, settings, assign roles, refresh suggestions | Hand over booth, delete room |
|---|---|---|---|---|
| Listener (guest OK) | ✓ | own songs only | | |
| Moderator | ✓ | ✓ | | |
| Co-DJ | ✓ | ✓ | ✓ | |
| DJ | ✓ | ✓ | ✓ | ✓ |

Creating a room, being made co-DJ or moderator, and deleting a room need an account (a guest
can end up as DJ when the booth passes to them, but can't delete the room). Guests can sign up
or log in from inside a room without leaving it.

**DJ leaves.** Pressing *Leave* hands the booth over at once. Closing the tab gives a
15-second grace period (so a refresh doesn't cost you the booth). The new DJ is a random
co-DJ, else a random moderator, else anyone (people with accounts first).

**/voteskip.** Typing `/voteskip` anywhere in a chat message starts a 60-second poll for the
current song. Everyone in the room gets one vote. The song is skipped when **more than** the
DJ's threshold (default 50%, set in room settings) of the people in the room vote yes. If
enough people vote no that it can't pass, it closes early.

**Unplayable videos.** Some uploads block embedding. The song is skipped once more than half of
the listeners whose players are running report the error, so one listener's ad blocker or
region lock can't skip it for everyone.

## Tests

```sh
cd backend
uv run pytest                      # protocol tests: roles, sync state, voteskip, succession, auth…

# Real-player sync check: needs both dev servers running.
uv run playwright install chromium # once
uv run python e2e/sync_check.py --listeners 3
```

`e2e/sync_check.py` opens a DJ and several listeners in headless Chromium, plays real songs,
and measures how far apart the players are through play, pause, seek, skip and a late join.

## Configuration

Environment variables for the backend:

| Variable | Default | |
|---|---|---|
| `CDJ_DB_PATH` | `backend/data/crowdsource_dj.sqlite3` | SQLite file (accounts, sessions, room snapshots) |
| `CDJ_DJ_GRACE_SECONDS` | `15` | How long a disconnected DJ keeps the booth |
| `CDJ_POLL_SECONDS` | `60` | How long a /voteskip poll stays open |
| `CDJ_FRONTEND_DIST` | `frontend/dist` | Built frontend to serve |
| `CDJ_SESSION_TTL_SECONDS` | `2592000` (30 days) | How long a login lasts |
| `CDJ_CLIENT_IP_HEADER` | unset | Header holding the visitor's real address, e.g. `CF-Connecting-IP`. See [Deploying](#deploying) |
| `FORWARDED_ALLOW_IPS` | `*` in the Docker image | Proxies uvicorn trusts for `X-Forwarded-For`/`-Proto` |

## Deploying

The Docker image is the deployable unit: it runs as a non-root user, keeps its data in
`/data`, and limits WebSocket messages to 64 KB. Run **one** process: rooms, rate limits and
live connections are kept in memory.

**The visitor's address.** Login lockouts, signup and search limits, and the cap on open
connections are counted per address, so the app must see the real one, and nobody may be able
to fake it. Pick the setup that matches how traffic reaches the app:

| How traffic arrives | Set | Make sure |
|---|---|---|
| Cloudflare (Tunnel, or proxied DNS). This is what `docker-compose.yml` assumes | `CDJ_CLIENT_IP_HEADER=CF-Connecting-IP` | The app is reachable **only** through Cloudflare: no published port, or a firewall that only lets in Cloudflare. Otherwise anyone can send the header themselves. |
| Another reverse proxy (nginx, Caddy, Traefik, a load balancer) | Leave `CDJ_CLIENT_IP_HEADER` unset. Set `FORWARDED_ALLOW_IPS` to the proxy's address | The proxy sets `X-Forwarded-For` itself. |
| Directly, no proxy | Leave `CDJ_CLIENT_IP_HEADER` unset. Set `FORWARDED_ALLOW_IPS=127.0.0.1` so clients can't send `X-Forwarded-For` | |

If you move off Cloudflare, remove `CDJ_CLIENT_IP_HEADER` from `docker-compose.yml`.

**With [`qd`](https://github.com/ujain1999/quick_deploy)** (Cloudflare Tunnel → Traefik → app on the
`qd` Docker network), `qd deploy` uses `docker-compose.yml` as is: it drops the published port, so
the only way in is through Cloudflare. `.qdignore` keeps local databases and dev files off the
server.
