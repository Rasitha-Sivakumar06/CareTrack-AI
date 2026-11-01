#!/usr/bin/env python3
"""
CareTrack AI — User Provisioning Utility
Creates initial Clinician/Doctor and Administrator accounts securely.
Never uses default passwords and masks password input via getpass.
"""

import argparse
import getpass
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from app.models.user import User
from app.security import hash_password


def create_user(
    username: str,
    email: str,
    password: str,
    role: str = "doctor",
    full_name: str | None = None,
) -> None:
    if len(password) < 8:
        print("Error: Password must be at least 8 characters long.", file=sys.stderr)
        sys.exit(1)

    if role not in ("doctor", "admin"):
        print(f"Error: Invalid role '{role}'. Allowed roles are 'doctor' or 'admin'.", file=sys.stderr)
        sys.exit(1)

    username_clean = username.strip().lower()
    email_clean = email.strip().lower()

    db = SessionLocal()
    try:
        existing = db.query(User).filter(
            (User.username == username_clean) | (User.email == email_clean)
        ).first()

        if existing:
            print(f"Error: A user with username '{username_clean}' or email '{email_clean}' already exists.", file=sys.stderr)
            sys.exit(1)

        hashed = hash_password(password)

        new_user = User(
            username=username_clean,
            email=email_clean,
            hashed_password=hashed,
            full_name=full_name.strip() if full_name else None,
            role=role,
            is_active=True,
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        print("=" * 60)
        print("USER CREATED SUCCESSFULLY")
        print("=" * 60)
        print(f"ID:        {new_user.id}")
        print(f"Username:  {new_user.username}")
        print(f"Email:     {new_user.email}")
        print(f"Role:      {new_user.role}")
        print(f"Full Name: {new_user.full_name or '—'}")
        print("Status:    Active")
        print("=" * 60)
        print("Notice: Password has been securely hashed with bcrypt. Never share credentials.")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Create a CareTrack AI Doctor or Admin user.")
    parser.add_argument("--username", help="User login name")
    parser.add_argument("--email", help="User email address")
    parser.add_argument("--role", choices=["doctor", "admin"], default="doctor", help="User role (doctor or admin)")
    parser.add_argument("--name", help="Full name of user")

    args = parser.parse_args()

    username = args.username
    if not username:
        username = input("Enter username: ").strip()

    email = args.email
    if not email:
        email = input("Enter email: ").strip()

    role = args.role

    full_name = args.name
    if not full_name:
        full_name = input("Enter full name (optional): ").strip()

    # Read password without echoing to console
    password = getpass.getpass("Enter strong password (min 8 characters): ")
    password_confirm = getpass.getpass("Confirm password: ")

    if password != password_confirm:
        print("Error: Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    create_user(
        username=username,
        email=email,
        password=password,
        role=role,
        full_name=full_name or None,
    )


if __name__ == "__main__":
    main()
