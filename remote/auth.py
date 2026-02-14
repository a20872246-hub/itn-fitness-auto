import bcrypt
import secrets
import time


class AuthManager:
    """Simple password-based authentication with session tokens."""

    def __init__(self, password_hash: str = ""):
        self._password_hash = password_hash.encode() if password_hash else b""
        self._sessions: dict[str, float] = {}
        self._session_duration = 86400  # 24 hours

    @property
    def is_configured(self) -> bool:
        return len(self._password_hash) > 0

    def set_password(self, password: str) -> str:
        """Hash and store a new password. Returns the hash string."""
        self._password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        return self._password_hash.decode()

    def verify_password(self, password: str) -> bool:
        if not self._password_hash:
            return False
        return bcrypt.checkpw(password.encode(), self._password_hash)

    def create_session(self) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = time.time() + self._session_duration
        self._cleanup_expired()
        return token

    def verify_session(self, token: str) -> bool:
        expiry = self._sessions.get(token)
        if expiry and time.time() < expiry:
            return True
        self._sessions.pop(token, None)
        return False

    def _cleanup_expired(self):
        now = time.time()
        expired = [t for t, exp in self._sessions.items() if now >= exp]
        for t in expired:
            del self._sessions[t]
