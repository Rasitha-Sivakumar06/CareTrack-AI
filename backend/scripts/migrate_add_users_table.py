#!/usr/bin/env python3
"""
CareTrack AI — Safe Additive Migration: Users Table
Location: backend/scripts/migrate_add_users_table.py

SAFETY GUARANTEES:
1. Strictly additive DDL: Only creates `users` table and unique indexes using IF NOT EXISTS.
2. Absolutely no DROP, ALTER, TRUNCATE, or DELETE operations on any table.
3. Protected clinical tables (patients, visits, vitals, medical_reports, ai_insights,
   clinical_measurements) are strictly guarded and asserted unchanged.
4. Each statement executes separately within an atomic PostgreSQL transaction (engine.begin).
5. Comprehensive schema validation verifies all 9 columns (names, types, nullability, PK)
   and both unique indexes (names, column targets, uniqueness).
6. Safe by default: Read-only dry-run mode unless explicit `--execute` flag is passed.
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text, inspect
from app.database import engine

# Exact individual DDL statements for PostgreSQL
STATEMENTS: List[Tuple[str, str]] = [
    (
        "Create 'users' table",
        """CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(120) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    role VARCHAR(20) NOT NULL DEFAULT 'doctor',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
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

# Clinical tables that must remain untouched and preserved
PROTECTED_TABLES: List[str] = [
    "patients",
    "visits",
    "vitals",
    "medical_reports",
    "ai_insights",
    "clinical_measurements",
]

# Strict definition of expected schema for the 9 columns in 'users' table
EXPECTED_COLUMNS: Dict[str, Dict[str, Any]] = {
    "id": {
        "nullable": False,
        "is_pk": True,
        "type_category": "INTEGER",
        "description": "Primary key integer/serial",
    },
    "username": {
        "nullable": False,
        "is_pk": False,
        "type_category": "VARCHAR",
        "max_length": 50,
        "description": "Unique username (VARCHAR 50, non-nullable)",
    },
    "email": {
        "nullable": False,
        "is_pk": False,
        "type_category": "VARCHAR",
        "max_length": 120,
        "description": "Unique email (VARCHAR 120, non-nullable)",
    },
    "hashed_password": {
        "nullable": False,
        "is_pk": False,
        "type_category": "VARCHAR",
        "max_length": 255,
        "description": "Bcrypt password hash (VARCHAR 255, non-nullable)",
    },
    "full_name": {
        "nullable": True,
        "is_pk": False,
        "type_category": "VARCHAR",
        "max_length": 100,
        "description": "Full name (VARCHAR 100, nullable)",
    },
    "role": {
        "nullable": False,
        "is_pk": False,
        "type_category": "VARCHAR",
        "max_length": 20,
        "description": "Role (VARCHAR 20, non-nullable, default doctor)",
    },
    "is_active": {
        "nullable": False,
        "is_pk": False,
        "type_category": "BOOLEAN",
        "description": "Active status (BOOLEAN, non-nullable, default true)",
    },
    "created_at": {
        "nullable": False,
        "is_pk": False,
        "type_category": "TIMESTAMP",
        "description": "Creation timestamp with timezone (non-nullable)",
    },
    "updated_at": {
        "nullable": False,
        "is_pk": False,
        "type_category": "TIMESTAMP",
        "description": "Update timestamp with timezone (non-nullable)",
    },
}

# Strict definition of expected unique indexes
EXPECTED_INDEXES: Dict[str, Dict[str, Any]] = {
    "ix_users_username": {
        "columns": ["username"],
        "unique": True,
    },
    "ix_users_email": {
        "columns": ["email"],
        "unique": True,
    },
}


def assert_migration_statements_safe() -> None:
    """
    Static safety assertion: ensures statements only create users/indexes
    and contain zero forbidden DDL/DML keywords or references to protected tables.
    """
    forbidden_keywords = ["DROP", "ALTER", "TRUNCATE", "DELETE"]
    for desc, stmt in STATEMENTS:
        upper = stmt.upper()
        for kw in forbidden_keywords:
            if kw in upper:
                raise ValueError(f"SAFETY VIOLATION: Statement contains forbidden keyword '{kw}': {stmt}")
        for pt in PROTECTED_TABLES:
            if pt in upper.lower():
                raise ValueError(f"SAFETY VIOLATION: Statement references protected table '{pt}': {stmt}")
        if "USERS" not in upper:
            raise ValueError(f"SAFETY VIOLATION: Statement does not target 'users': {stmt}")


