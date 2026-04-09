"""add execution event id

Revision ID: 20260409_0004
Revises: 20260409_0003
Create Date: 2026-04-09 20:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_0004"
down_revision = "20260409_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("execution_events", sa.Column("event_id", sa.String(length=128), nullable=True))
    op.create_index(op.f("ix_execution_events_event_id"), "execution_events", ["event_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_execution_events_event_id"), table_name="execution_events")
    op.drop_column("execution_events", "event_id")
