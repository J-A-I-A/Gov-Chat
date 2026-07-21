"""Add mfa_code and mfa_trusted_device tables

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-21 09:00:00.000000

Backs email-based login MFA: hashed one-time codes and trusted-device tokens.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from open_webui.migrations.util import get_existing_tables

revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(get_existing_tables())

    if 'mfa_code' not in existing_tables:
        op.create_table(
            'mfa_code',
            sa.Column('id', sa.String(), nullable=False, primary_key=True),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('code_hash', sa.Text(), nullable=False),
            sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('expires_at', sa.BigInteger(), nullable=False),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.UniqueConstraint('user_id', name='uq_mfa_code_user'),
        )

    if 'mfa_trusted_device' not in existing_tables:
        op.create_table(
            'mfa_trusted_device',
            sa.Column('id', sa.String(), nullable=False, primary_key=True),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('token_hash', sa.Text(), nullable=False),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('expires_at', sa.BigInteger(), nullable=False),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.UniqueConstraint('token_hash', name='uq_mfa_trusted_device_token'),
        )
        op.create_index(
            'idx_mfa_trusted_device_user',
            'mfa_trusted_device',
            ['user_id'],
        )


def downgrade() -> None:
    existing_tables = set(get_existing_tables())
    if 'mfa_trusted_device' in existing_tables:
        op.drop_index('idx_mfa_trusted_device_user', table_name='mfa_trusted_device')
        op.drop_table('mfa_trusted_device')
    if 'mfa_code' in existing_tables:
        op.drop_table('mfa_code')
