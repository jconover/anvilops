"""add_port_entity_id_to_server_requests

Revision ID: a3f7c2d91e45
Revises: 528e7de10cd8
Create Date: 2026-03-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7c2d91e45'
down_revision: Union[str, None] = '528e7de10cd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('server_requests', sa.Column('port_entity_id', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('server_requests', 'port_entity_id')
