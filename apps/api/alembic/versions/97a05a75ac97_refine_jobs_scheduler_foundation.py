"""refine jobs scheduler foundation"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '97a05a75ac97'
down_revision = '062990490619'
branch_labels = None
depends_on = None


def upgrade() -> None:
    job_category_enum = postgresql.ENUM(
        'command',
        'meter_read',
        'connectivity_check',
        'system_maintenance',
        name='job_category',
    )
    job_target_type_enum = postgresql.ENUM(
        'meter',
        'endpoint',
        'system',
        name='job_target_type',
    )
    job_schedule_type_enum = postgresql.ENUM(
        'manual',
        'once',
        'cron',
        'interval',
        name='job_schedule_type',
    )
    job_run_status_enum = postgresql.ENUM(
        'pending',
        'claimed',
        'running',
        'succeeded',
        'failed',
        'cancelled',
        'timed_out',
        name='job_run_status',
    )
    bind = op.get_bind()
    job_category_enum.create(bind, checkfirst=True)
    job_target_type_enum.create(bind, checkfirst=True)
    job_schedule_type_enum.create(bind, checkfirst=True)
    job_run_status_enum.create(bind, checkfirst=True)

    op.add_column('job_runs', sa.Column('target_meter_id', sa.Uuid(), nullable=True))
    op.add_column('job_runs', sa.Column('target_endpoint_id', sa.Uuid(), nullable=True))
    op.add_column('job_runs', sa.Column('related_command_id', sa.Uuid(), nullable=True))
    op.add_column('job_runs', sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True))
    op.add_column('job_runs', sa.Column('available_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('job_runs', sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('job_runs', sa.Column('claim_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('job_runs', sa.Column('worker_identifier', sa.String(length=128), nullable=True))
    op.add_column('job_runs', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('job_runs', sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('job_runs', sa.Column('max_retries', sa.Integer(), server_default='0', nullable=False))
    op.add_column('job_runs', sa.Column('request_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('job_runs', sa.Column('latest_error_code', sa.String(length=128), nullable=True))
    op.execute("UPDATE job_runs SET scheduled_for = COALESCE(queued_at, now()), available_at = COALESCE(queued_at, now()) WHERE scheduled_for IS NULL OR available_at IS NULL")
    op.alter_column('job_runs', 'scheduled_for', nullable=False)
    op.alter_column('job_runs', 'available_at', nullable=False)
    op.execute("ALTER TABLE job_runs ALTER COLUMN status DROP DEFAULT")
    op.alter_column('job_runs', 'status',
               existing_type=postgresql.ENUM('draft', 'ready', 'running', 'succeeded', 'failed', 'paused', name='job_status'),
               type_=job_run_status_enum,
               postgresql_using=(
                   "CASE "
                   "WHEN status IN ('draft', 'ready') THEN 'pending'::job_run_status "
                   "WHEN status = 'running' THEN 'running'::job_run_status "
                   "WHEN status = 'succeeded' THEN 'succeeded'::job_run_status "
                   "WHEN status = 'failed' THEN 'failed'::job_run_status "
                   "WHEN status = 'paused' THEN 'cancelled'::job_run_status "
                   "ELSE 'pending'::job_run_status END"
               ),
               existing_nullable=False,
               existing_server_default=sa.text("'ready'::job_status"))
    op.execute("ALTER TABLE job_runs ALTER COLUMN status SET DEFAULT 'pending'::job_run_status")
    op.alter_column('job_runs', 'queued_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True,
               existing_server_default=sa.text('now()'))
    op.create_index('ix_job_runs_claimable_lookup', 'job_runs', ['status', 'available_at', 'claim_expires_at'], unique=False)
    op.create_index('ix_job_runs_recent_history', 'job_runs', ['scheduled_for', 'status'], unique=False)
    op.create_index('ix_job_runs_worker_identifier', 'job_runs', ['worker_identifier'], unique=False)
    op.create_foreign_key(op.f('fk_job_runs_target_meter_id_meters'), 'job_runs', 'meters', ['target_meter_id'], ['id'])
    op.create_foreign_key(op.f('fk_job_runs_related_command_id_commands'), 'job_runs', 'commands', ['related_command_id'], ['id'])
    op.create_foreign_key(op.f('fk_job_runs_target_endpoint_id_communication_endpoints'), 'job_runs', 'communication_endpoints', ['target_endpoint_id'], ['id'])
    op.add_column('jobs', sa.Column('target_type', job_target_type_enum, server_default='system', nullable=False))
    op.add_column('jobs', sa.Column('schedule_type', job_schedule_type_enum, server_default='manual', nullable=False))
    op.add_column('jobs', sa.Column('interval_seconds', sa.Integer(), nullable=True))
    op.add_column('jobs', sa.Column('command_template_id', sa.Uuid(), nullable=True))
    op.add_column('jobs', sa.Column('priority', postgresql.ENUM('low', 'normal', 'high', 'urgent', name='command_priority', create_type=False), server_default='normal', nullable=False))
    op.add_column('jobs', sa.Column('timeout_seconds', sa.Integer(), server_default='120', nullable=False))
    op.add_column('jobs', sa.Column('max_retries', sa.Integer(), server_default='0', nullable=False))
    op.add_column('jobs', sa.Column('notes', sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE jobs
        SET schedule_type = CASE
            WHEN schedule_expression IS NOT NULL THEN 'cron'::job_schedule_type
            ELSE 'manual'::job_schedule_type
        END
        """
    )
    op.alter_column('jobs', 'job_type',
               existing_type=sa.VARCHAR(length=128),
               type_=job_category_enum,
               postgresql_using=(
                   "CASE "
                   "WHEN job_type = 'meter_read' THEN 'meter_read'::job_category "
                   "WHEN job_type = 'connectivity_check' THEN 'connectivity_check'::job_category "
                   "WHEN job_type = 'system_maintenance' THEN 'system_maintenance'::job_category "
                   "ELSE 'command'::job_category END"
               ),
               existing_nullable=False,
               existing_server_default=False)
    op.create_index('ix_jobs_enabled', 'jobs', ['enabled'], unique=False)
    op.create_index('ix_jobs_schedule_type', 'jobs', ['schedule_type'], unique=False)
    op.create_foreign_key(op.f('fk_jobs_command_template_id_command_templates'), 'jobs', 'command_templates', ['command_template_id'], ['id'])


