from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Account(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "accounts"

    consumer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("consumers.id"), nullable=False)
    service_point_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("service_points.id"))
    account_number: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, server_default="active")
    billing_cycle: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint("account_number"),
        Index("ix_accounts_consumer_id", "consumer_id"),
        Index("ix_accounts_service_point_id", "service_point_id"),
    )
