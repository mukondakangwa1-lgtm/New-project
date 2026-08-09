"""
Digital Campus - KUDOS Visit Hook
Public, auth-free endpoint. Fired by the frontend whenever someone loads a
page: the first visit switches on KUDOS' continuous learning for good
(never stops by itself — it just keeps improving).
"""
from fastapi import APIRouter

from app.core.auto_learner import resume_kudos_learner, start_learning_on_visit

router = APIRouter()


@router.post("/visit")
def visit():
    """Site visit hook — starts (or confirms) continuous learning."""
    result = start_learning_on_visit()
    if result.get("error"):
        # No admin account yet — keep the flag armed so the first admin
        # login triggers the same resume path.
        resume_kudos_learner()
    return result