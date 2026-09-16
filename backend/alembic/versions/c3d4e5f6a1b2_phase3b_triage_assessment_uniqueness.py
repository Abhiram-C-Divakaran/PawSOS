"""phase3b_triage_assessment_uniqueness

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-09-17 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a1b2'
down_revision: Union[str, None] = 'b2c3d4e5f6a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'triage_assessments' in existing_tables:
        existing_constraints = [c['name'] for c in inspector.get_unique_constraints('triage_assessments')]
        if 'uq_triage_assessment_case_model' not in existing_constraints:
            with op.batch_alter_table('triage_assessments') as batch_op:
                batch_op.create_unique_constraint(
                    'uq_triage_assessment_case_model',
                    ['rescue_case_id', 'model_name', 'model_version']
                )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'triage_assessments' in existing_tables:
        existing_constraints = [c['name'] for c in inspector.get_unique_constraints('triage_assessments')]
        if 'uq_triage_assessment_case_model' in existing_constraints:
            with op.batch_alter_table('triage_assessments') as batch_op:
                batch_op.drop_constraint('uq_triage_assessment_case_model', type_='unique')
