"""One application API for CLI, Web and future messaging clients."""
from .session import SessionError, SessionStore

__all__ = ['SessionError', 'SessionStore']
