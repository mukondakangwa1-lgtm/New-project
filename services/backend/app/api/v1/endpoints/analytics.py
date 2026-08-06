"""
Digital Campus - Admin Analytics Dashboard
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.models import User, Course, Enrollment, Attendance, Session as SessionModel, KudosConversation, KudosMessage
from app.models_extended import Assignment, Submission, Grade, Notification, ExamAttempt

router = APIRouter()


@router.get("/overview")
def admin_overview(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Get complete platform overview."""
    return {
        "users": {
            "total": db.query(User).count(),
            "admins": db.query(User).filter(User.is_admin == True).count(),
            "students": db.query(User).filter(User.is_admin == False).count(),
        },
        "courses": {
            "total": db.query(Course).count(),
            "enrollments": db.query(Enrollment).count(),
        },
        "attendance": {
            "total_sessions": db.query(SessionModel).count(),
            "total_checkins": db.query(Attendance).count(),
            "present": db.query(Attendance).filter(Attendance.status == "present").count(),
            "late": db.query(Attendance).filter(Attendance.status == "late").count(),
            "absent": db.query(Attendance).filter(Attendance.status == "absent").count(),
        },
        "assignments": {
            "total": db.query(Assignment).count(),
            "submissions": db.query(Submission).count(),
            "graded": db.query(Submission).filter(Submission.status == "graded").count(),
        },
        "exams": {
            "total_attempts": db.query(ExamAttempt).count(),
            "graded": db.query(ExamAttempt).filter(ExamAttempt.status == "graded").count(),
        },
        "kudos": {
            "conversations": db.query(KudosConversation).count(),
            "messages": db.query(KudosMessage).count(),
        },
    }


@router.get("/attendance-trends")
def attendance_trends(days: int = 30, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Get attendance trends over time."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    sessions = db.query(SessionModel).filter(SessionModel.session_date >= since.date()).all()
    trends = []
    for s in sessions:
        checkins = db.query(Attendance).filter(Attendance.session_id == s.id).count()
        trends.append({
            "date": str(s.session_date),
            "course_id": s.course_id,
            "checkins": checkins,
        })
    return {"days": days, "data": trends}


@router.get("/top-courses")
def top_courses(limit: int = 10, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Get courses with most enrollments."""
    results = (
        db.query(Course, func.count(Enrollment.id).label("count"))
        .outerjoin(Enrollment)
        .group_by(Course.id)
        .order_by(func.count(Enrollment.id).desc())
        .limit(limit)
        .all()
    )
    return [{"course_id": c.id, "code": c.code, "title": c.title, "enrollments": count} for c, count in results]


@router.get("/engagement")
def engagement_stats(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Get user engagement metrics."""
    active_users = db.query(User).filter(User.is_active == True).count()
    users_with_submissions = db.query(func.count(func.distinct(Submission.student_id))).scalar() or 0
    users_with_attendance = db.query(func.count(func.distinct(Attendance.student_id))).scalar() or 0
    return {
        "active_users": active_users,
        "users_submitting_assignments": users_with_submissions,
        "users_attending_classes": users_with_attendance,
        "engagement_rate": round(users_with_attendance / active_users * 100, 1) if active_users > 0 else 0,
    }
