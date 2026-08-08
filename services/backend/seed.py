"""
Digital Campus - Database Seed Script
Creates the superadmin account ONLY when it does not exist. Never resets
existing credentials. Run: cd services/backend && .venv/bin/python seed.py

Credentials come from the environment:
  SUPERADMIN_EMAIL      (default: admin@campus.edu)
  SUPERADMIN_PASSWORD   (default: none — a random password is generated and
                         printed once if the account is created)
"""
import os
import secrets

from app.core.database import SessionLocal, init_db
from app.core.security import get_password_hash
from app.models import User

# Ensure tables exist
init_db()

db = SessionLocal()

admin_email = os.environ.get("SUPERADMIN_EMAIL", "admin@campus.edu").strip().lower()
admin_password = os.environ.get("SUPERADMIN_PASSWORD", "").strip()

existing = db.query(User).filter(User.email == admin_email).first()
if existing:
    if not existing.is_admin:
        existing.is_admin = True
        db.commit()
        print(f"✅ Promoted existing account to superadmin: {admin_email}")
    else:
        print(f"ℹ️  Superadmin already exists: {admin_email} (credentials unchanged)")
else:
    if not admin_password:
        admin_password = secrets.token_urlsafe(12)
        print("⚠️  No SUPERADMIN_PASSWORD set — a random password was generated.")
    admin = User(
        email=admin_email,
        full_name="Superadmin",
        hashed_password=get_password_hash(admin_password),
        is_admin=True,
    )
    db.add(admin)
    db.commit()
    print(f"✅ Superadmin created: {admin_email}")

db.close()

if admin_password:
    print(f"\n🔐 Login credentials:")
    print(f"   Email: {admin_email}")
    print(f"   Password: {admin_password}")
print(f"\n⚠️  Change the password after first login via the Superadmin Dashboard.")
