"""refine meter registry schema"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'dcba41ea4f5a'
down_revision = '46c4d7ab94b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    transport_type_enum = postgresql.ENUM(
        "tcp_ip",
        "cellular",
        "rs485",
        "plc",
        name="transport_type",
    )
    ip_mode_enum = postgresql.ENUM(
        "static",
        "dhcp",
        "private_apn",
        name="ip_mode",
    )
    authentication_mode_enum = postgresql.ENUM(
        "none",
        "pap",
        "chap",
        "tls_psk",
        name="authentication_mode",
    )
    phase_type_enum = postgresql.ENUM(
        "single_phase",
        "three_phase",
        name="phase_type",
    )
    meter_category_enum = postgresql.ENUM(
        "electricity",
        "water",
        "gas",
        "heat",
        name="meter_category",
    )

    bind = op.get_bind()
    transport_type_enum.create(bind, checkfirst=True)
    ip_mode_enum.create(bind, checkfirst=True)
    authentication_mode_enum.create(bind, checkfirst=True)
    phase_type_enum.create(bind, checkfirst=True)
    meter_category_enum.create(bind, checkfirst=True)

    op.alter_column("communication_profiles", "transport", new_column_name="transport_type")
    op.alter_column(
        "communication_profiles",
        "transport_type",
        existing_type=sa.String(length=64),
        type_=transport_type_enum,
        postgresql_using=(
            "CASE "
            "WHEN transport_type IN ('tcp_ip', 'cellular', 'rs485', 'plc') "
            "THEN transport_type::transport_type "
            "ELSE 'tcp_ip'::transport_type END"
        ),
        nullable=False,
    )
    op.alter_column("communication_profiles", "settings_json", new_column_name="protocol_settings")
    op.add_column("communication_profiles", sa.Column("ip_mode", ip_mode_enum, nullable=True))
    op.add_column("communication_profiles", sa.Column("port", sa.Integer(), nullable=True))
    op.add_column("communication_profiles", sa.Column("apn", sa.String(length=255), nullable=True))
    op.add_column(
        "communication_profiles",
        sa.Column("authentication_mode", authentication_mode_enum, nullable=True),
    )
    op.add_column(
        "communication_profiles",
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )
    op.create_index(
        "ix_communication_profiles_is_active",
        "communication_profiles",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        "ix_communication_profiles_transport_type",
        "communication_profiles",
        ["transport_type"],
        unique=False,
    )

    op.add_column("meter_firmware_versions", sa.Column("release_notes", sa.Text(), nullable=True))
    op.add_column(
        "meter_firmware_versions",
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )
    op.drop_column("meter_firmware_versions", "release_date")
    op.create_index(
        "ix_meter_firmware_versions_is_active",
        "meter_firmware_versions",
        ["is_active"],
        unique=False,
    )

    op.alter_column("meter_manufacturers", "country_code", new_column_name="country")
    op.add_column("meter_manufacturers", sa.Column("website", sa.String(length=255), nullable=True))
    op.add_column(
        "meter_manufacturers",
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )
    op.create_index(
        "ix_meter_manufacturers_is_active",
        "meter_manufacturers",
        ["is_active"],
        unique=False,
    )

    op.alter_column("meter_models", "name", new_column_name="display_name")
    op.add_column("meter_models", sa.Column("phase_type", phase_type_enum, nullable=True))
    op.add_column("meter_models", sa.Column("meter_category", meter_category_enum, nullable=True))
    op.add_column(
        "meter_models",
        sa.Column("dlms_capable", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("meter_models", sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False))
    op.execute(
        """
        UPDATE meter_models
        SET
            phase_type = CASE
                WHEN phase_count = 3 THEN 'three_phase'::phase_type
                ELSE 'single_phase'::phase_type
            END,
            meter_category = 'electricity'::meter_category
        """
    )
    op.alter_column("meter_models", "phase_type", nullable=False)
    op.alter_column("meter_models", "meter_category", nullable=False)
    op.drop_column("meter_models", "phase_count")
    op.create_index("ix_meter_models_is_active", "meter_models", ["is_active"], unique=False)
    op.create_index(
        "ix_meter_models_meter_category",
        "meter_models",
        ["meter_category"],
        unique=False,
    )

    op.add_column("meter_profiles", sa.Column("meter_model_id", sa.Uuid(), nullable=True))
    op.add_column("meter_profiles", sa.Column("communication_profile_id", sa.Uuid(), nullable=True))
    op.add_column(
        "meter_profiles",
        sa.Column("protocol_defaults", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("meter_profiles", sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False))
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM meter_profiles) THEN
                RAISE EXCEPTION 'Existing meter_profiles rows require manual backfill for meter_model_id before this migration can continue.';
            END IF;
        END $$;
        """
    )
    op.alter_column("meter_profiles", "meter_model_id", nullable=False)
    op.create_index("ix_meter_profiles_is_active", "meter_profiles", ["is_active"], unique=False)
    op.create_index(
        "ix_meter_profiles_meter_model_id",
        "meter_profiles",
        ["meter_model_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_meter_profiles_communication_profile_id_communication_profiles"),
        "meter_profiles",
        "communication_profiles",
        ["communication_profile_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_meter_profiles_meter_model_id_meter_models"),
        "meter_profiles",
        "meter_models",
        ["meter_model_id"],
        ["id"],
    )

    op.add_column("meter_status_history", sa.Column("previous_status", sa.Enum(
        "registered", "commissioned", "active", "inactive", "retired", name="meter_lifecycle_status"
    ), nullable=True))
    op.alter_column("meter_status_history", "status", new_column_name="new_status")
    op.alter_column("meter_status_history", "recorded_at", new_column_name="changed_at")
    op.drop_index("ix_meter_status_history_meter_recorded_at", table_name="meter_status_history")
    op.drop_index("ix_meter_status_history_meter_status", table_name="meter_status_history")
    op.drop_column("meter_status_history", "source")
    op.create_index(
        "ix_meter_status_history_meter_changed_at",
        "meter_status_history",
        ["meter_id", "changed_at"],
        unique=False,
    )
    op.create_index(
        "ix_meter_status_history_meter_new_status",
        "meter_status_history",
        ["meter_id", "new_status"],
        unique=False,
    )

    op.drop_constraint(op.f("uq_meters_utility_meter_id"), "meters", type_="unique")
    op.alter_column("meters", "utility_meter_id", new_column_name="utility_meter_number")
    op.alter_column("meters", "lifecycle_status", new_column_name="current_status")
    op.drop_index("ix_meters_lifecycle_status", table_name="meters")
    op.add_column("meters", sa.Column("badge_number", sa.String(length=128), nullable=True))
    op.add_column("meters", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("meters", sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False))
    op.create_index("ix_meters_communication_profile_id", "meters", ["communication_profile_id"], unique=False)
    op.create_index("ix_meters_current_status", "meters", ["current_status"], unique=False)
    op.create_index("ix_meters_is_active", "meters", ["is_active"], unique=False)
    op.create_index("ix_meters_manufacturer_id", "meters", ["manufacturer_id"], unique=False)
    op.create_unique_constraint(
        op.f("uq_meters_utility_meter_number"),
        "meters",
        ["utility_meter_number"],
    )


