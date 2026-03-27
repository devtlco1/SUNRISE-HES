"""expand meter manufacturer country column"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision = 'de970c68a2f4'
down_revision = 'dcba41ea4f5a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "meter_manufacturers",
        "country",
        existing_type=sa.String(length=8),
        type_=sa.String(length=128),
        postgresql_using="country::varchar(128)",
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "meter_manufacturers",
        "country",
        existing_type=sa.String(length=128),
        type_=sa.String(length=8),
        postgresql_using="LEFT(country, 8)",
        existing_nullable=True,
    )
