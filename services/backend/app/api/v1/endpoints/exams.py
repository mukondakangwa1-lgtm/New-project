"""
Digital Campus - Exams & Quizzes
"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models import User
from app.models_extended import Exam, ExamQuestion, ExamAttempt, Notification

router = APIRouter()


class ExamCreate(BaseModel):
    course_id: int
    title: str
    description: str = ""
    duration_minutes: int = 60
    max_score: int = 100
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class QuestionCreate(BaseModel):
    question_text: str
    question_type: str = "multiple_choice"
    options: str = "[]"  # JSON array
    correct_answer: str = ""
    points: int = 1


class AnswerSubmit(BaseModel):
    answers: dict  # {question_id: answer}


@router.get("/exams")
def list_exams(course_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Exam).filter(Exam.is_published == True)
    if course_id:
        q = q.filter(Exam.course_id == course_id)
    return q.order_by(Exam.created_at.desc()).all()


@router.post("/exams", status_code=201)
def create_exam(body: ExamCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    e = Exam(created_by=admin.id, **body.model_dump())
    if body.start_time:
        e.start_time = datetime.fromisoformat(body.start_time)
    if body.end_time:
        e.end_time = datetime.fromisoformat(body.end_time)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@router.post("/exams/{exam_id}/questions", status_code=201)
def add_question(exam_id: int, body: QuestionCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(404, "Exam not found")
    count = db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id).count()
    q = ExamQuestion(exam_id=exam_id, question_text=body.question_text, question_type=body.question_type, options=body.options, correct_answer=body.correct_answer, points=body.points, order_index=count)
    db.add(q)
    db.commit()
    return q


@router.post("/exams/{exam_id}/publish")
def publish_exam(exam_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    e = db.query(Exam).filter(Exam.id == exam_id).first()
    if not e:
        raise HTTPException(404, "Exam not found")
    e.is_published = True
    db.commit()
    return {"status": "published"}


@router.get("/exams/{exam_id}")
def get_exam(exam_id: int, db: Session = Depends(get_db)):
    e = db.query(Exam).options(joinedload(Exam.questions)).filter(Exam.id == exam_id).first()
    if not e:
        raise HTTPException(404, "Exam not found")
    return e


@router.post("/exams/{exam_id}/start", status_code=201)
def start_attempt(exam_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    exam = db.query(Exam).filter(Exam.id == exam_id, Exam.is_published == True).first()
    if not exam:
        raise HTTPException(404, "Exam not found")
    attempt = ExamAttempt(exam_id=exam_id, student_id=user.id, status="in_progress")
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


@router.post("/exams/{exam_id}/submit/{attempt_id}")
def submit_attempt(exam_id: int, attempt_id: int, body: AnswerSubmit, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = db.query(ExamAttempt).filter(ExamAttempt.id == attempt_id, ExamAttempt.student_id == user.id).first()
    if not attempt:
        raise HTTPException(404, "Attempt not found")
    attempt.answers = json.dumps(body.answers)
    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.status = "submitted"

    # Auto-grade
    questions = db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id).all()
    score = 0
    for q in questions:
        user_answer = body.answers.get(str(q.id), "")
        if q.question_type in ("multiple_choice", "true_false"):
            if str(user_answer).strip().lower() == str(q.correct_answer).strip().lower():
                score += q.points
        elif q.question_type == "short_answer":
            if str(user_answer).strip().lower() == str(q.correct_answer).strip().lower():
                score += q.points
    attempt.score = score
    attempt.status = "graded"

    db.add(Notification(user_id=user.id, title="Exam Graded", message=f"Your exam attempt scored {score}/{sum(q.points for q in questions)}", notification_type="grade"))
    db.commit()
    return {"score": score, "total": sum(q.points for q in questions), "percentage": round(score / sum(q.points for q in questions) * 100, 1) if questions else 0}
