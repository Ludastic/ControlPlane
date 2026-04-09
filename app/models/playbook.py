from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Playbook(TimestampMixin, Base):
    __tablename__ = "playbooks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    artifacts = relationship("Artifact", back_populates="playbook", cascade="all, delete-orphan")
    policy_resources = relationship("PolicyResource", back_populates="playbook")
