from __future__ import annotations

import uuid

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import enum_type
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.gis.enums import AssetStatus


class Region(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "regions"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[AssetStatus] = mapped_column(
        enum_type(AssetStatus, name="asset_status"),
        nullable=False,
        server_default=AssetStatus.ACTIVE.value,
    )
    geometry: Mapped[str | None] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))

    sectors: Mapped[list["Sector"]] = relationship(back_populates="region")

    __table_args__ = (
        UniqueConstraint("code"),
        UniqueConstraint("name"),
    )


class Sector(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sectors"

    region_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("regions.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[AssetStatus] = mapped_column(
        enum_type(AssetStatus, name="asset_status"),
        nullable=False,
        server_default=AssetStatus.ACTIVE.value,
    )
    geometry: Mapped[str | None] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))

    region: Mapped["Region"] = relationship(back_populates="sectors")
    substations: Mapped[list["Substation"]] = relationship(back_populates="sector")

    __table_args__ = (
        UniqueConstraint("region_id", "code"),
        Index("ix_sectors_region_id", "region_id"),
    )


class Substation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "substations"

    sector_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sectors.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[AssetStatus] = mapped_column(
        enum_type(AssetStatus, name="asset_status"),
        nullable=False,
        server_default=AssetStatus.ACTIVE.value,
    )
    location: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))

    sector: Mapped["Sector"] = relationship(back_populates="substations")
    feeders: Mapped[list["Feeder"]] = relationship(back_populates="substation")

    __table_args__ = (
        UniqueConstraint("sector_id", "code"),
        Index("ix_substations_sector_id", "sector_id"),
    )


class Feeder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "feeders"

    substation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("substations.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[AssetStatus] = mapped_column(
        enum_type(AssetStatus, name="asset_status"),
        nullable=False,
        server_default=AssetStatus.ACTIVE.value,
    )
    geometry: Mapped[str | None] = mapped_column(Geometry("MULTILINESTRING", srid=4326))

    substation: Mapped["Substation"] = relationship(back_populates="feeders")
    transformers: Mapped[list["Transformer"]] = relationship(back_populates="feeder")

    __table_args__ = (
        UniqueConstraint("substation_id", "code"),
        Index("ix_feeders_substation_id", "substation_id"),
    )


class Transformer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transformers"

    feeder_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feeders.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[AssetStatus] = mapped_column(
        enum_type(AssetStatus, name="asset_status"),
        nullable=False,
        server_default=AssetStatus.ACTIVE.value,
    )
    location: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
    description: Mapped[str | None] = mapped_column(Text())

    feeder: Mapped["Feeder"] = relationship(back_populates="transformers")

    __table_args__ = (
        UniqueConstraint("feeder_id", "code"),
        Index("ix_transformers_feeder_id", "feeder_id"),
    )
