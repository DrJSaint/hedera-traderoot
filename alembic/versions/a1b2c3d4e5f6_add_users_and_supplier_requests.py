"""add users and supplier_requests tables

Revision ID: a1b2c3d4e5f6
Revises: 00e4da965871
Create Date: 2026-05-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '00e4da965871'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'designer'")),
        sa.Column("designer_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.ForeignKeyConstraint(["designer_id"], ["designers.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "supplier_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("request_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("target_supplier_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_supplier_id"], ["suppliers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("requester_id", "target_supplier_id", name="uq_requests_requester_supplier"),
    )


def downgrade() -> None:
    op.drop_table("supplier_requests")
    op.drop_table("users")
