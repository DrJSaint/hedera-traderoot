"""
Reset a user's password directly in the database.
Usage:
    python scripts/reset_password.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth import hash_password
import app.db as db


def main():
    print("Reset user password")
    print("-------------------")
    email    = input("Email: ").strip()
    password = input("New password: ").strip()

    if not email or not password:
        print("Email and password are required.")
        sys.exit(1)

    user = db.get_user_by_email(email)
    if not user:
        print(f"No account found for {email}.")
        sys.exit(1)

    db.update_user_password(user["id"], hash_password(password))
    print(f"Password updated for {email} (id={user['id']}, role={user['role']}).")


if __name__ == "__main__":
    main()