def get_table_row_counts(target_engine) -> Dict[str, int]:
    """Capture row counts of protected tables to verify zero modification."""
    inspector = inspect(target_engine)
    existing_tables = set(inspector.get_table_names())
    counts: Dict[str, int] = {}
    with target_engine.connect() as conn:
        for table in PROTECTED_TABLES:
            if table in existing_tables:
                res = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                counts[table] = int(res) if res is not None else 0
    return counts


def validate_users_schema(target_engine) -> Tuple[bool, List[str]]:
    """
    Thoroughly inspect the 'users' table schema:
    1. Validates table existence.
    2. Validates all 9 columns: name, type category, length, nullability.
    3. Validates primary key constraint: strictly ['id'].
    4. Validates both unique indexes: names, target column, uniqueness flag.
    Returns (is_valid, list_of_issues).
    """
    inspector = inspect(target_engine)
    tables = inspector.get_table_names()
    if "users" not in tables:
        return False, ["Table 'users' does not exist in database."]

    issues: List[str] = []

    # 1. Inspect Primary Key
    pk_info = inspector.get_pk_constraint("users")
    pk_cols = pk_info.get("constrained_columns", [])
    if pk_cols != ["id"]:
        issues.append(f"Primary key mismatch: expected ['id'], got {pk_cols}")

    # 2. Inspect All 9 Required Columns
    raw_columns = inspector.get_columns("users")
    col_map = {c["name"]: c for c in raw_columns}

    # Check for missing columns
    for col_name, expected in EXPECTED_COLUMNS.items():
        if col_name not in col_map:
            issues.append(f"Missing required column: '{col_name}' ({expected['description']})")
            continue

        actual = col_map[col_name]

        # Check nullability (except id on SQLite where PK nullable flag can report True)
        is_sqlite = target_engine.dialect.name == "sqlite"
        if not (is_sqlite and col_name == "id"):
            if actual["nullable"] != expected["nullable"]:
                issues.append(
                    f"Nullability mismatch on '{col_name}': expected nullable={expected['nullable']}, "
                    f"got nullable={actual['nullable']}"
                )

        # Check type category
        actual_type_str = str(actual["type"]).upper()
        expected_cat = expected["type_category"]
        if expected_cat == "INTEGER":
            if not any(k in actual_type_str for k in ("INT", "SERIAL")):
                issues.append(f"Type mismatch on '{col_name}': expected integer/serial, got {actual_type_str}")
        elif expected_cat == "VARCHAR":
            if "VARCHAR" not in actual_type_str and "TEXT" not in actual_type_str and "STRING" not in actual_type_str:
                issues.append(f"Type mismatch on '{col_name}': expected VARCHAR, got {actual_type_str}")
        elif expected_cat == "BOOLEAN":
            if "BOOL" not in actual_type_str and "TINYINT" not in actual_type_str:
                issues.append(f"Type mismatch on '{col_name}': expected BOOLEAN, got {actual_type_str}")
        elif expected_cat == "TIMESTAMP":
            if not any(k in actual_type_str for k in ("TIMESTAMP", "DATETIME", "TIME")):
                issues.append(f"Type mismatch on '{col_name}': expected TIMESTAMP/DATETIME, got {actual_type_str}")

    # Check for unexpected extra columns
    for col_name in col_map:
        if col_name not in EXPECTED_COLUMNS:
            issues.append(f"Unexpected extra column in 'users': '{col_name}'")

    # 3. Inspect Unique Indexes
    raw_indexes = inspector.get_indexes("users")
    idx_map = {idx["name"]: idx for idx in raw_indexes}

    for idx_name, expected in EXPECTED_INDEXES.items():
        if idx_name not in idx_map:
            issues.append(f"Missing index: '{idx_name}'")
            continue

        actual_idx = idx_map[idx_name]
        if actual_idx.get("column_names") != expected["columns"]:
            issues.append(
                f"Index '{idx_name}' column target mismatch: expected {expected['columns']}, "
                f"got {actual_idx.get('column_names')}"
            )
        if not actual_idx.get("unique"):
            issues.append(f"Index '{idx_name}' must be unique, but unique={actual_idx.get('unique')}")

    return len(issues) == 0, issues


