"""phase2_6_org_fields_user_preferences

Revision ID: f4b9c8d7e6f5
Revises: f3a8b2c1d0e9
Create Date: 2026-09-13 00:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f4b9c8d7e6f5'
down_revision: Union[str, None] = 'f3a8b2c1d0e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Add operating_region and description to organizations
    op.add_column('organizations', sa.Column('operating_region', sa.String(), nullable=True))
    op.add_column('organizations', sa.Column('description', sa.String(), nullable=True))

    # 2. Add notification_preferences to users
    op.add_column('users', sa.Column('notification_preferences', sa.JSON(), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'notification_preferences')
    op.drop_column('organizations', 'description')
    op.drop_column('organizations', 'operating_region')
