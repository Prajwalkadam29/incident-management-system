"""Fix signal_count column type: String(20) → Integer

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-05-05 00:01:00.000000

Context:
  Before Alembic was introduced, create_all() created signal_count
  as String(20). This migration corrects the type to Integer for any
  database that was created with the old create_all() approach.

  If you are running Alembic from a fresh database, revision 0001
  already creates signal_count as Integer — this migration will
  detect no change and complete instantly (it is idempotent).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a1"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cast existing string values to integer.
    # postgresql_using is required because PostgreSQL won't implicitly
    # cast VARCHAR → INTEGER without an explicit USING clause.
    op.alter_column(
        "work_items",
        "signal_count",
        existing_type=sa.String(20),
        type_=sa.Integer(),
        existing_nullable=True,
        nullable=False,
        server_default="0",
        # This USING clause handles the actual data cast in PostgreSQL.
        # We explicitly cast signal_count::text so that if it is ALREADY
        # an Integer (e.g. from fresh 0001 migration), it doesn't crash
        # when compared to the empty string ''.
        postgresql_using="COALESCE(NULLIF(signal_count::text, '')::integer, 0)",
    )


def downgrade() -> None:
    # Convert Integer back to String (reversible)
    op.alter_column(
        "work_items",
        "signal_count",
        existing_type=sa.Integer(),
        type_=sa.String(20),
        existing_nullable=False,
        nullable=True,
        server_default=None,
        postgresql_using="signal_count::varchar",
    )
