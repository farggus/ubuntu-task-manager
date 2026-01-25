"""Data models for the application."""

from models.fail2ban import (
    BannedIP,
    Fail2banStatus,
    JailInfo,
    JailType,
)

__all__ = [
    'BannedIP',
    'Fail2banStatus',
    'JailInfo',
    'JailType',
]
