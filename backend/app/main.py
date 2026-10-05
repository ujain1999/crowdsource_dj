import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, config, music
from .ratelimit import SlidingWindow, TokenBucket
from .room import Client, Identity, RoomManager, identity_public, normalize_room_id, pretty_room_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("crowdsource_dj")

rooms = RoomManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    rooms.save_all()


app = FastAPI(title="Crowdsource DJ", lifespan=lifespan)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


def _client_ip(request: Request) -> str:
    if config.CLIENT_IP_HEADER:
        forwarded = request.headers.get(config.CLIENT_IP_HEADER, "").strip()
        if forwarded:
            return forwarded[:64]
    return request.client.host if request.client else "unknown"


# Brute-force protection. Failed logins are counted per account and address, so one person
# guessing only locks themselves out, with a much higher per-account cap to slow guessing
# spread over many addresses. Auth attempts and searches are also capped per address.
failed_logins = SlidingWindow(limit=10, window=15 * 60)
failed_logins_any_address = SlidingWindow(limit=100, window=60 * 60)
auth_attempts = SlidingWindow(limit=30, window=60)
searches = SlidingWindow(limit=60, window=60)


# ---- auth ---------------------------------------------------------------------------------

class Credentials(BaseModel):
    username: str
    password: str


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def current_user(authorization: str | None) -> auth.User | None:
    return auth.user_for_token(_bearer(authorization))


@app.post("/api/auth/signup")
def signup(body: Credentials, request: Request):
    if not auth_attempts.allow(_client_ip(request)):
        raise HTTPException(429, "Too many attempts. Wait a minute and try again.")
    try:
        user, token = auth.signup(body.username, body.password)
    except auth.AuthError as e:
        raise HTTPException(400, str(e))
    return {"token": token, "user": user.public()}


@app.post("/api/auth/login")
def login(body: Credentials, request: Request):
    ip = _client_ip(request)
    name_key = body.username.strip().lower()[:64]
    name_ip_key = f"{name_key}|{ip}"
    if (
        not auth_attempts.allow(ip)
        or failed_logins.blocked(name_ip_key)
        or failed_logins_any_address.blocked(name_key)
    ):
        raise HTTPException(429, "Too many attempts. Wait a few minutes and try again.")
    try:
        user, token = auth.login(body.username, body.password)
    except auth.AuthError as e:
        failed_logins.hit(name_ip_key)
        failed_logins_any_address.hit(name_key)
        raise HTTPException(401, str(e))
    return {"token": token, "user": user.public()}


@app.get("/api/auth/me")
def me(authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    if not user:
        raise HTTPException(401, "Not logged in.")
    return {"user": user.public()}


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    token = _bearer(authorization)
    if token:
        auth.logout(token)
    return {"ok": True}


# ---- rooms --------------------------------------------------------------------------------

class NewRoom(BaseModel):
    name: str | None = None


@app.post("/api/rooms")
def create_room(body: NewRoom | None = None, authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    if not user:
        raise HTTPException(401, "Log in to create a room. DJs need an account.")
    room = rooms.create(user, body.name if body else None)
    return {"id": room.id, "pretty_id": pretty_room_id(room.id)}


@app.get("/api/rooms/{raw_id}")
def room_info(raw_id: str):
    room_id = normalize_room_id(raw_id)
    room = rooms.get(room_id) if room_id else None
    if not room:
        raise HTTPException(404, "There's no room with that code.")
    track = room.current_track()
    return {
        "id": room.id,
        "pretty_id": pretty_room_id(room.id),
        "name": room.name,
        "listeners": len(room.members),
        "dj_name": room.dj_name,
        "now_playing": {"title": track["title"], "artist": track["artist"]} if track and not room.finished else None,
    }


# ---- music --------------------------------------------------------------------------------

@app.get("/api/search")
async def search(q: str, request: Request):
    q = q.strip()[: config.MAX_SEARCH_LENGTH]
    if not q:
        return {"results": []}
    if music.looks_like_url(q):
        return {"results": [], "is_url": True}
    if not searches.allow(_client_ip(request)):
        raise HTTPException(429, "Searching too fast. Slow down a little.")
    return {"results": await asyncio.to_thread(music.search, q)}


# ---- realtime -----------------------------------------------------------------------------

JOIN_TIMEOUT = 10
MESSAGES_PER_SECOND = 5
MESSAGE_BURST = 20


@app.websocket("/ws/{raw_id}")
async def room_socket(ws: WebSocket, raw_id: str):
    await ws.accept()
    room_id = normalize_room_id(raw_id)
    room = rooms.get(room_id) if room_id else None
    if not room:
        await ws.send_json({"type": "not_found"})
        await ws.close(code=4404)
        return

    # Credentials arrive in the first message rather than the URL, so login tokens
    # never end up in access logs or proxy logs.
    try:
        join = await asyncio.wait_for(ws.receive_json(), timeout=JOIN_TIMEOUT)
    except (asyncio.TimeoutError, WebSocketDisconnect, RuntimeError, ValueError, KeyError):
        # KeyError: a binary frame, which receive_json can't read.
        await ws.close(code=4400)
        return
    if not isinstance(join, dict) or join.get("type") != "join":
        await ws.close(code=4400)
        return
    token = join.get("token") if isinstance(join.get("token"), str) else None
    user = await asyncio.to_thread(auth.user_for_token, token)
    identity = (
        Identity.for_user(user) if user
        else Identity.for_guest(str(join.get("client_id") or ""), str(join.get("name") or ""))
    )
    if room.is_banned(identity.key):
        await ws.send_json({"type": "kicked", "by": None})
        await ws.close(code=4403)
        return

    client = Client(identity, ws.send_json, ws.close)
    pump = asyncio.create_task(client.pump())
    client.send({
        "type": "hello",
        "you": identity_public(identity),
        "token_rejected": bool(token) and user is None,
        "chat": list(room.chat)[-100:],
    })
    room.attach(client)
    client.send({"type": "state", "state": room.public_state()})

    limiter = TokenBucket(rate=MESSAGES_PER_SECOND, burst=MESSAGE_BURST)
    try:
        while True:
            msg = await ws.receive_json()
            if not limiter.allow():
                client.send({"type": "error", "message": "Slow down a little."})
                continue
            if isinstance(msg, dict):
                await room.handle(client, msg)
            if client.closed or room.deleted:
                break
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception:
        log.exception("websocket error in room %s", room.id)
    finally:
        if not room.deleted:
            room.detach(client)
        client.close_soon()
        try:
            await asyncio.wait_for(pump, timeout=2)
        except Exception:
            pump.cancel()


# ---- frontend -----------------------------------------------------------------------------

if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        candidate = (config.FRONTEND_DIST / path).resolve()
        if path and candidate.is_file() and config.FRONTEND_DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(config.FRONTEND_DIST / "index.html")
