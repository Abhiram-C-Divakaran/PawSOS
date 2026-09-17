"""Regression tests for Alembic database migrations.
Validates that Phase 3B correctly reuses existing PostgreSQL named enums
without attempting to recreate them, preventing DuplicateObject errors
on previously-migrated staging databases.
"""
import os
import pytest
from unittest.mock import MagicMock
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"
PHASE_3B_MIGRATION = MIGRATIONS_DIR / "b2c3d4e5f6a1_phase3b_triage_assessment.py"
PHASE_3B_UNIQUENESS_MIGRATION = MIGRATIONS_DIR / "c3d4e5f6a1b2_phase3b_triage_assessment_uniqueness.py"


def test_phase3b_migration_uses_postgresql_enum_with_create_type_false():
    """Verify that b2c3d4e5f6a1 explicitly uses postgresql.ENUM with create_type=False
    when executing on PostgreSQL to prevent DuplicateObject errors.
    """
    assert PHASE_3B_MIGRATION.exists(), f"Migration file not found at {PHASE_3B_MIGRATION}"
    with open(PHASE_3B_MIGRATION, "r", encoding="utf-8") as f:
        content = f.read()

    assert "from sqlalchemy.dialects import postgresql" in content, (
        "b2c3d4e5f6a1 must import postgresql dialect"
    )
    assert "postgresql.ENUM" in content, (
        "b2c3d4e5f6a1 must use postgresql.ENUM for PostgreSQL dialect"
    )
    assert "create_type=False" in content, (
        "b2c3d4e5f6a1 must specify create_type=False to reuse existing rescue_priority_enum"
    )
    assert "rescue_priority_enum" in content, (
        "b2c3d4e5f6a1 must reference rescue_priority_enum"
    )
    # Ensure no destructive drop of the shared enum
    assert "DROP TYPE" not in content, (
        "b2c3d4e5f6a1 must not drop rescue_priority_enum"
    )


def test_postgresql_enum_suppresses_create_type_ddl_on_table_creation():
    """Demonstrate dialect behavior:
    - Generic sa.Enum emits EnumGenerator._on_table_create (causing DuplicateObject on existing DB).
    - Dialect-specific postgresql.ENUM(create_type=False) cleanly suppresses DDL emission.
    """
    pg_dialect = postgresql.dialect()
    mock_conn = MagicMock()
    mock_conn.dialect = pg_dialect

    # 1. Defective pattern: generic sa.Enum
    m_buggy = sa.MetaData()
    t_buggy = sa.Table(
        "triage_assessments_buggy",
        m_buggy,
        sa.Column(
            "suggested_priority",
            sa.Enum("GENERAL", "MODERATE", "URGENT", "CRITICAL", name="rescue_priority_enum", create_type=False),
        ),
    )
    mock_conn.reset_mock()
    t_buggy.dispatch.before_create(t_buggy, mock_conn)
    # Generic sa.Enum delegates to dialect_impl which defaults create_type=True and dispatches DDL
    buggy_calls = [
        call for call in mock_conn.mock_calls
        if "EnumGenerator" in str(call) or "_run_ddl_visitor" in str(call)
    ]
    assert len(buggy_calls) > 0, "Generic sa.Enum should trigger DDL visitor on PostgreSQL"

    # 2. Fixed pattern: postgresql.ENUM(create_type=False)
    m_fixed = sa.MetaData()
    t_fixed = sa.Table(
        "triage_assessments_fixed",
        m_fixed,
        sa.Column(
            "suggested_priority",
            postgresql.ENUM("GENERAL", "MODERATE", "URGENT", "CRITICAL", name="rescue_priority_enum", create_type=False),
        ),
    )
    mock_conn.reset_mock()
    t_fixed.dispatch.before_create(t_fixed, mock_conn)
    # postgresql.ENUM with create_type=False must emit ZERO DDL visitor calls
    fixed_calls = [
        call for call in mock_conn.mock_calls
        if "EnumGenerator" in str(call) or "_run_ddl_visitor" in str(call)
    ]
    assert len(fixed_calls) == 0, (
        f"postgresql.ENUM(create_type=False) must not emit DDL visitor calls, but emitted: {fixed_calls}"
    )


