"""Add password_reset_token table

Revision ID: a7b8c9d0e1f2
Revises: 42e2978c7933
Create Date: 2026-07-21 00:00:00.000000

Stores hashed, single-use, expiring tokens backing the password-reset and
account-setup email flows.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from open_webui.migrations.util import get_existing_tables

revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = '42e2978c7933'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(get_existing_tables())

    if 'password_reset_token' not in existing_tables:
        op.create_table(
            'password_reset_token',
            sa.Column('id', sa.String(), nullable=False, primary_key=True),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('token_hash', sa.Text(), nullable=False),
            sa.Column('expires_at', sa.BigInteger(), nullable=False),
            sa.Column('used_at', sa.BigInteger(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.UniqueConstraint('token_hash', name='uq_password_reset_token_hash'),
        )
        op.create_index(
            'idx_password_reset_token_user',
            'password_reset_token',
            ['user_id'],
        )


def downgrade() -> None:
    existing_tables = set(get_existing_tables())
    if 'password_reset_token' in existing_tables:
        op.drop_index('idx_password_reset_token_user', table_name='password_reset_token')
        op.drop_table('password_reset_token')
