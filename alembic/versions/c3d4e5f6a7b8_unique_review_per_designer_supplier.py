"""unique review per designer per supplier

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-12 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove duplicate reviews, keeping the most recent per (supplier_id, designer_id)
    op.execute("""
        DELETE FROM reviews
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM reviews
            GROUP BY supplier_id, designer_id
        )
    """)

    with op.batch_alter_table("reviews") as batch_op:
        batch_op.create_unique_constraint(
            "uq_reviews_supplier_designer", ["supplier_id", "designer_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("reviews") as batch_op:
        batch_op.drop_constraint("uq_reviews_supplier_designer", type_="unique")
