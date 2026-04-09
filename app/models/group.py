from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Group(TimestampMixin, Base):
    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    host_memberships = relationship("HostGroupMembership", back_populates="group", cascade="all, delete-orphan")
    policy_assignments = relationship("PolicyAssignment", back_populates="group")


class HostGroupMembership(Base):
    __tablename__ = "host_group_memberships"
    __table_args__ = (UniqueConstraint("host_id", "group_id", name="uq_host_group_membership"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    host_id: Mapped[str] = mapped_column(ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)

    host = relationship("Host", back_populates="group_memberships")
    group = relationship("Group", back_populates="host_memberships")
