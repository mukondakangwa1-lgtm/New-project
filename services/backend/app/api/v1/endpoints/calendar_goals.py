"""
Digital Campus - Calendar, Goals & Notifications
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.models_extended import CalendarEvent, StudyGoal, Notification

router = APIRouter()


class EventCreate(BaseModel):
    title: str
    description: str = ""
    event_type: str = "custom"
    start_time: str
    end_time: str
    location: str = ""
    course_id: Optional[int] = None
    reminder_minutes: int = 30


class GoalCreate(BaseModel):
    title: str
    description: str = ""
    goal_type: str = "daily"
    target_value: int = 1
    deadline: Optional[str] = None


# Calendar
@router.get("/calendar")
def list_events(start: Optional[str] = None, end: Optional[str] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(CalendarEvent).filter(CalendarEvent.user_id == user.id)
    if start:
        q = q.filter(CalendarEvent.start_time >= datetime.fromisoformat(start))
    if end:
        q = q.filter(CalendarEvent.end_time <= datetime.fromisoformat(end))
    return q.order_by(CalendarEvent.start_time).all()


@router.post("/calendar", status_code=201)
def create_event(body: EventCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    e = CalendarEvent(
        user_id=user.id, title=body.title, description=body.description,
        event_type=body.event_type, start_time=datetime.fromisoformat(body.start_time),
        end_time=datetime.fromisoformat(body.end_time), location=body.location,
        course_id=body.course_id, reminder_minutes=body.reminder_minutes,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@router.delete("/calendar/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    e = db.query(CalendarEvent).filter(CalendarEvent.id == event_id, CalendarEvent.user_id == user.id).first()
    if not e:
        raise HTTPException(404, "Event not found")
    db.delete(e)
    db.commit()


# Goals
@router.get("/goals")
def list_goals(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(StudyGoal).filter(StudyGoal.user_id == user.id).order_by(StudyGoal.created_at.desc()).all()


@router.post("/goals", status_code=201)
def create_goal(body: GoalCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    g = StudyGoal(user_id=user.id, **body.model_dump())
    if body.deadline:
        g.deadline = datetime.fromisoformat(body.deadline)
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


@router.patch("/goals/{goal_id}")
def update_goal_progress(goal_id: int, increment: int = 1, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    g = db.query(StudyGoal).filter(StudyGoal.id == goal_id, StudyGoal.user_id == user.id).first()
    if not g:
        raise HTTPException(404, "Goal not found")
    g.current_value = min(g.current_value + increment, g.target_value)
    if g.current_value >= g.target_value:
        g.is_completed = True
    db.commit()
    return g


# Notifications
@router.get("/notifications")
def list_notifications(unread_only: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        q = q.filter(Notification.is_read == False)
    return q.order_by(Notification.created_at.desc()).limit(50).all()


@router.patch("/notifications/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user.id).first()
    if n:
        n.is_read = True
        db.commit()
    return {"status": "read"}


@router.post("/notifications/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read == False).update({"is_read": True})
    db.commit()
    return {"status": "all_read"}
