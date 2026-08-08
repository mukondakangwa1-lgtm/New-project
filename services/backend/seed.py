"""
Digital Campus - Database Seed Script
Creates superadmin + demo courses (so frontend not empty).
Works with BOTH PostgreSQL and SQLite (via DATABASE_URL).
Run: cd services/backend && .venv/bin/python seed.py
     or  python scripts/init_db.py --seed  (same)
"""
from datetime import date, time
from app.core.database import SessionLocal, init_db
from app.core.security import get_password_hash
from app.models import User, Course
from app.models_extended import Assignment, StudyGoal

init_db()
db = SessionLocal()

# --- Superadmin ---
admin_email = "admin@campus.edu"
admin_password = "superadmin123"
existing = db.query(User).filter(User.email == admin_email).first()
if existing:
    existing.hashed_password = get_password_hash(admin_password)
    existing.is_admin = True
    existing.full_name = "Superadmin"
    db.commit()
    admin = existing
    print(f"✅ Superadmin updated: {admin_email}")
else:
    admin = User(email=admin_email, full_name="Superadmin", hashed_password=get_password_hash(admin_password), is_admin=True)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print(f"✅ Superadmin created: {admin_email}")

# --- Demo Courses (only if empty) ---
if db.query(Course).count() == 0:
    demos = [
        Course(title="Introduction to Computer Science", code="CS101", description="Fundamentals of programming, algorithms, and data structures. SQLite + PostgreSQL hands-on.", instructor="Dr. Ada Lovelace", credits=3),
        Course(title="Data Structures & Algorithms", code="CS201", description="Lists, trees, graphs, sorting - with pgvector for semantic search.", instructor="Prof. Alan Turing", credits=4),
        Course(title="Web Development", code="CS301", description="FastAPI + Next.js + MinIO S3. Build full-stack Digital Campus.", instructor="Dr. Grace Hopper", credits=3),
        Course(title="Database Systems", code="CS302", description="PostgreSQL vs SQLite - hybrid storage, transactions, indexing.", instructor="Dr. Edgar Codd", credits=3),
        Course(title="Machine Learning", code="CS401", description="Embeddings, vectors, KUDOS AI, LLM integration.", instructor="Prof. Andrew Ng", credits=4),
        Course(title="Cloud Storage & Security", code="CS303", description="MinIO, R2, B2 - free secure object storage, AES256, presigned URLs.", instructor="Dr. Whitfield Diffie", credits=3),
    ]
    db.add_all(demos)
    db.commit()
    print(f"✅ Created {len(demos)} demo courses")
else:
    print(f"ℹ️  Courses already exist ({db.query(Course).count()}) - skipping demo")

# --- Demo Assignment ---
if db.query(Assignment).count() == 0:
    cs101 = db.query(Course).filter(Course.code == "CS101").first()
    if cs101:
        db.add(Assignment(course_id=cs101.id, created_by=admin.id, title="Assignment 1: Hybrid DB", description="Explain PostgreSQL vs SQLite - when to use each. Submit via Hub (MinIO S3).", max_score=100))
        db.commit()
        print("✅ Created demo assignment")

db.close()
print(f"\n🔐 Login: {admin_email} / {admin_password}")
print("📚 Courses ready - see /courses, /assignments, /exams")
print("⚠️  Change password: Superadmin Dashboard -> chat `change password NEW`")
