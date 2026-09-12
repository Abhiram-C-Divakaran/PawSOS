"""phase2_5_dispatch_refresh_indexes

Revision ID: f3a8b2c1d0e9
Revises: e81f72a4bc91
Create Date: 2026-09-12 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f3a8b2c1d0e9'
down_revision: Union[str, None] = 'e81f72a4bc91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Add dispatch state and organization columns to rescue_cases
    op.add_column('rescue_cases', sa.Column('organization_id', sa.Uuid(), nullable=True))
    op.add_column('rescue_cases', sa.Column('dispatch_attempt', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('rescue_cases', sa.Column('dispatch_radius_km', sa.Float(), nullable=False, server_default='5.0'))
    op.add_column('rescue_cases', sa.Column('last_dispatch_at', sa.DateTime(), nullable=True))
    bind = op.get_bind()
    if bind and bind.dialect.name == 'sqlite':
        with op.batch_alter_table('rescue_cases') as batch_op:
            batch_op.create_foreign_key(
                'fk_rescue_cases_organization_id',
                'organizations',
                ['organization_id'], ['id']
            )
    else:
        op.create_foreign_key(
            'fk_rescue_cases_organization_id',
            'rescue_cases', 'organizations',
            ['organization_id'], ['id']
        )

    # 2. Create refresh_sessions table for token revocation
    op.create_table(
        'refresh_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('device_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('replaced_by', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_sessions_user_id'), 'refresh_sessions', ['user_id'], unique=False)
    op.create_index(op.f('ix_refresh_sessions_token_hash'), 'refresh_sessions', ['token_hash'], unique=True)

    # 3. Add performance indexes for frequently queried fields
    op.create_index('ix_rescue_cases_organization_id', 'rescue_cases', ['organization_id'], unique=False)
    op.create_index('ix_rescue_cases_status_priority_created', 'rescue_cases', ['status', 'triage_priority', 'created_at'], unique=False)
    op.create_index('ix_rescue_cases_org_status', 'rescue_cases', ['organization_id', 'status'], unique=False)

    op.create_index('ix_rescue_assignments_case_status', 'rescue_assignments', ['rescue_case_id', 'assignment_status'], unique=False)
    op.create_index('ix_rescue_assignments_rescuer_status', 'rescue_assignments', ['rescuer_id', 'assignment_status'], unique=False)
    op.create_index('ix_rescue_assignments_expires_at', 'rescue_assignments', ['expires_at'], unique=False)

    op.create_index('ix_notifications_user_read', 'notifications', ['user_id', 'is_read'], unique=False)
    op.create_index('ix_device_tokens_user_active', 'device_tokens', ['user_id', 'is_active'], unique=False)

def downgrade() -> None:
    op.drop_index('ix_device_tokens_user_active', table_name='device_tokens')
    op.drop_index('ix_notifications_user_read', table_name='notifications')

    op.drop_index('ix_rescue_assignments_expires_at', table_name='rescue_assignments')
    op.drop_index('ix_rescue_assignments_rescuer_status', table_name='rescue_assignments')
    op.drop_index('ix_rescue_assignments_case_status', table_name='rescue_assignments')

    op.drop_index('ix_rescue_cases_org_status', table_name='rescue_cases')
    op.drop_index('ix_rescue_cases_status_priority_created', table_name='rescue_cases')
    op.drop_index('ix_rescue_cases_organization_id', table_name='rescue_cases')

    op.drop_index(op.f('ix_refresh_sessions_token_hash'), table_name='refresh_sessions')
    op.drop_index(op.f('ix_refresh_sessions_user_id'), table_name='refresh_sessions')
    op.drop_table('refresh_sessions')

    bind = op.get_bind()
    if bind and bind.dialect.name != 'sqlite':
        op.drop_constraint('fk_rescue_cases_organization_id', 'rescue_cases', type_='foreignkey')
    op.drop_column('rescue_cases', 'last_dispatch_at')
    op.drop_column('rescue_cases', 'dispatch_radius_km')
    op.drop_column('rescue_cases', 'dispatch_attempt')
    op.drop_column('rescue_cases', 'organization_id')
