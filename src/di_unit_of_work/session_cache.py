from contextvars import ContextVar, Token

from sqlalchemy.orm import Session


class SessionCache:
    """Stores the current SQLAlchemy session in a context-local variable."""

    def __init__(self) -> None:
        self._session_ctx: ContextVar[Session | None] = ContextVar(
            "banking_app_session",
            default=None,
        )

    def get_current_session(self) -> Session | None:
        session = self._session_ctx.get()
        return session

    def has_active_session(self) -> bool:
        return self.get_current_session() is not None

    def set_current_session(self, session: Session) -> Token[Session | None]:
        return self._session_ctx.set(session)

    def reset_to_token(self, token: Token[Session | None]) -> None:
        self._session_ctx.reset(token)

    def clear(self) -> None:
        self._session_ctx.set(None)
