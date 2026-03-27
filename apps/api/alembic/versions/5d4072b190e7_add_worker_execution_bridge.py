"""add worker execution bridge"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision = '5d4072b190e7'
down_revision = '97a05a75ac97'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE command_execution_attempt_status ADD VALUE IF NOT EXISTS 'running'")
    op.add_column('command_execution_attempts', sa.Column('job_run_id', sa.Uuid(), nullable=True))
    op.create_index('ix_command_execution_attempts_active_command', 'command_execution_attempts', ['meter_command_id', 'ended_at'], unique=False)
    op.create_index('ix_command_execution_attempts_job_run_id', 'command_execution_attempts', ['job_run_id'], unique=False)
    op.create_index('ix_command_execution_attempts_worker_status', 'command_execution_attempts', ['worker_identifier', 'status', 'ended_at'], unique=False)
    op.create_foreign_key(op.f('fk_command_execution_attempts_job_run_id_job_runs'), 'command_execution_attempts', 'job_runs', ['job_run_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(op.f('fk_command_execution_attempts_job_run_id_job_runs'), 'command_execution_attempts', type_='foreignkey')
    op.drop_index('ix_command_execution_attempts_worker_status', table_name='command_execution_attempts')
    op.drop_index('ix_command_execution_attempts_job_run_id', table_name='command_execution_attempts')
    op.drop_index('ix_command_execution_attempts_active_command', table_name='command_execution_attempts')
    op.drop_column('command_execution_attempts', 'job_run_id')
