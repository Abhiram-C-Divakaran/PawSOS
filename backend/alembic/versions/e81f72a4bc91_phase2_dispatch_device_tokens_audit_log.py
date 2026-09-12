"""phase2_dispatch_device_tokens_audit_log

Revision ID: e81f72a4bc91
Revises: da53ea883683
Create Date: 2026-09-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e81f72a4bc91'
down_revision: Union[str, None] = 'da53ea883683'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update rescue_assignments table with dispatch offer fields
    op.add_column('rescue_assignments', sa.Column('offered_at', sa.DateTime(), nullable=True))
    op.add_column('rescue_assignments', sa.Column('expires_at', sa.DateTime(), nullable=True))
    op.add_column('rescue_assignments', sa.Column('expired_at', sa.DateTime(), nullable=True))
    op.add_column('rescue_assignments', sa.Column('rejection_reason', sa.String(), nullable=True))

    # 2. Update users table with veterinary_facility_id
    op.add_column('users', sa.Column('veterinary_facility_id', sa.Uuid(), nullable=True))
    bind = op.get_bind()
    if bind and bind.dialect.name == 'sqlite':
        with op.batch_alter_table('users') as batch_op:
            batch_op.create_foreign_key(
                'fk_users_veterinary_facility_id',
                'veterinary_facilities',
                ['veterinary_facility_id'], ['id']
            )
    else:
        op.create_foreign_key(
            'fk_users_veterinary_facility_id',
            'users', 'veterinary_facilities',
            ['veterinary_facility_id'], ['id']
        )

    # 3. Update notifications table with data payload column
    op.add_column('notifications', sa.Column('data', sa.Text(), nullable=True))

    # 4. Create device_tokens table
    op.create_table(
        'device_tokens',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('platform', sa.String(), nullable=False, server_default='WEB'),
        sa.Column('device_name', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_device_tokens_user_id'), 'device_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_device_tokens_token'), 'device_tokens', ['token'], unique=False)

    # 5. Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('entity', sa.String(), nullable=False),
        sa.Column('entity_id', sa.Uuid(), nullable=True),
        sa.Column('old_value', sa.JSON(), nullable=True),
        sa.Column('new_value', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_actor_id'), 'audit_logs', ['actor_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity'), 'audit_logs', ['entity'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_id'), 'audit_logs', ['entity_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_logs_timestamp'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_entity_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_entity'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_actor_id'), table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_index(op.f('ix_device_tokens_token'), table_name='device_tokens')
    op.drop_index(op.f('ix_device_tokens_user_id'), table_name='device_tokens')
    op.drop_table('device_tokens')

    op.drop_column('notifications', 'data')

    bind = op.get_bind()
    if bind and bind.dialect.name != 'sqlite':
        op.drop_constraint('fk_users_veterinary_facility_id', 'users', type_='foreignkey')
    op.drop_column('users', 'veterinary_facility_id')

    op.drop_column('rescue_assignments', 'rejection_reason')
    op.drop_column('rescue_assignments', 'expired_at')
    op.drop_column('rescue_assignments', 'expires_at')
    op.drop_column('rescue_assignments', 'offered_at')
