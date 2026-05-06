"""Initial schema — work_items, rca_records, incident_events

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-05-05 00:00:00.000000

Creates the full IMS schema from scratch.
This is the authoritative schema definition — not create_all().
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── work_items ────────────────────────────────────────────────────
    op.create_table(
        "work_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("component_id", sa.String(255), nullable=False),
        sa.Column(
            "component_type",
            sa.Enum("RDBMS", "API", "CACHE", "QUEUE", "NOSQL", "MCP_HOST",
                    name="componenttype"),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum("P0", "P1", "P2", "P3", name="severity"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("OPEN", "INVESTIGATING", "RESOLVED", "CLOSED",
                    name="workitemstatus"),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        # Metrics
        sa.Column("mttr_minutes", sa.Float, nullable=True),
        # Integer from day 1 — correct type from the start
        sa.Column("signal_count", sa.Integer, nullable=False, server_default="0"),
    )

    # Indexes on work_items
    op.create_index("ix_work_items_component_id", "work_items", ["component_id"])
    op.create_index("ix_work_items_status_severity", "work_items",
                    ["status", "severity"])
    op.create_index("ix_work_items_component_status", "work_items",
                    ["component_id", "status"])

    # ── rca_records ───────────────────────────────────────────────────
    op.create_table(
        "rca_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "work_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("work_items.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        # Mandatory RCA fields
        sa.Column("incident_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("incident_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "root_cause_category",
            sa.Enum("INFRASTRUCTURE", "APPLICATION", "NETWORK",
                    "DEPENDENCY", "HUMAN_ERROR", "UNKNOWN",
                    name="rootcausecategory"),
            nullable=False,
        ),
        sa.Column("fix_applied", sa.Text, nullable=False),
        sa.Column("prevention_steps", sa.Text, nullable=False),
        # Optional enrichment
        sa.Column("affected_users_count", sa.String(50), nullable=True),
        sa.Column("timeline_notes", sa.Text, nullable=True),
        # Meta
        sa.Column("submitted_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )

    # ── incident_events ───────────────────────────────────────────────
    op.create_table(
        "incident_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "work_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("work_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.Enum(
                "INCIDENT_CREATED", "STATUS_CHANGED", "SIGNAL_RECEIVED",
                "RCA_SUBMITTED", "INCIDENT_CLOSED", "ALERT_FIRED",
                "CORRELATION_LINKED", "COMMENT_ADDED",
                name="eventtype",
            ),
            nullable=False,
        ),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("actor", sa.String(255), nullable=True),
        sa.Column("event_metadata", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    # Indexes on incident_events
    op.create_index("ix_incident_events_work_item_id", "incident_events",
                    ["work_item_id"])
    op.create_index("ix_incident_events_work_item_created", "incident_events",
                    ["work_item_id", "created_at"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("incident_events")
    op.drop_table("rca_records")
    op.drop_table("work_items")

    # Drop PostgreSQL enum types
    op.execute("DROP TYPE IF EXISTS eventtype")
    op.execute("DROP TYPE IF EXISTS rootcausecategory")
    op.execute("DROP TYPE IF EXISTS workitemstatus")
    op.execute("DROP TYPE IF EXISTS severity")
    op.execute("DROP TYPE IF EXISTS componenttype")