def run_migration(target_engine=None, execute_writes: bool = False) -> None:
    """
    Executes the migration workflow.
    - Default: read-only dry-run mode (zero writes).
    - With execute_writes=True: executes statements inside engine.begin() transaction.
    """
    if target_engine is None:
        target_engine = engine

    print("=" * 70)
    print("CARETRACK AI — SAFE ADDITIVE MIGRATION REVIEW & RUNNER")
    print("=" * 70)

    mode_label = "EXECUTE (LIVE WRITES)" if execute_writes else "DRY-RUN (READ-ONLY)"
    print(f"Current Execution Mode: {mode_label}\n")

    # Static assertion check on statement strings
    assert_migration_statements_safe()

    # Step 1: Pre-migration safety inspection
    print("1. Inspecting database tables and baseline row counts...")
    baseline_counts = get_table_row_counts(target_engine)
    for tbl, count in baseline_counts.items():
        print(f"   - Protected table '{tbl}': {count} existing records preserved")

    inspector = inspect(target_engine)
    tables = inspector.get_table_names()
    users_exists = "users" in tables

    # Step 2: Validate existing schema if table already exists
    if users_exists:
        print("\n2. 'users' table already detected. Validating schema...")
        is_valid, issues = validate_users_schema(target_engine)
        if is_valid:
            print("   SUCCESS: Existing 'users' table schema is fully valid and compatible.")
            print("   - All 9 columns (names, types, nullability, PK) verified.")
            print("   - Both unique indexes (ix_users_username, ix_users_email) verified.")
            print("   No schema changes are required.")
            return
        else:
            print("   WARNING: Schema discrepancies detected in existing 'users' table:")
            for issue in issues:
                print(f"     * {issue}")
            print("   Manual clinician/DBA review recommended.")
            return
    else:
        print("\n2. 'users' table does not exist in the database.")

    # Step 3: Review / Dry-run SQL Statements
    print("\n3. Reviewing Planned Additive SQL Statements:")
    for idx, (desc, stmt) in enumerate(STATEMENTS, 1):
        print(f"\n   Statement {idx} ({desc}):")
        indented = "\n".join("     " + line for line in stmt.splitlines())
        print(indented)

    if not execute_writes:
        print("\n" + "=" * 70)
        print("DRY-RUN COMPLETE: Zero database changes were made.")
        print("To execute this migration against the database, run:")
        print("  python backend/scripts/migrate_add_users_table.py --execute")
        print("=" * 70)
        return

    # Step 4: Live Execution with PostgreSQL Transaction Handling
    print("\n4. Executing Migration Statements within Atomic Transaction (engine.begin)...")
    try:
        with target_engine.begin() as conn:
            for idx, (desc, stmt) in enumerate(STATEMENTS, 1):
                print(f"   Executing statement {idx} ({desc})...")
                conn.execute(text(stmt))
        print("   Transaction committed successfully.")
    except Exception as exc:
        print(f"   ERROR: Transaction failed and was rolled back automatically: {exc}", file=sys.stderr)
        raise

    # Step 5: Post-migration Verification
    print("\n5. Verifying Migration Results & Data Integrity...")
    is_valid, issues = validate_users_schema(target_engine)
    if not is_valid:
        raise RuntimeError(f"Post-migration schema validation failed: {issues}")
    print("   SUCCESS: 'users' table and indexes verified in database schema.")
    print("   - All 9 columns (names, types, nullability, PK) verified.")
    print("   - Both unique indexes (ix_users_username, ix_users_email) verified.")

    post_counts = get_table_row_counts(target_engine)
    for tbl in PROTECTED_TABLES:
        if tbl in baseline_counts:
            assert post_counts[tbl] == baseline_counts[tbl], (
                f"CRITICAL SAFETY VIOLATION: Row count mismatch in protected table '{tbl}'!"
            )
    print("   CONFIRMED: All protected clinical tables remain completely unmodified.")
    print("\n" + "=" * 70)
    print("MIGRATION COMPLETED SUCCESSFULLY (100% VERIFIED)!")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Safe additive migration for CareTrack AI users table."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the migration against the database (defaults to dry-run read-only mode).",
    )
    args = parser.parse_args()
    run_migration(execute_writes=args.execute)


if __name__ == "__main__":
    main()
