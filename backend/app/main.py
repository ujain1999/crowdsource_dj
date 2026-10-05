import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, config, music
from .room import Client, Identity, RoomManager, identity_public, normalize_room_id, pretty_room_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("crowdsource_dj")

rooms = RoomManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    rooms.save_all()


app = FastAPI(title="Crowdsource DJ", lifespan=lifespan)


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
def signup(body: Credentials):
    try:
        user, token = auth.signup(body.username, body.password)
    except auth.AuthError as e:
        raise HTTPException(400, str(e))
    return {"token": token, "user": user.public()}


@app.post("/api/auth/login")
def login(body: Credentials):
    try:
        user, token = auth.login(body.username, body.password)
    except auth.AuthError as e:
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
async def search(q: str):
    q = q.strip()
    if not q:
        return {"results": []}
    if music.looks_like_url(q):
        return {"results": [], "is_url": True}
    return {"results": await asyncio.to_thread(music.search, q)}


# ---- realtime -----------------------------------------------------------------------------

@app.websocket("/ws/{raw_id}")
async def room_socket(ws: WebSocket, raw_id: str):
    await ws.accept()
    room_id = normalize_room_id(raw_id)
    room = rooms.get(room_id) if room_id else None
    if not room:
        await ws.send_json({"type": "not_found"})
        await ws.close(code=4404)
        return

    params = ws.query_params
    user = await asyncio.to_thread(auth.user_for_token, params.get("token"))
    identity = (
        Identity.for_user(user) if user
        else Identity.for_guest(params.get("client_id", ""), params.get("name", ""))
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
        "token_rejected": bool(params.get("token")) and user is None,
        "chat": list(room.chat)[-100:],
    })
    room.attach(client)
    client.send({"type": "state", "state": room.public_state()})

    try:
        while True:
            msg = await ws.receive_json()
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
