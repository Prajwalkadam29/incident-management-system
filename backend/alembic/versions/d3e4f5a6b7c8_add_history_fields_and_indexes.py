"""Add history fields and indexes

Revision ID: d3e4f5a6b7c8
Revises: c295d92760f9
Create Date: 2026-05-06 19:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c295d92760f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new history / RCA columns
    op.add_column('work_items', sa.Column('closed_by', sa.String(length=255), nullable=True))
    op.add_column('work_items', sa.Column('rca_submitted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('work_items', sa.Column('archived_reason', sa.Text(), nullable=True))
    
    # Create single-column indexes for query optimization in history
    op.create_index('ix_work_items_status', 'work_items', ['status'], unique=False)
    op.create_index('ix_work_items_closed_at', 'work_items', ['closed_at'], unique=False)
    op.create_index('ix_work_items_severity', 'work_items', ['severity'], unique=False)


def downgrade() -> None:
    # Drop single-column indexes
    op.drop_index('ix_work_items_severity', table_name='work_items')
    op.drop_index('ix_work_items_closed_at', table_name='work_items')
    op.drop_index('ix_work_items_status', table_name='work_items')
    
    # Drop history columns
    op.drop_column('work_items', 'archived_reason')
    op.drop_column('work_items', 'rca_submitted_at')
    op.drop_column('work_items', 'closed_by')
