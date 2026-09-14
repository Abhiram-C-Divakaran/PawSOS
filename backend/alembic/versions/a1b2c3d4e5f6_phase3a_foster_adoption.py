"""phase3a_foster_adoption

Revision ID: a1b2c3d4e5f6
Revises: f4b9c8d7e6f5
Create Date: 2026-09-15 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f4b9c8d7e6f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    is_sqlite = conn.dialect.name == 'sqlite'

    existing_tables = inspector.get_table_names()

    # 1. Update foster_homes with organization, locality, verification fields and check constraints
    if 'foster_homes' in existing_tables:
        existing_cols = [c['name'] for c in inspector.get_columns('foster_homes')]
        if 'organization_id' not in existing_cols:
            op.add_column('foster_homes', sa.Column('organization_id', sa.Uuid(), nullable=True))
        if 'locality' not in existing_cols:
            op.add_column('foster_homes', sa.Column('locality', sa.String(), nullable=True))
        if 'verified_at' not in existing_cols:
            op.add_column('foster_homes', sa.Column('verified_at', sa.DateTime(), nullable=True))
        if 'verified_by_user_id' not in existing_cols:
            op.add_column('foster_homes', sa.Column('verified_by_user_id', sa.Uuid(), nullable=True))

        existing_indexes = [ix['name'] for ix in inspector.get_indexes('foster_homes')]
        if 'ix_foster_homes_organization_id' not in existing_indexes:
            op.create_index('ix_foster_homes_organization_id', 'foster_homes', ['organization_id'])

        if not is_sqlite:
            op.create_foreign_key('fk_foster_homes_organization_id', 'foster_homes', 'organizations', ['organization_id'], ['id'])
            op.create_foreign_key('fk_foster_homes_verified_by_user_id', 'foster_homes', 'users', ['verified_by_user_id'], ['id'])
            op.create_check_constraint('check_foster_capacity_positive', 'foster_homes', 'capacity >= 1')
            op.create_check_constraint('check_foster_occupancy_non_negative', 'foster_homes', 'current_occupancy >= 0')
            op.create_check_constraint('check_foster_occupancy_within_capacity', 'foster_homes', 'current_occupancy <= capacity')

    # 2. Update foster_assignments with created_at
    if 'foster_assignments' in existing_tables:
        fa_cols = [c['name'] for c in inspector.get_columns('foster_assignments')]
        if 'created_at' not in fa_cols:
            op.add_column('foster_assignments', sa.Column('created_at', sa.DateTime(), nullable=True))

    # 3. Create foster_care_updates table
    if 'foster_care_updates' not in existing_tables:
        op.create_table(
            'foster_care_updates',
            sa.Column('id', sa.Uuid(), primary_key=True, nullable=False),
            sa.Column('assignment_id', sa.Uuid(), sa.ForeignKey('foster_assignments.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('general_notes', sa.Text(), nullable=True),
            sa.Column('appetite_status', sa.String(), nullable=True),
            sa.Column('activity_status', sa.String(), nullable=True),
            sa.Column('weight_kg', sa.Float(), nullable=True),
            sa.Column('medication_administered', sa.Text(), nullable=True),
            sa.Column('concern_flag', sa.Boolean(), default=False, nullable=False),
            sa.Column('readiness_recommendation', sa.String(), nullable=True),
        )
        op.create_index('ix_foster_care_updates_assignment_id', 'foster_care_updates', ['assignment_id'])

    # 4. Create adoption_listings table
    if 'adoption_listings' not in existing_tables:
        op.create_table(
            'adoption_listings',
            sa.Column('id', sa.Uuid(), primary_key=True, nullable=False),
            sa.Column('animal_id', sa.Uuid(), sa.ForeignKey('animals.id'), nullable=False),
            sa.Column('rescue_case_id', sa.Uuid(), sa.ForeignKey('rescue_cases.id'), nullable=False),
            sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id'), nullable=False),
            sa.Column('title', sa.String(), nullable=False),
            sa.Column('public_description', sa.Text(), nullable=False),
            sa.Column('public_image_url', sa.String(), nullable=True),
            sa.Column('status', sa.String(), default='DRAFT', nullable=False),
            sa.Column('published_at', sa.DateTime(), nullable=True),
            sa.Column('closed_at', sa.DateTime(), nullable=True),
            sa.Column('created_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_adoption_listings_animal_id', 'adoption_listings', ['animal_id'])
        op.create_index('ix_adoption_listings_rescue_case_id', 'adoption_listings', ['rescue_case_id'])
        op.create_index('ix_adoption_listings_organization_id', 'adoption_listings', ['organization_id'])
        op.create_index('ix_adoption_listings_status', 'adoption_listings', ['status'])

    # 5. Create adoption_applications table
    if 'adoption_applications' not in existing_tables:
        op.create_table(
            'adoption_applications',
            sa.Column('id', sa.Uuid(), primary_key=True, nullable=False),
            sa.Column('listing_id', sa.Uuid(), sa.ForeignKey('adoption_listings.id', ondelete='CASCADE'), nullable=False),
            sa.Column('applicant_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('status', sa.String(), default='SUBMITTED', nullable=False),
            sa.Column('housing_type', sa.String(), nullable=True),
            sa.Column('owns_or_rents', sa.String(), nullable=True),
            sa.Column('landlord_permission', sa.Boolean(), nullable=True),
            sa.Column('household_size', sa.Integer(), nullable=True),
            sa.Column('children_in_household', sa.Boolean(), nullable=True),
            sa.Column('existing_pets', sa.Text(), nullable=True),
            sa.Column('animal_experience', sa.Text(), nullable=True),
            sa.Column('reason_for_adoption', sa.Text(), nullable=False),
            sa.Column('care_plan', sa.Text(), nullable=True),
            sa.Column('submitted_at', sa.DateTime(), nullable=False),
            sa.Column('reviewed_at', sa.DateTime(), nullable=True),
            sa.Column('reviewed_by_user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('decision_notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_adoption_applications_listing_id', 'adoption_applications', ['listing_id'])
        op.create_index('ix_adoption_applications_applicant_id', 'adoption_applications', ['applicant_id'])
        op.create_index('ix_adoption_applications_status', 'adoption_applications', ['status'])

    # 6. Create adoption_visits table
    if 'adoption_visits' not in existing_tables:
        op.create_table(
            'adoption_visits',
            sa.Column('id', sa.Uuid(), primary_key=True, nullable=False),
            sa.Column('application_id', sa.Uuid(), sa.ForeignKey('adoption_applications.id', ondelete='CASCADE'), nullable=False),
            sa.Column('scheduled_at', sa.DateTime(), nullable=False),
            sa.Column('status', sa.String(), default='SCHEDULED', nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_adoption_visits_application_id', 'adoption_visits', ['application_id'])
        op.create_index('ix_adoption_visits_status', 'adoption_visits', ['status'])


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind and bind.dialect.name == 'sqlite'

    op.drop_table('adoption_visits')
    op.drop_table('adoption_applications')
    op.drop_table('adoption_listings')
    op.drop_table('foster_care_updates')

    op.drop_column('foster_assignments', 'created_at')

    if not is_sqlite:
        op.drop_constraint('check_foster_occupancy_within_capacity', 'foster_homes', type_='check')
        op.drop_constraint('check_foster_occupancy_non_negative', 'foster_homes', type_='check')
        op.drop_constraint('check_foster_capacity_positive', 'foster_homes', type_='check')
        op.drop_constraint('fk_foster_homes_verified_by_user_id', 'foster_homes', type_='foreignkey')
        op.drop_constraint('fk_foster_homes_organization_id', 'foster_homes', type_='foreignkey')

    op.drop_index('ix_foster_homes_organization_id', table_name='foster_homes')
    op.drop_column('foster_homes', 'verified_by_user_id')
    op.drop_column('foster_homes', 'verified_at')
    op.drop_column('foster_homes', 'locality')
    op.drop_column('foster_homes', 'organization_id')
