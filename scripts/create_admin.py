"""
Create an admin user account.
Run once to seed the first admin, or to reset admin credentials.

Usage:
    python scripts/create_admin.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth import hash_password
import app.db as db


def main():
    print("Create admin account")
    print("--------------------")
    email    = input("Email: ").strip()
    password = input("Password: ").strip()

    if not email or not password:
        print("Email and password are required.")
        sys.exit(1)

    existing = db.get_user_by_email(email)
    if existing:
        if existing["role"] == "admin":
            print(f"Admin account already exists for {email}.")
        else:
            print(f"A designer account already exists for {email}. Cannot overwrite.")
        sys.exit(1)

    user_id = db.create_user(email, hash_password(password), role="admin")
    print(f"Admin account created (id={user_id}).")
    print("Set SECRET_KEY in your environment before running in production.")


if __name__ == "__main__":
    main()
