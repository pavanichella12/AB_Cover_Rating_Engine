#!/usr/bin/env python3
"""
Create a new user for ABCover login.
Run: python3 add_user.py
Or: python3 add_user.py "user@company.com" "their_password" "Display Name"
"""
import sys
import getpass
from auth import init_db, create_user

def main():
    init_db()
    if len(sys.argv) >= 3:
        email = sys.argv[1].strip()
        password = sys.argv[2]
        name = sys.argv[3].strip() if len(sys.argv) > 3 else ""
    else:
        email = input("Email: ").strip()
        password = getpass.getpass("Password: ")
        name = input("Display name (optional): ").strip()
    if not email or not password:
        print("Email and password are required.")
        sys.exit(1)
    if not email.lower().endswith("@abcover.org"):
        print("Only @abcover.org email addresses are allowed.")
        sys.exit(1)
    if create_user(email, password, name):
        print(f"User created: {email}")
    else:
        print(f"User already exists: {email}")
        sys.exit(1)

if __name__ == "__main__":
    main()