def test_phase3b_uniqueness_migration_structure():
    """Verify that c3d4e5f6a1b2 correctly chains from b2c3d4e5f6a1 and defines uniqueness constraint."""
    assert PHASE_3B_UNIQUENESS_MIGRATION.exists(), (
        f"Uniqueness migration not found at {PHASE_3B_UNIQUENESS_MIGRATION}"
    )
    with open(PHASE_3B_UNIQUENESS_MIGRATION, "r", encoding="utf-8") as f:
        content = f.read()

    assert "down_revision: Union[str, None] = 'b2c3d4e5f6a1'" in content, (
        "c3d4e5f6a1b2 must revise b2c3d4e5f6a1"
    )
    assert "uq_triage_assessment_case_model" in content, (
        "c3d4e5f6a1b2 must manage uq_triage_assessment_case_model"
    )
    assert "DROP TYPE" not in content, (
        "c3d4e5f6a1b2 must not drop shared types"
    )


@pytest.mark.skipif(
    not os.environ.get("POSTGRES_TEST_URL") and not (
        os.environ.get("DATABASE_URL", "").startswith("postgresql")
    ),
    reason="Live PostgreSQL regression test requires active PostgreSQL instance",
)
def test_postgres_live_incremental_migration_phase3a_to_head():
    """Live PostgreSQL integration test:
    Simulates Render deployment against an existing database previously migrated to Phase 3A.
    Steps:
    1. Upgrade to a1b2c3d4e5f6 (Phase 3A).
    2. Confirm rescue_priority_enum exists and is referenced by rescue_cases.
    3. Run upgrade head in a separate Alembic command.
    4. Confirm no DuplicateObject error, current == head, and shared enum is reused.
    """
    from alembic.config import Config
    from alembic import command

    db_url = os.environ.get("POSTGRES_TEST_URL") or os.environ.get("DATABASE_URL")
    alembic_ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"

    cfg = Config(str(alembic_ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)

    engine = sa.create_engine(db_url)

    try:
        # Step A: Upgrade to Phase 3A
        command.upgrade(cfg, "a1b2c3d4e5f6")

        with engine.connect() as conn:
            # Check rescue_priority_enum exists
            result = conn.execute(
                sa.text("SELECT typname FROM pg_type WHERE typname = 'rescue_priority_enum'")
            ).scalar()
            assert result == "rescue_priority_enum"

            # Check rescue_cases.triage_priority uses rescue_priority_enum
            col_udt = conn.execute(
                sa.text(
                    "SELECT udt_name FROM information_schema.columns "
                    "WHERE table_name = 'rescue_cases' AND column_name = 'triage_priority'"
                )
            ).scalar()
            assert col_udt == "rescue_priority_enum"

        # Step B: Upgrade to head in independent command
        command.upgrade(cfg, "head")

        with engine.connect() as conn:
            # Check enum labels are exactly GENERAL, MODERATE, URGENT, CRITICAL
            labels = conn.execute(
                sa.text(
                    "SELECT enumlabel FROM pg_enum "
                    "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
                    "WHERE pg_type.typname = 'rescue_priority_enum' "
                    "ORDER BY enumsortorder"
                )
            ).scalars().all()
            assert list(labels) == ["GENERAL", "MODERATE", "URGENT", "CRITICAL"]

            # Check triage_assessments.suggested_priority also references rescue_priority_enum
            assess_udt = conn.execute(
                sa.text(
                    "SELECT udt_name FROM information_schema.columns "
                    "WHERE table_name = 'triage_assessments' AND column_name = 'suggested_priority'"
                )
            ).scalar()
            assert assess_udt == "rescue_priority_enum"

            # Check unique constraint exists on triage_assessments
            uq = conn.execute(
                sa.text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conname = 'uq_triage_assessment_case_model'"
                )
            ).scalar()
            assert uq == "uq_triage_assessment_case_model"

    finally:
        engine.dispose()
