import hashlib
import secrets
import time
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from cryptography.fernet import Fernet

PH = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def verify_password(password, password_hash):
    try:
        return PH.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def auth_version(config):
    return digest(config.password_hash)


def login(db, config, password, ip):
    key = digest("login:" + ip)
    with db.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        c.execute("DELETE FROM rate_limits WHERE reset_at < ?",(time.time(),))
        row = c.execute("SELECT attempts,reset_at FROM rate_limits WHERE key=?", (key,)).fetchone()
        if row and row[1] > time.time() and row[0] >= 8:
            return None, "rate_limited"
        attempts = row[0] + 1 if row and row[1] > time.time() else 1
        reset_at = row[1] if row and row[1] > time.time() else time.time() + 900
        c.execute("INSERT INTO rate_limits VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET attempts=?,reset_at=?", (key, attempts, reset_at, attempts, reset_at))
    if not verify_password(password, config.password_hash):
        return None, "invalid"
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    with db.connect() as c:
        c.execute("DELETE FROM rate_limits WHERE key=?", (key,))
        c.execute("DELETE FROM sessions WHERE expires < ? OR auth_version != ?", (time.time(), auth_version(config)))
        c.execute("INSERT INTO sessions VALUES(?,?,?,?)", (digest(token), csrf, time.time()+86400, auth_version(config)))
    return {"token": token, "csrf": csrf}, None


def session(db, config, token):
    if not token or len(token) > 200:
        return None
    rows = db.rows("SELECT csrf FROM sessions WHERE token_hash=? AND expires>? AND auth_version=?", (digest(token), time.time(), auth_version(config)))
    return rows[0] if rows else None


def encrypt(config, plaintext):
    return Fernet(config.encryption_key.encode()).encrypt(plaintext.encode()).decode()


def decrypt(config, ciphertext):
    return Fernet(config.encryption_key.encode()).decrypt(ciphertext.encode()).decode()