def downgrade() -> None:
    op.drop_constraint(op.f("uq_meters_utility_meter_number"), "meters", type_="unique")
    op.drop_index("ix_meters_manufacturer_id", table_name="meters")
    op.drop_index("ix_meters_is_active", table_name="meters")
    op.drop_index("ix_meters_current_status", table_name="meters")
    op.drop_index("ix_meters_communication_profile_id", table_name="meters")
    op.drop_column("meters", "is_active")
    op.drop_column("meters", "notes")
    op.drop_column("meters", "badge_number")
    op.alter_column("meters", "current_status", new_column_name="lifecycle_status")
    op.alter_column("meters", "utility_meter_number", new_column_name="utility_meter_id")
    op.create_index("ix_meters_lifecycle_status", "meters", ["lifecycle_status"], unique=False)
    op.create_unique_constraint(op.f("uq_meters_utility_meter_id"), "meters", ["utility_meter_id"])

    op.drop_index("ix_meter_status_history_meter_new_status", table_name="meter_status_history")
    op.drop_index("ix_meter_status_history_meter_changed_at", table_name="meter_status_history")
    op.add_column("meter_status_history", sa.Column("source", sa.String(length=128), nullable=True))
    op.alter_column("meter_status_history", "changed_at", new_column_name="recorded_at")
    op.alter_column("meter_status_history", "new_status", new_column_name="status")
    op.drop_column("meter_status_history", "previous_status")
    op.create_index(
        "ix_meter_status_history_meter_recorded_at",
        "meter_status_history",
        ["meter_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_meter_status_history_meter_status",
        "meter_status_history",
        ["meter_id", "status"],
        unique=False,
    )

    op.drop_constraint(op.f("fk_meter_profiles_meter_model_id_meter_models"), "meter_profiles", type_="foreignkey")
    op.drop_constraint(
        op.f("fk_meter_profiles_communication_profile_id_communication_profiles"),
        "meter_profiles",
        type_="foreignkey",
    )
    op.drop_index("ix_meter_profiles_meter_model_id", table_name="meter_profiles")
    op.drop_index("ix_meter_profiles_is_active", table_name="meter_profiles")
    op.drop_column("meter_profiles", "is_active")
    op.drop_column("meter_profiles", "protocol_defaults")
    op.drop_column("meter_profiles", "communication_profile_id")
    op.drop_column("meter_profiles", "meter_model_id")

    op.drop_index("ix_meter_models_meter_category", table_name="meter_models")
    op.drop_index("ix_meter_models_is_active", table_name="meter_models")
    op.add_column("meter_models", sa.Column("phase_count", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE meter_models
        SET phase_count = CASE
            WHEN phase_type = 'three_phase' THEN 3
            ELSE 1
        END
        """
    )
    op.drop_column("meter_models", "is_active")
    op.drop_column("meter_models", "dlms_capable")
    op.drop_column("meter_models", "meter_category")
    op.drop_column("meter_models", "phase_type")
    op.alter_column("meter_models", "display_name", new_column_name="name")

    op.drop_index("ix_meter_manufacturers_is_active", table_name="meter_manufacturers")
    op.drop_column("meter_manufacturers", "is_active")
    op.drop_column("meter_manufacturers", "website")
    op.alter_column("meter_manufacturers", "country", new_column_name="country_code")

    op.drop_index("ix_meter_firmware_versions_is_active", table_name="meter_firmware_versions")
    op.add_column("meter_firmware_versions", sa.Column("release_date", sa.Date(), nullable=True))
    op.drop_column("meter_firmware_versions", "is_active")
    op.drop_column("meter_firmware_versions", "release_notes")

    op.drop_index("ix_communication_profiles_transport_type", table_name="communication_profiles")
    op.drop_index("ix_communication_profiles_is_active", table_name="communication_profiles")
    op.drop_column("communication_profiles", "is_active")
    op.drop_column("communication_profiles", "authentication_mode")
    op.drop_column("communication_profiles", "apn")
    op.drop_column("communication_profiles", "port")
    op.drop_column("communication_profiles", "ip_mode")
    op.alter_column("communication_profiles", "protocol_settings", new_column_name="settings_json")
    op.alter_column(
        "communication_profiles",
        "transport_type",
        existing_type=postgresql.ENUM("tcp_ip", "cellular", "rs485", "plc", name="transport_type"),
        type_=sa.String(length=64),
        postgresql_using="transport_type::text",
    )
    op.alter_column("communication_profiles", "transport_type", new_column_name="transport")

    postgresql.ENUM("tcp_ip", "cellular", "rs485", "plc", name="transport_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM("static", "dhcp", "private_apn", name="ip_mode").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM("none", "pap", "chap", "tls_psk", name="authentication_mode").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM("single_phase", "three_phase", name="phase_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM("electricity", "water", "gas", "heat", name="meter_category").drop(op.get_bind(), checkfirst=True)
