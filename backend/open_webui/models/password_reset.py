"""Single-use, time-limited password reset / account-setup tokens.

Only a SHA-256 hash of each token is stored, so a leak of the ``password_reset_token``
table cannot be used to take over accounts. One token type backs both the
forgot-password flow and the new-user account-setup email.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
import uuid

from open_webui.internal.db import Base, get_async_db_context
from sqlalchemy import BigInteger, Column, String, Text, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


class PasswordResetToken(Base):
    """A hashed, expiring, single-use credential for setting a password."""

    __tablename__ = 'password_reset_token'

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    token_hash = Column(Text, nullable=False, unique=True)
    expires_at = Column(BigInteger, nullable=False)
    used_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, nullable=False)


class PasswordResetTokensTable:
    """Data-access layer for password reset / setup tokens."""

    async def create(
        self,
        user_id: str,
        ttl_seconds: int,
        db: AsyncSession | None = None,
    ) -> str:
        """Mint a new token for ``user_id`` and return the raw (unhashed) value.

        Any previously issued tokens for the user are invalidated first, so only
        the most recent link is ever valid.
        """
        raw_token = secrets.token_urlsafe(32)
        now = int(time.time())
        async with get_async_db_context(db) as session:
            await session.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id))
            session.add(
                PasswordResetToken(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    token_hash=_hash_token(raw_token),
                    expires_at=now + ttl_seconds,
                    used_at=None,
                    created_at=now,
                )
            )
            await session.commit()
        return raw_token

    async def verify_and_consume(
        self,
        raw_token: str,
        db: AsyncSession | None = None,
    ) -> str | None:
        """Validate a raw token and mark it used. Returns the user_id or None.

        Returns None if the token is unknown, already used, or expired.
        """
        if not raw_token:
            return None
        token_hash = _hash_token(raw_token)
        now = int(time.time())
        async with get_async_db_context(db) as session:
            row = (
                await session.execute(
                    select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
                )
            ).scalar_one_or_none()
            if row is None or row.used_at is not None or row.expires_at < now:
                return None
            # Atomically claim the token: the UPDATE only matches while used_at is
            # still NULL, so a concurrent request cannot consume it twice.
            result = await session.execute(
                update(PasswordResetToken)
                .where(PasswordResetToken.id == row.id, PasswordResetToken.used_at.is_(None))
                .values(used_at=now)
            )
            await session.commit()
            if result.rowcount != 1:
                return None
            return row.user_id

    async def invalidate_for_user(
        self,
        user_id: str,
        db: AsyncSession | None = None,
    ) -> None:
        """Delete all outstanding tokens for a user (e.g. after a password change)."""
        async with get_async_db_context(db) as session:
            await session.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id))
            await session.commit()


PasswordResetTokens = PasswordResetTokensTable()  # singleton — module-level instance
