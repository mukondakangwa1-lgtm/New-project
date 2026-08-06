"""
Digital Campus - Assignments & Grades
"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models import User, Course, Enrollment
from app.models_extended import Assignment, Submission, Grade, Notification

router = APIRouter()


class AssignmentCreate(BaseModel):
    course_id: int
    title: str
    description: str = ""
    due_date: Optional[str] = None
    max_score: int = 100
    weight: float = 1.0


class SubmissionCreate(BaseModel):
    content: str = ""
    file_url: str = ""


class GradeSubmission(BaseModel):
    score: float
    feedback: str = ""


# Assignments
@router.get("/assignments")
def list_assignments(course_id: Optional[int] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Assignment)
    if course_id:
        q = q.filter(Assignment.course_id == course_id)
    return q.order_by(Assignment.created_at.desc()).all()


@router.post("/assignments", status_code=201)
def create_assignment(body: AssignmentCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    a = Assignment(created_by=admin.id, **body.model_dump())
    if body.due_date:
        a.due_date = datetime.fromisoformat(body.due_date)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.post("/assignments/{assignment_id}/submit", status_code=201)
def submit_assignment(assignment_id: int, body: SubmissionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not a:
        raise HTTPException(404, "Assignment not found")
    existing = db.query(Submission).filter(Submission.assignment_id == assignment_id, Submission.student_id == user.id).first()
    if existing:
        existing.content = body.content
        existing.file_url = body.file_url
        existing.status = "submitted"
        existing.submitted_at = datetime.now(timezone.utc)
        db.commit()
        return existing
    s = Submission(assignment_id=assignment_id, student_id=user.id, content=body.content, file_url=body.file_url)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.get("/assignments/{assignment_id}/submissions")
def list_submissions(assignment_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(Submission).options(joinedload(Submission.student)).filter(Submission.assignment_id == assignment_id).all()


@router.post("/assignments/{assignment_id}/submissions/{submission_id}/grade")
def grade_submission(assignment_id: int, submission_id: int, body: GradeSubmission, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    s = db.query(Submission).filter(Submission.id == submission_id, Submission.assignment_id == assignment_id).first()
    if not s:
        raise HTTPException(404, "Submission not found")
    s.score = body.score
    s.feedback = body.feedback
    s.status = "graded"
    s.graded_at = datetime.now(timezone.utc)
    # Create notification
    db.add(Notification(user_id=s.student_id, title="Assignment Graded", message=f"Your submission scored {body.score}. Feedback: {body.feedback[:200]}", notification_type="grade", link=f"/courses"))
    db.commit()
    return s


# Grades
@router.get("/grades/my")
def my_grades(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Grade).filter(Grade.student_id == user.id).all()


@router.get("/grades/course/{course_id}")
def course_grades(course_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(Grade).options(joinedload(Grade.student)).filter(Grade.course_id == course_id).all()
