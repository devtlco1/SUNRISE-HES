from __future__ import annotations

import uuid
from datetime import date

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Date, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Consumer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "consumers"

    external_ref: Mapped[str | None] = mapped_column(String(128))
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    consumer_type: Mapped[str] = mapped_column(String(64), nullable=False, server_default="residential")
    national_id: Mapped[str | None] = mapped_column(String(64))
    phone_number: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        UniqueConstraint("external_ref"),
        UniqueConstraint("national_id"),
    )


class ServicePoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_points"

    service_point_code: Mapped[str] = mapped_column(String(128), nullable=False)
    sector_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sectors.id"))
    transformer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transformers.id"))
    address_line: Mapped[str | None] = mapped_column(String(255))
    premises_type: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    geometry: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
    notes: Mapped[str | None] = mapped_column(Text())

    __table_args__ = (
        UniqueConstraint("service_point_code"),
        Index("ix_service_points_sector_id", "sector_id"),
        Index("ix_service_points_transformer_id", "transformer_id"),
    )


class MeterAccountAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "meter_account_assignments"

    meter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meters.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    service_point_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("service_points.id"))
    active_from: Mapped[date] = mapped_column(Date(), nullable=False)
    active_to: Mapped[date | None] = mapped_column(Date())
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        UniqueConstraint("meter_id", "account_id", "active_from"),
        Index("ix_meter_account_assignments_account_id", "account_id"),
        Index("ix_meter_account_assignments_meter_current", "meter_id", "is_current"),
    )
