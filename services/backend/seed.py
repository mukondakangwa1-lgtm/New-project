"""
Digital Campus - Database Seed Script
Creates ONLY the superadmin account. No demo data.
Run: cd services/backend && .venv/bin/python seed.py
"""
from datetime import date, time, timedelta

from app.core.database import SessionLocal, init_db
from app.core.security import get_password_hash
from app.models import User

# Ensure tables exist
init_db()

db = SessionLocal()

# --- Create superadmin ONLY ---
admin_email = "admin@campus.edu"
admin_password = "superadmin123"

existing = db.query(User).filter(User.email == admin_email).first()
if existing:
    # Update password if superadmin exists
    existing.hashed_password = get_password_hash(admin_password)
    existing.is_admin = True
    existing.full_name = "Superadmin"
    db.commit()
    print(f"✅ Superadmin updated: {admin_email}")
else:
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
print(f"\n🔐 Login credentials:")
print(f"   Email: {admin_email}")
print(f"   Password: {admin_password}")
print(f"\n⚠️  Change password immediately via the Superadmin Dashboard chat:")
print(f"   'change password [new_password]'")
