"""Email-based MFA: one-time login codes and trusted-device tokens.

Only SHA-256 hashes are stored, so a dump of these tables cannot be replayed to
bypass the second factor. Login codes are single-use, expiring, and attempt-limited
to keep the small 6-digit space from being brute-forced.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
import uuid

from open_webui.internal.db import Base, get_async_db_context
from sqlalchemy import BigInteger, Column, Integer, String, Text, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

MAX_CODE_ATTEMPTS = 5


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


class MfaCode(Base):
    """A single-use, expiring 6-digit login code (stored hashed)."""

    __tablename__ = 'mfa_code'

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, unique=True)  # one active code per user
    code_hash = Column(Text, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    expires_at = Column(BigInteger, nullable=False)
    created_at = Column(BigInteger, nullable=False)


class MfaTrustedDevice(Base):
    """A browser the user chose to trust, so MFA is skipped until it expires."""

    __tablename__ = 'mfa_trusted_device'

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    token_hash = Column(Text, nullable=False, unique=True)
    user_agent = Column(Text, nullable=True)
    expires_at = Column(BigInteger, nullable=False)
    created_at = Column(BigInteger, nullable=False)


class MfaCodesTable:
    """Data-access for one-time login codes."""

    async def create(self, user_id: str, ttl_seconds: int, db: AsyncSession | None = None) -> str:
        """Issue a fresh 6-digit code for the user and return the raw value.

        Any previous code for the user is replaced so only the latest is valid.
        """
        raw_code = f'{secrets.randbelow(1000000):06d}'
        now = int(time.time())
        async with get_async_db_context(db) as session:
            await session.execute(delete(MfaCode).where(MfaCode.user_id == user_id))
            session.add(
                MfaCode(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    code_hash=_hash(raw_code),
                    attempts=0,
                    expires_at=now + ttl_seconds,
                    created_at=now,
                )
            )
            await session.commit()
        return raw_code

    async def verify(self, user_id: str, code: str, db: AsyncSession | None = None) -> str:
        """Validate a code. Returns 'ok', 'invalid', 'expired', or 'locked'.

        On success the code is consumed (deleted). A wrong code increments the
        attempt counter and locks (deletes) the code once the limit is reached.
        """
        code = (code or '').strip()
        now = int(time.time())
        async with get_async_db_context(db) as session:
            row = (
                await session.execute(select(MfaCode).where(MfaCode.user_id == user_id))
            ).scalar_one_or_none()
            if row is None:
                return 'invalid'
            if row.expires_at < now:
                await session.execute(delete(MfaCode).where(MfaCode.id == row.id))
                await session.commit()
                return 'expired'
            if row.code_hash == _hash(code):
                await session.execute(delete(MfaCode).where(MfaCode.id == row.id))
                await session.commit()
                return 'ok'
            # Wrong code: count the attempt and lock out once exhausted.
            new_attempts = row.attempts + 1
            if new_attempts >= MAX_CODE_ATTEMPTS:
                await session.execute(delete(MfaCode).where(MfaCode.id == row.id))
                await session.commit()
                return 'locked'
            await session.execute(
                update(MfaCode).where(MfaCode.id == row.id).values(attempts=new_attempts)
            )
            await session.commit()
            return 'invalid'

    async def clear(self, user_id: str, db: AsyncSession | None = None) -> None:
        async with get_async_db_context(db) as session:
            await session.execute(delete(MfaCode).where(MfaCode.user_id == user_id))
            await session.commit()


class MfaTrustedDevicesTable:
    """Data-access for trusted-device tokens."""

    async def create(
        self,
        user_id: str,
        ttl_seconds: int,
        user_agent: str | None = None,
        db: AsyncSession | None = None,
    ) -> str:
        """Create a trusted-device record and return the raw cookie token."""
        raw_token = secrets.token_urlsafe(32)
        now = int(time.time())
        async with get_async_db_context(db) as session:
            session.add(
                MfaTrustedDevice(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    token_hash=_hash(raw_token),
                    user_agent=(user_agent or '')[:512] or None,
                    expires_at=now + ttl_seconds,
                    created_at=now,
                )
            )
            await session.commit()
        return raw_token

    async def is_trusted(self, user_id: str, raw_token: str, db: AsyncSession | None = None) -> bool:
        """True if the token maps to a non-expired trusted device for this user."""
        if not raw_token:
            return False
        now = int(time.time())
        async with get_async_db_context(db) as session:
            row = (
                await session.execute(
                    select(MfaTrustedDevice).where(
                        MfaTrustedDevice.token_hash == _hash(raw_token),
                        MfaTrustedDevice.user_id == user_id,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            if row.expires_at < now:
                await session.execute(delete(MfaTrustedDevice).where(MfaTrustedDevice.id == row.id))
                await session.commit()
                return False
            return True

    async def revoke_all(self, user_id: str, db: AsyncSession | None = None) -> None:
        async with get_async_db_context(db) as session:
            await session.execute(delete(MfaTrustedDevice).where(MfaTrustedDevice.user_id == user_id))
            await session.commit()


MfaCodes = MfaCodesTable()  # singleton
MfaTrustedDevices = MfaTrustedDevicesTable()  # singleton
