from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Host(TimestampMixin, Base):
    __tablename__ = "hosts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    fqdn: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="online", nullable=False)
    agent_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    group_memberships = relationship("HostGroupMembership", back_populates="host", cascade="all, delete-orphan")
    inventory_snapshots = relationship("InventorySnapshot", back_populates="host", cascade="all, delete-orphan")
    execution_runs = relationship("ExecutionRun", back_populates="host", cascade="all, delete-orphan")
    policy_assignments = relationship("PolicyAssignment", back_populates="host")
