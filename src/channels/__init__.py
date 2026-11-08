"""Reusable authenticated message dispatch, independent of platform SDKs."""
from .gateway import MessageGateway

__all__ = ['MessageGateway']
