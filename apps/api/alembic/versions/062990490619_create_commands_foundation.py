"""create commands foundation"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '062990490619'
down_revision = 'f7d20a7d2bb2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    command_priority_enum = postgresql.ENUM(
        'low',
        'normal',
        'high',
        'urgent',
        name='command_priority',
    )
    command_priority_enum.create(op.get_bind(), checkfirst=True)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'command_status'
            ) THEN
                CREATE TYPE command_status AS ENUM (
                    'pending', 'scheduled', 'queued', 'in_progress', 'retry_wait', 'succeeded', 'failed', 'cancelled', 'timed_out'
                );
            ELSE
                ALTER TYPE command_status ADD VALUE IF NOT EXISTS 'queued';
                ALTER TYPE command_status ADD VALUE IF NOT EXISTS 'retry_wait';
                ALTER TYPE command_status ADD VALUE IF NOT EXISTS 'timed_out';
            END IF;
        END $$;
        """
    )
    op.create_table('command_templates',
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('category', sa.Enum('remote_disconnect', 'remote_reconnect', 'on_demand_read', 'clock_sync', 'profile_capture', 'connectivity_test', 'config_push', name='command_category'), nullable=False),
    sa.Column('target_scope', sa.Enum('meter', name='command_target_scope'), server_default='meter', nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('payload_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('timeout_seconds', sa.Integer(), server_default='120', nullable=False),
    sa.Column('max_retries', sa.Integer(), server_default='0', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_command_templates')),
    sa.UniqueConstraint('code', name=op.f('uq_command_templates_code'))
    )
    op.create_index('ix_command_templates_category', 'command_templates', ['category'], unique=False)
    op.create_index('ix_command_templates_is_active', 'command_templates', ['is_active'], unique=False)
    op.create_table('command_execution_attempts',
    sa.Column('meter_command_id', sa.Uuid(), nullable=False),
    sa.Column('attempt_number', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('started', 'succeeded', 'failed', 'cancelled', 'timed_out', name='command_execution_attempt_status'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('worker_identifier', sa.String(length=128), nullable=True),
    sa.Column('endpoint_id', sa.Uuid(), nullable=True),
    sa.Column('session_history_id', sa.Uuid(), nullable=True),
    sa.Column('bytes_sent', sa.Integer(), nullable=True),
    sa.Column('bytes_received', sa.Integer(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('error_code', sa.String(length=128), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('request_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('response_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('execution_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['endpoint_id'], ['communication_endpoints.id'], name=op.f('fk_command_execution_attempts_endpoint_id_communication_endpoints')),
    sa.ForeignKeyConstraint(['meter_command_id'], ['commands.id'], name=op.f('fk_command_execution_attempts_meter_command_id_commands'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['session_history_id'], ['connectivity_session_history.id'], name=op.f('fk_command_execution_attempts_session_history_id_connectivity_session_history')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_command_execution_attempts')),
    sa.UniqueConstraint('meter_command_id', 'attempt_number', name=op.f('uq_command_execution_attempts_meter_command_id'))
    )
    op.create_index('ix_command_execution_attempts_command_started_at', 'command_execution_attempts', ['meter_command_id', 'started_at'], unique=False)
    op.create_index('ix_command_execution_attempts_status_started_at', 'command_execution_attempts', ['status', 'started_at'], unique=False)
    op.add_column('commands', sa.Column('command_template_id', sa.Uuid(), nullable=True))
    op.add_column('commands', sa.Column('endpoint_assignment_id', sa.Uuid(), nullable=True))
    op.add_column('commands', sa.Column('protocol_association_profile_id', sa.Uuid(), nullable=True))
    op.add_column('commands', sa.Column('idempotency_key', sa.String(length=128), nullable=True))
    op.add_column('commands', sa.Column('priority', sa.Enum('low', 'normal', 'high', 'urgent', name='command_priority'), server_default='normal', nullable=False))
    op.add_column('commands', sa.Column('normalized_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('commands', sa.Column('result_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('commands', sa.Column('queued_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('commands', sa.Column('timeout_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('commands', sa.Column('latest_error_code', sa.String(length=128), nullable=True))
    op.add_column('commands', sa.Column('latest_error_message', sa.Text(), nullable=True))
    op.add_column('commands', sa.Column('max_retries', sa.Integer(), server_default='0', nullable=False))
    op.add_column('commands', sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('commands', sa.Column('notes', sa.Text(), nullable=True))
    op.execute(
        """
        INSERT INTO command_templates (
            code,
            name,
            category,
            target_scope,
            description,
            timeout_seconds,
            max_retries,
            is_active,
            id
        )
        SELECT DISTINCT
            lower(regexp_replace(command_type, '[^a-zA-Z0-9]+', '-', 'g')) AS code,
            initcap(replace(command_type, '_', ' ')) AS name,
            CASE
                WHEN command_type = 'remote_disconnect' THEN 'remote_disconnect'::command_category
                WHEN command_type = 'remote_reconnect' THEN 'remote_reconnect'::command_category
                WHEN command_type = 'clock_sync' THEN 'clock_sync'::command_category
                WHEN command_type = 'profile_capture' THEN 'profile_capture'::command_category
                WHEN command_type = 'connectivity_test' THEN 'connectivity_test'::command_category
                WHEN command_type = 'config_push' THEN 'config_push'::command_category
                ELSE 'on_demand_read'::command_category
            END AS category,
            'meter'::command_target_scope AS target_scope,
            'Migrated from legacy command_type column.' AS description,
            120 AS timeout_seconds,
            0 AS max_retries,
            true AS is_active,
            (
                substr(md5(command_type), 1, 8) || '-' ||
                substr(md5(command_type), 9, 4) || '-' ||
                substr(md5(command_type), 13, 4) || '-' ||
                substr(md5(command_type), 17, 4) || '-' ||
                substr(md5(command_type), 21, 12)
            )::uuid AS id
        FROM commands
        WHERE command_type IS NOT NULL
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        UPDATE commands AS c
        SET
            command_template_id = ct.id,
            result_summary = c.response_payload,
            latest_error_message = c.status_message
        FROM command_templates AS ct
        WHERE ct.code = lower(regexp_replace(c.command_type, '[^a-zA-Z0-9]+', '-', 'g'))
          AND c.command_template_id IS NULL;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM commands WHERE command_template_id IS NULL) THEN
                RAISE EXCEPTION 'Existing commands rows require command_template_id backfill before this migration can continue.';
            END IF;
        END $$;
        """
    )
    op.alter_column('commands', 'command_template_id', nullable=False)
    op.create_index('ix_commands_correlation_id', 'commands', ['correlation_id'], unique=False)
    op.create_index('ix_commands_pending_queue_lookup', 'commands', ['status', 'queued_at'], unique=False)
    op.create_unique_constraint(op.f('uq_commands_idempotency_key'), 'commands', ['idempotency_key'])
    op.create_foreign_key(op.f('fk_commands_protocol_association_profile_id_protocol_association_profiles'), 'commands', 'protocol_association_profiles', ['protocol_association_profile_id'], ['id'])
    op.create_foreign_key(op.f('fk_commands_endpoint_assignment_id_meter_endpoint_assignments'), 'commands', 'meter_endpoint_assignments', ['endpoint_assignment_id'], ['id'])
    op.create_foreign_key(op.f('fk_commands_command_template_id_command_templates'), 'commands', 'command_templates', ['command_template_id'], ['id'])
    op.drop_constraint(op.f('fk_commands_job_run_id_job_runs'), 'commands', type_='foreignkey')
    op.drop_index('ix_commands_job_run_id', table_name='commands')
    op.drop_column('commands', 'job_run_id')
    op.drop_column('commands', 'command_type')
    op.drop_column('commands', 'response_payload')
    op.drop_column('commands', 'status_message')


def downgrade() -> None:
    command_priority_enum = postgresql.ENUM(
        'low',
        'normal',
        'high',
        'urgent',
        name='command_priority',
    )
    op.add_column('commands', sa.Column('status_message', sa.Text(), nullable=True))
    op.add_column('commands', sa.Column('response_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('commands', sa.Column('command_type', sa.String(length=128), nullable=True))
    op.add_column('commands', sa.Column('job_run_id', sa.Uuid(), nullable=True))
    op.execute(
        """
        UPDATE commands AS c
        SET
            command_type = ct.code,
            response_payload = c.result_summary,
            status_message = c.latest_error_message
        FROM command_templates AS ct
        WHERE ct.id = c.command_template_id;
        """
    )
    op.create_index('ix_commands_job_run_id', 'commands', ['job_run_id'], unique=False)
    op.create_foreign_key(
        op.f('fk_commands_job_run_id_job_runs'),
        'commands',
        'job_runs',
        ['job_run_id'],
        ['id'],
    )
    op.drop_constraint(op.f('fk_commands_command_template_id_command_templates'), 'commands', type_='foreignkey')
    op.drop_constraint(op.f('fk_commands_endpoint_assignment_id_meter_endpoint_assignments'), 'commands', type_='foreignkey')
    op.drop_constraint(op.f('fk_commands_protocol_association_profile_id_protocol_association_profiles'), 'commands', type_='foreignkey')
    op.drop_constraint(op.f('uq_commands_idempotency_key'), 'commands', type_='unique')
    op.drop_index('ix_commands_pending_queue_lookup', table_name='commands')
    op.drop_index('ix_commands_correlation_id', table_name='commands')
    op.drop_column('commands', 'notes')
    op.drop_column('commands', 'retry_count')
    op.drop_column('commands', 'max_retries')
    op.drop_column('commands', 'latest_error_message')
    op.drop_column('commands', 'latest_error_code')
    op.drop_column('commands', 'timeout_at')
    op.drop_column('commands', 'queued_at')
    op.drop_column('commands', 'result_summary')
    op.drop_column('commands', 'normalized_payload')
    op.drop_column('commands', 'priority')
    op.drop_column('commands', 'idempotency_key')
    op.drop_column('commands', 'protocol_association_profile_id')
    op.drop_column('commands', 'endpoint_assignment_id')
    op.drop_column('commands', 'command_template_id')
    op.drop_index('ix_command_execution_attempts_status_started_at', table_name='command_execution_attempts')
    op.drop_index('ix_command_execution_attempts_command_started_at', table_name='command_execution_attempts')
    op.drop_table('command_execution_attempts')
    op.drop_index('ix_command_templates_is_active', table_name='command_templates')
    op.drop_index('ix_command_templates_category', table_name='command_templates')
    op.drop_table('command_templates')
    command_priority_enum.drop(op.get_bind(), checkfirst=True)
