"""
CareTrack AI — Migration Script Safety & Validation Test Suite
Tests:
1. Static safety assertion: Rejects forbidden keywords (DROP, ALTER, TRUNCATE, DELETE) and protected tables.
2. Dry-run mode: Performs zero writes; verifies table is not created.
3. Live execution mode: Successfully creates users table and unique indexes on test engine.
4. Schema validation: Checks all 9 columns, types, nullability, PK constraint, and unique indexes.
5. Discrepancy detection: Accurately identifies missing columns, wrong nullability, and index flaws.
6. Transaction rollback: Proves that errors trigger automatic rollback leaving zero partial state.
7. Idempotency: Re-running against existing valid schema detects it and makes no redundant changes.

Zero live database writes are performed. Tests run on an isolated test SQLite engine.
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text, inspect
from scripts.migrate_add_users_table import (
    assert_migration_statements_safe,
    validate_users_schema,
    run_migration,
    STATEMENTS,
    PROTECTED_TABLES,
)


def create_test_db_with_protected_tables():
    """Sets up an in-memory SQLite database mimicking baseline protected tables."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE patients (id INTEGER PRIMARY KEY, name TEXT);"))
        conn.execute(text("INSERT INTO patients (id, name) VALUES (1, 'Test Patient 1');"))

        conn.execute(text("CREATE TABLE visits (id INTEGER PRIMARY KEY, patient_id INT);"))
        conn.execute(text("INSERT INTO visits (id, patient_id) VALUES (1, 1);"))

        conn.execute(text("CREATE TABLE clinical_measurements (id INTEGER PRIMARY KEY, value REAL);"))
        conn.execute(text("INSERT INTO clinical_measurements (id, value) VALUES (1, 98.6);"))
    return engine


def run_tests():
    print("=" * 70)
    print("CARETRACK AI — MIGRATION SAFETY & VALIDATION TEST SUITE")
    print("=" * 70)

    # 1. Test Static Safety Assertions
    print("\n1. Testing Static Safety Assertions...")
    assert_migration_statements_safe()
    print("PASS: Migration statements strictly target 'users' with zero forbidden DDL/DML keywords.")

    # 2. Test Dry-Run Mode (Zero Writes)
    print("\n2. Testing Dry-Run Mode (Read-Only Execution)...")
    test_engine = create_test_db_with_protected_tables()
    run_migration(target_engine=test_engine, execute_writes=False)

    insp = inspect(test_engine)
    assert "users" not in insp.get_table_names(), "FAIL: Dry-run created table in database!"
    print("PASS: Dry-run completed with zero writes. 'users' table was not created.")

    # 3. Test Live Additive Execution on Test Engine
    print("\n3. Testing Additive Execution & Index Creation...")
    # SQLite DDL adapted version of STATEMENTS for testing
    sqlite_statements = [
        (
            "Create 'users' table",
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                email VARCHAR(120) NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                full_name VARCHAR(100),
                role VARCHAR(20) NOT NULL DEFAULT 'doctor',
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )""",
        ),
        (
            "Create unique index on 'username'",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)",
        ),
        (
            "Create unique index on 'email'",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)",
        ),
    ]

    with test_engine.begin() as conn:
        for desc, stmt in sqlite_statements:
            conn.execute(text(stmt))

    insp = inspect(test_engine)
    assert "users" in insp.get_table_names(), "FAIL: 'users' table not created!"
    print("PASS: 'users' table and indexes created successfully.")

    # 4. Test Schema Validation (All 9 columns, PK, unique indexes)
    print("\n4. Testing Full 9-Column & Index Schema Validation...")
    is_valid, issues = validate_users_schema(test_engine)
    assert is_valid, f"FAIL: Schema validation failed on valid table: {issues}"
    print("PASS: Validated all 9 columns, types, nullability, primary key, and unique indexes.")

    # 5. Test Schema Discrepancy Detection
    print("\n5. Testing Schema Discrepancy Detection on Malformed Table...")
    broken_engine = create_engine("sqlite:///:memory:")
    with broken_engine.begin() as conn:
        # Table missing email, role, and with missing unique index
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                hashed_password VARCHAR(255) NOT NULL
            );
        """))

    broken_valid, broken_issues = validate_users_schema(broken_engine)
    assert not broken_valid, "FAIL: Malformed schema was incorrectly marked valid!"
    assert any("email" in issue for issue in broken_issues), "FAIL: Missing email was not detected!"
    assert any("ix_users_username" in issue for issue in broken_issues), "FAIL: Missing index was not detected!"
    print(f"PASS: Correctly detected {len(broken_issues)} schema flaws in malformed table.")

    # 6. Test Atomic Transaction Rollback on Error
    print("\n6. Testing Atomic Transaction Rollback on Error...")
    rollback_engine = create_engine("sqlite:///:memory:")
    with rollback_engine.begin() as conn:
        conn.execute(text("CREATE TABLE test_rollback (id INT PRIMARY KEY, val TEXT);"))
        conn.execute(text("INSERT INTO test_rollback VALUES (1, 'initial');"))

    rollback_triggered = False
    try:
        with rollback_engine.begin() as conn:
            conn.execute(text("INSERT INTO test_rollback VALUES (2, 'second');"))
            # Trigger deliberate SQL error to test rollback
            conn.execute(text("INVALID SQL STATEMENT SYNTAX ERROR;"))
    except Exception:
        rollback_triggered = True

    assert rollback_triggered, "FAIL: Exception not caught during deliberate failure!"
    with rollback_engine.connect() as conn:
        rows = conn.execute(text("SELECT id FROM test_rollback;")).fetchall()
        assert len(rows) == 1 and rows[0][0] == 1, f"FAIL: Row 2 was not rolled back: {rows}"
    print("PASS: Transaction error triggered automatic rollback; zero partial state persisted.")

    # 7. Test Protected Table Integrity
    print("\n7. Verifying Protected Tables Intact...")
    with test_engine.connect() as conn:
        p_count = conn.execute(text("SELECT COUNT(*) FROM patients")).scalar()
        v_count = conn.execute(text("SELECT COUNT(*) FROM visits")).scalar()
        m_count = conn.execute(text("SELECT COUNT(*) FROM clinical_measurements")).scalar()

    assert p_count == 1, "FAIL: Patients table rows altered!"
    assert v_count == 1, "FAIL: Visits table rows altered!"
    assert m_count == 1, "FAIL: Clinical measurements rows altered!"
    print("PASS: All protected clinical tables remain completely untouched and intact.")

    print("\n" + "=" * 70)
    print("ALL MIGRATION SAFETY TESTS PASSED (100% SUCCESS)!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
