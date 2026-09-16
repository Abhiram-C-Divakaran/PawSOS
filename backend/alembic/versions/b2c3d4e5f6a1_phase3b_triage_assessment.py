"""phase3b_triage_assessment

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-09-16 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    is_sqlite = conn.dialect.name == 'sqlite'

    existing_tables = inspector.get_table_names()

    if 'triage_assessments' not in existing_tables:
        op.create_table(
            'triage_assessments',
            sa.Column('id', sa.Uuid(), primary_key=True, nullable=False),
            sa.Column('rescue_case_id', sa.Uuid(), sa.ForeignKey('rescue_cases.id', ondelete='CASCADE'), nullable=False),
            sa.Column('animal_image_id', sa.Uuid(), sa.ForeignKey('animal_images.id', ondelete='SET NULL'), nullable=True),
            sa.Column('source', sa.String(length=32), nullable=False, server_default='IMAGE_AI'),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='PENDING'),
            sa.Column('suggested_priority', sa.Enum('GENERAL', 'MODERATE', 'URGENT', 'CRITICAL', name='rescue_priority_enum', create_type=False), nullable=True),
            sa.Column('score', sa.Integer(), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=True),
            sa.Column('visible_signs', sa.Text(), nullable=True),
            sa.Column('reason_codes', sa.Text(), nullable=True),
            sa.Column('explanation', sa.Text(), nullable=True),
            sa.Column('provider', sa.String(length=64), nullable=False, server_default='disabled'),
            sa.Column('model_name', sa.String(length=128), nullable=False, server_default='pawreach-vision-safety'),
            sa.Column('model_version', sa.String(length=64), nullable=False, server_default='v1.0'),
            sa.Column('sanitized_error_code', sa.String(length=64), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
        )

        op.create_index('ix_triage_assessments_rescue_case_id', 'triage_assessments', ['rescue_case_id'])
        op.create_index('ix_triage_assessments_animal_image_id', 'triage_assessments', ['animal_image_id'])
        op.create_index('ix_triage_assessments_status', 'triage_assessments', ['status'])
        op.create_index('ix_triage_assessment_idempotency', 'triage_assessments', ['rescue_case_id', 'model_name', 'model_version'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'triage_assessments' in existing_tables:
        op.drop_table('triage_assessments')
