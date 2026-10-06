import os
import tempfile
import uuid

_tmp = tempfile.mkdtemp(prefix="cdj-test-")
os.environ["CDJ_DB_PATH"] = os.path.join(_tmp, "test.sqlite3")
os.environ["CDJ_OFFLINE_MUSIC"] = "1"
os.environ["CDJ_DJ_GRACE_SECONDS"] = "0.4"
os.environ["CDJ_POLL_SECONDS"] = "30"
os.environ["CDJ_FRONTEND_DIST"] = os.path.join(_tmp, "no-frontend")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_rate_limits():
    for limiter in (main.failed_logins, main.failed_logins_any_address, main.auth_attempts, main.searches,
                    main.room_creations):
        limiter.reset()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class Person:
    """A websocket participant that keeps track of the latest room state."""

    def __init__(self, ws):
        self.ws = ws
        self.state = None
        self.you = None
        self.chat = []
        self.errors = []
        self.events = []

    def _consume(self, msg):
        t = msg["type"]
        if t == "state":
            self.state = msg["state"]
        elif t in ("hello", "identity"):
            self.you = msg["you"]
            self.chat.extend(msg.get("chat", []))
        elif t == "chat":
            self.chat.append(msg["message"])
        elif t == "error":
            self.errors.append(msg["message"])
        self.events.append(msg)
        return msg

    def next(self):
        return self._consume(self.ws.receive_json())

    def until(self, pred, limit=200):
        for _ in range(limit):
            msg = self.next()
            if pred(msg, self):
                return msg
        raise AssertionError("condition never met")

    def until_state(self, pred, limit=200):
        return self.until(lambda m, p: m["type"] == "state" and pred(p.state), limit)["state"]

    def until_error(self):
        return self.until(lambda m, p: m["type"] == "error")["message"]

    def send(self, **msg):
        self.ws.send_json(msg)

    @property
    def key(self):
        return self.you["key"]

    def role(self, key=None):
        key = key or self.key
        for m in self.state["members"]:
            if m["key"] == key:
                return m["role"]
        return None


@pytest.fixture
def signup(client):
    def make(name=None):
        name = name or f"u{uuid.uuid4().hex[:8]}"
        r = client.post("/api/auth/signup", json={"username": name, "password": "secret123"})
        assert r.status_code == 200, r.text
        return r.json()["token"], r.json()["user"]
    return make


@pytest.fixture
def new_room(client, signup):
    def make():
        token, user = signup()
        r = client.post("/api/rooms", json={}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        return r.json()["id"], token, user
    return make


@pytest.fixture
def join(client):
    """Returns a context-manager factory: with join(room, token=...) as person."""
    from contextlib import contextmanager

    @contextmanager
    def connect(room_id, token=None, name="Guest"):
        with client.websocket_connect(f"/ws/{room_id}") as ws:
            ws.send_json({"type": "join", "token": token, "client_id": uuid.uuid4().hex, "name": name})
            p = Person(ws)
            p.until(lambda m, _: m["type"] == "state")
            yield p
    return connect
