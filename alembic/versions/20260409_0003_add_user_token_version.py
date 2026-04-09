"""add user token version

Revision ID: 20260409_0003
Revises: 20260409_0002
Create Date: 2026-04-09 19:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_0003"
down_revision = "20260409_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("users", "token_version")
