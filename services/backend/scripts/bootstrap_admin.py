"""
E2E bootstrap — creates the admin user and a seeded sandbox workspace from
environment variables (used by the docker-based Playwright job):

    ADMIN_EMAIL, ADMIN_PASSWORD  -> superadmin login
    E2E_REPO_ROOT                -> directory that holds .kudos_workspaces/
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal, init_db
from app.core.security import get_password_hash
from app.models import User

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "e2e@campus.edu")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "E2e-pass-1234")
REPO_ROOT = os.environ.get("E2E_REPO_ROOT", "/e2e-repo")


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if not user:
            user = User(email=ADMIN_EMAIL, full_name="E2E Admin",
                        hashed_password=get_password_hash(ADMIN_PASSWORD))
            db.add(user)
        user.is_admin = True
        db.commit()
        print(f"admin ready: {ADMIN_EMAIL} (admin={user.is_admin})")
    finally:
        db.close()

    ws_root = os.path.join(REPO_ROOT, ".kudos_workspaces", "ws1")
    os.makedirs(ws_root, exist_ok=True)
    with open(os.path.join(ws_root, "hello.txt"), "w") as fh:
        fh.write("hello from the e2e workspace\n")
    print(f"workspace seeded: {ws_root}")


if __name__ == "__main__":
    sys.exit(main())
