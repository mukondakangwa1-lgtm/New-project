"""
Digital Campus - Timetable & Attendance Endpoints
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models import Attendance, Course, Session as SessionModel, TimetableEntry, User
from app.schemas import (
    AttendanceCheckIn,
    AttendanceMark,
    AttendanceReport,
    AttendanceResponse,
    AttendanceWithStudent,
    SessionBulkGenerate,
    SessionBulkGenerateResponse,
    SessionOpenClose,
    SessionResponse,
    SessionWithCourse,
    TimetableEntryCreate,
    TimetableEntryResponse,
    TimetableEntryUpdate,
    TimetableEntryWithCourse,
    UserResponse,
)

router = APIRouter()

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ──────────────────────────────────────────────
# TIMETABLE CRUD
# ──────────────────────────────────────────────


@router.get("/timetable", response_model=list[TimetableEntryWithCourse])
def list_timetable(
    course_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all timetable entries, optionally filtered by course."""
    q = db.query(TimetableEntry).options(joinedload(TimetableEntry.course))
    if course_id:
        q = q.filter(TimetableEntry.course_id == course_id)
    return q.order_by(TimetableEntry.day_of_week, TimetableEntry.start_time).all()


@router.post("/timetable", response_model=TimetableEntryResponse, status_code=201)
def create_timetable_entry(
    entry_in: TimetableEntryCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Create a timetable entry (admin only)."""
    # Verify course exists
    course = db.query(Course).filter(Course.id == entry_in.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if entry_in.day_of_week < 0 or entry_in.day_of_week > 6:
        raise HTTPException(status_code=400, detail="day_of_week must be 0-6 (Mon-Sun)")

    if entry_in.start_time >= entry_in.end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")

    entry = TimetableEntry(**entry_in.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/timetable/{entry_id}", response_model=TimetableEntryResponse)
def update_timetable_entry(
    entry_id: int,
    entry_in: TimetableEntryUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update a timetable entry (admin only)."""
    entry = db.query(TimetableEntry).filter(TimetableEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Timetable entry not found")

    for field, value in entry_in.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)

    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/timetable/{entry_id}", status_code=204)
def delete_timetable_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete a timetable entry (admin only)."""
    entry = db.query(TimetableEntry).filter(TimetableEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Timetable entry not found")
    db.delete(entry)
    db.commit()


# ──────────────────────────────────────────────
# SESSIONS — AUTO-GENERATE FROM TIMETABLE
# ──────────────────────────────────────────────


@router.post("/sessions/generate", response_model=SessionBulkGenerateResponse)
def generate_sessions(
    body: SessionBulkGenerate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Auto-generate attendance sessions from timetable entries
    for a date range. Skips dates that already have sessions.
    """
    # Get relevant timetable entries
    q = db.query(TimetableEntry).filter(TimetableEntry.is_active == True)
    if body.course_id:
        q = q.filter(TimetableEntry.course_id == body.course_id)
    entries = q.all()

    if not entries:
        raise HTTPException(status_code=404, detail="No active timetable entries found")

    created = 0
    current = body.start_date
    while current <= body.end_date:
        weekday = current.weekday()  # 0=Mon .. 6=Sun
        for entry in entries:
            if entry.day_of_week != weekday:
                continue

            # Skip if session already exists for this entry + date
            existing = (
                db.query(SessionModel)
                .filter(
                    SessionModel.timetable_entry_id == entry.id,
                    SessionModel.session_date == current,
                )
                .first()
            )
            if existing:
                continue

            session = SessionModel(
                timetable_entry_id=entry.id,
                course_id=entry.course_id,
                session_date=current,
                start_time=entry.start_time,
                end_time=entry.end_time,
                room=entry.room,
                is_open=False,
            )
            db.add(session)
            created += 1

        current += timedelta(days=1)

    db.commit()
    return SessionBulkGenerateResponse(
        sessions_created=created,
        start_date=body.start_date,
        end_date=body.end_date,
    )


@router.get("/sessions", response_model=list[SessionWithCourse])
def list_sessions(
    course_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    is_open: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List sessions with optional filters."""
    q = db.query(SessionModel).options(joinedload(SessionModel.course))
    if course_id:
        q = q.filter(SessionModel.course_id == course_id)
    if date_from:
        q = q.filter(SessionModel.session_date >= date_from)
    if date_to:
        q = q.filter(SessionModel.session_date <= date_to)
    if is_open is not None:
        q = q.filter(SessionModel.is_open == is_open)
    return q.order_by(SessionModel.session_date, SessionModel.start_time).all()


@router.get("/sessions/today", response_model=list[SessionWithCourse])
def today_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all sessions scheduled for today."""
    today = date.today()
    return (
        db.query(SessionModel)
        .options(joinedload(SessionModel.course))
        .filter(SessionModel.session_date == today)
        .order_by(SessionModel.start_time)
        .all()
    )


@router.get("/sessions/active", response_model=list[SessionWithCourse])
def active_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all currently open sessions (accepting check-ins)."""
    return (
        db.query(SessionModel)
        .options(joinedload(SessionModel.course))
        .filter(SessionModel.is_open == True, SessionModel.is_cancelled == False)
        .order_by(SessionModel.session_date, SessionModel.start_time)
        .all()
    )


@router.get("/sessions/{session_id}", response_model=SessionWithCourse)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific session."""
    session = (
        db.query(SessionModel)
        .options(joinedload(SessionModel.course))
        .filter(SessionModel.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: int,
    body: SessionOpenClose,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Open or close a session for check-ins (admin only)."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_open = body.is_open
    db.commit()
    db.refresh(session)
    return session


@router.patch("/sessions/{session_id}/cancel", response_model=SessionResponse)
def cancel_session(
    session_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Cancel a session (admin only)."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_cancelled = True
    session.is_open = False
    db.commit()
    db.refresh(session)
    return session


# ──────────────────────────────────────────────
# ATTENDANCE — CHECK-IN & RECORDS
# ──────────────────────────────────────────────


@router.post("/attendance/check-in", response_model=AttendanceResponse, status_code=201)
def student_check_in(
    body: AttendanceCheckIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Student checks in to an open session."""
    session = db.query(SessionModel).filter(SessionModel.id == body.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.is_open:
        raise HTTPException(status_code=400, detail="Session is not open for check-in")

    if session.is_cancelled:
        raise HTTPException(status_code=400, detail="Session has been cancelled")

    # Check duplicate
    existing = (
        db.query(Attendance)
        .filter(
            Attendance.session_id == body.session_id,
            Attendance.student_id == current_user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already checked in to this session")

    # Check enrollment
    from app.models import Enrollment

    enrolled = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == current_user.id,
            Enrollment.course_id == session.course_id,
        )
        .first()
    )
    if not enrolled:
        raise HTTPException(
            status_code=400,
            detail="You are not enrolled in this course",
        )

    attendance = Attendance(
        session_id=body.session_id,
        student_id=current_user.id,
        status=body.status,
        notes=body.notes,
    )
    db.add(attendance)
    db.commit()
    db.refresh(attendance)
    return attendance


@router.get("/attendance/session/{session_id}", response_model=list[AttendanceWithStudent])
def session_attendance(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all attendance records for a session."""
    return (
        db.query(Attendance)
        .options(joinedload(Attendance.student))
        .filter(Attendance.session_id == session_id)
        .all()
    )


@router.post("/attendance/session/{session_id}/mark", response_model=AttendanceResponse, status_code=201)
def admin_mark_attendance(
    session_id: int,
    body: AttendanceMark,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin marks a student as present/late/absent/excused (admin only)."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    student = db.query(User).filter(User.id == body.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Upsert — update if exists, create if not
    existing = (
        db.query(Attendance)
        .filter(
            Attendance.session_id == session_id,
            Attendance.student_id == body.student_id,
        )
        .first()
    )
    if existing:
        existing.status = body.status
        existing.notes = body.notes
        db.commit()
        db.refresh(existing)
        return existing

    attendance = Attendance(
        session_id=session_id,
        student_id=body.student_id,
        status=body.status,
        notes=body.notes,
    )
    db.add(attendance)
    db.commit()
    db.refresh(attendance)
    return attendance


@router.get("/attendance/my", response_model=list[AttendanceResponse])
def my_attendance(
    course_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's attendance records."""
    q = db.query(Attendance).filter(Attendance.student_id == current_user.id)
    if course_id:
        q = q.join(SessionModel).filter(SessionModel.course_id == course_id)
    return q.order_by(Attendance.checked_in_at.desc()).all()


@router.get("/attendance/report/{course_id}", response_model=list[AttendanceReport])
def attendance_report(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get attendance report for a course — stats per enrolled student."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Get all sessions for this course
    sessions = (
        db.query(SessionModel)
        .filter(SessionModel.course_id == course_id, SessionModel.is_cancelled == False)
        .all()
    )
    total_sessions = len(sessions)
    session_ids = [s.id for s in sessions]

    # Get enrolled students
    from app.models import Enrollment
    enrollments = (
        db.query(Enrollment)
        .options(joinedload(Enrollment.student))
        .filter(Enrollment.course_id == course_id)
        .all()
    )

    reports = []
    for enrollment in enrollments:
        student = enrollment.student

        if session_ids:
            attendances = (
                db.query(Attendance)
                .filter(
                    Attendance.student_id == student.id,
                    Attendance.session_id.in_(session_ids),
                )
                .all()
            )
        else:
            attendances = []

        present = sum(1 for a in attendances if a.status == "present")
        late = sum(1 for a in attendances if a.status == "late")
        excused = sum(1 for a in attendances if a.status == "excused")
        marked_absent = sum(1 for a in attendances if a.status == "absent")
        # Unmarked sessions count as absent
        unmarked = total_sessions - len(attendances)
        absent = marked_absent + unmarked

        attended = present + late + excused
        rate = (attended / total_sessions * 100) if total_sessions > 0 else 0.0

        reports.append(
            AttendanceReport(
                student=UserResponse.model_validate(student),
                course=course,
                total_sessions=total_sessions,
                present=present,
                late=late,
                absent=absent,
                excused=excused,
                attendance_rate=round(rate, 1),
            )
        )

    return reports
