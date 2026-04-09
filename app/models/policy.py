from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Policy(TimestampMixin, Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    assignments = relationship("PolicyAssignment", back_populates="policy", cascade="all, delete-orphan")
    resources = relationship("PolicyResource", back_populates="policy", cascade="all, delete-orphan")


class PolicyAssignment(TimestampMixin, Base):
    __tablename__ = "policy_assignments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    host_id: Mapped[str | None] = mapped_column(ForeignKey("hosts.id", ondelete="CASCADE"), nullable=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=True)

    policy = relationship("Policy", back_populates="assignments")
    host = relationship("Host", back_populates="policy_assignments")
    group = relationship("Group", back_populates="policy_assignments")


class PolicyResource(TimestampMixin, Base):
    __tablename__ = "policy_resources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(64), default="ansible_playbook", nullable=False)
    playbook_id: Mapped[str] = mapped_column(ForeignKey("playbooks.id", ondelete="RESTRICT"), nullable=False)
    playbook_version: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_order: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    variables: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    on_failure: Mapped[str] = mapped_column(String(32), default="stop", nullable=False)

    policy = relationship("Policy", back_populates="resources")
    playbook = relationship("Playbook", back_populates="policy_resources")