def downgrade() -> None:
    job_category_enum = postgresql.ENUM(
        'command',
        'meter_read',
        'connectivity_check',
        'system_maintenance',
        name='job_category',
    )
    job_target_type_enum = postgresql.ENUM(
        'meter',
        'endpoint',
        'system',
        name='job_target_type',
    )
    job_schedule_type_enum = postgresql.ENUM(
        'manual',
        'once',
        'cron',
        'interval',
        name='job_schedule_type',
    )
    job_run_status_enum = postgresql.ENUM(
        'pending',
        'claimed',
        'running',
        'succeeded',
        'failed',
        'cancelled',
        'timed_out',
        name='job_run_status',
    )
    op.drop_constraint(op.f('fk_jobs_command_template_id_command_templates'), 'jobs', type_='foreignkey')
    op.drop_index('ix_jobs_schedule_type', table_name='jobs')
    op.drop_index('ix_jobs_enabled', table_name='jobs')
    op.alter_column('jobs', 'job_type',
               existing_type=job_category_enum,
               type_=sa.VARCHAR(length=128),
               postgresql_using='job_type::text',
               existing_nullable=False)
    op.drop_column('jobs', 'notes')
    op.drop_column('jobs', 'max_retries')
    op.drop_column('jobs', 'timeout_seconds')
    op.drop_column('jobs', 'priority')
    op.drop_column('jobs', 'command_template_id')
    op.drop_column('jobs', 'interval_seconds')
    op.drop_column('jobs', 'schedule_type')
    op.drop_column('jobs', 'target_type')
    op.drop_constraint(op.f('fk_job_runs_target_endpoint_id_communication_endpoints'), 'job_runs', type_='foreignkey')
    op.drop_constraint(op.f('fk_job_runs_related_command_id_commands'), 'job_runs', type_='foreignkey')
    op.drop_constraint(op.f('fk_job_runs_target_meter_id_meters'), 'job_runs', type_='foreignkey')
    op.drop_index('ix_job_runs_worker_identifier', table_name='job_runs')
    op.drop_index('ix_job_runs_recent_history', table_name='job_runs')
    op.drop_index('ix_job_runs_claimable_lookup', table_name='job_runs')
    op.alter_column('job_runs', 'queued_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))
    op.execute("ALTER TABLE job_runs ALTER COLUMN status DROP DEFAULT")
    op.alter_column('job_runs', 'status',
               existing_type=job_run_status_enum,
               type_=postgresql.ENUM('draft', 'ready', 'running', 'succeeded', 'failed', 'paused', name='job_status'),
               postgresql_using=(
                   "CASE "
                   "WHEN status = 'pending' THEN 'ready'::job_status "
                   "WHEN status = 'claimed' THEN 'ready'::job_status "
                   "WHEN status = 'running' THEN 'running'::job_status "
                   "WHEN status = 'succeeded' THEN 'succeeded'::job_status "
                   "WHEN status = 'failed' THEN 'failed'::job_status "
                   "WHEN status = 'cancelled' THEN 'paused'::job_status "
                   "WHEN status = 'timed_out' THEN 'failed'::job_status "
                   "ELSE 'ready'::job_status END"
               ),
               existing_nullable=False,
               existing_server_default=sa.text("'ready'::job_status"))
    op.execute("ALTER TABLE job_runs ALTER COLUMN status SET DEFAULT 'ready'::job_status")
    op.drop_column('job_runs', 'latest_error_code')
    op.drop_column('job_runs', 'request_payload')
    op.drop_column('job_runs', 'max_retries')
    op.drop_column('job_runs', 'retry_count')
    op.drop_column('job_runs', 'cancelled_at')
    op.drop_column('job_runs', 'worker_identifier')
    op.drop_column('job_runs', 'claim_expires_at')
    op.drop_column('job_runs', 'claimed_at')
    op.drop_column('job_runs', 'available_at')
    op.drop_column('job_runs', 'scheduled_for')
    op.drop_column('job_runs', 'related_command_id')
    op.drop_column('job_runs', 'target_endpoint_id')
    op.drop_column('job_runs', 'target_meter_id')
    job_run_status_enum.drop(op.get_bind(), checkfirst=True)
    job_schedule_type_enum.drop(op.get_bind(), checkfirst=True)
    job_target_type_enum.drop(op.get_bind(), checkfirst=True)
    job_category_enum.drop(op.get_bind(), checkfirst=True)
