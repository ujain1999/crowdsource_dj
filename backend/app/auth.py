import hashlib
import hmac
import re
import secrets
import sqlite3
from dataclasses import dataclass

from . import db

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")
MAX_PASSWORD_LENGTH = 256


class AuthError(Exception):
    pass


@dataclass
class User:
    id: int
    username: str

    def public(self) -> dict:
        return {"id": self.id, "username": self.username}


def _hash(password: str, salt: bytes) -> str:
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def _verify(password: str, stored: str) -> bool:
    try:
        _, salt_hex, _ = stored.split("$")
    except ValueError:
        return False
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    return hmac.compare_digest(_hash(password, salt), stored)


# Checked when the username doesn't exist, so a failed login takes the same time either way.
_DUMMY_HASH = _hash("not-a-real-password", bytes(16))


def signup(username: str, password: str) -> tuple[User, str]:
    username = (username or "").strip()
    if not USERNAME_RE.match(username):
        raise AuthError("Usernames are 3–24 characters: letters, numbers, dots, dashes or underscores.")
    if len(password or "") < 6:
        raise AuthError("Passwords need at least 6 characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise AuthError(f"Passwords can be at most {MAX_PASSWORD_LENGTH} characters.")
    try:
        user_id = db.create_user(username, _hash(password, secrets.token_bytes(16)))
    except sqlite3.IntegrityError:
        raise AuthError(f"The name “{username}” is taken. Try another one.")
    return _new_session(User(user_id, username))


def login(username: str, password: str) -> tuple[User, str]:
    password = password or ""
    row = db.get_user_by_name((username or "").strip()[:64])
    too_long = len(password) > MAX_PASSWORD_LENGTH
    ok = _verify(password[:MAX_PASSWORD_LENGTH], row["password_hash"] if row else _DUMMY_HASH)
    if row is None or too_long or not ok:
        raise AuthError("That username and password don't match.")
    return _new_session(User(row["id"], row["username"]))


def _new_session(user: User) -> tuple[User, str]:
    token = secrets.token_urlsafe(32)
    db.create_session(token, user.id)
    return user, token


def user_for_token(token: str | None) -> User | None:
    if not isinstance(token, str) or not token or len(token) > 128:
        return None
    row = db.user_for_token(token)
    return User(row["id"], row["username"]) if row else None


def logout(token: str) -> None:
    db.delete_session(token)
