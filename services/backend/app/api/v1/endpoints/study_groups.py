"""
Digital Campus - Study Groups & Forums
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.models_extended import StudyGroup, StudyGroupMember, ForumThread, ForumReply

router = APIRouter()


class GroupCreate(BaseModel):
    name: str
    description: str = ""
    course_id: Optional[int] = None
    max_members: int = 20
    is_public: bool = True


class ThreadCreate(BaseModel):
    course_id: int
    title: str
    content: str = ""


class ReplyCreate(BaseModel):
    content: str


# Study Groups
@router.get("/groups")
def list_groups(course_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(StudyGroup).filter(StudyGroup.is_public == True)
    if course_id:
        q = q.filter(StudyGroup.course_id == course_id)
    return q.order_by(StudyGroup.created_at.desc()).all()


@router.post("/groups", status_code=201)
def create_group(body: GroupCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    g = StudyGroup(created_by=user.id, **body.model_dump())
    db.add(g)
    db.flush()
    db.add(StudyGroupMember(group_id=g.id, user_id=user.id, role="moderator"))
    db.commit()
    db.refresh(g)
    return g


@router.post("/groups/{group_id}/join")
def join_group(group_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    g = db.query(StudyGroup).filter(StudyGroup.id == group_id).first()
    if not g:
        raise HTTPException(404, "Group not found")
    existing = db.query(StudyGroupMember).filter(StudyGroupMember.group_id == group_id, StudyGroupMember.user_id == user.id).first()
    if existing:
        return {"message": "Already a member"}
    count = db.query(StudyGroupMember).filter(StudyGroupMember.group_id == group_id).count()
    if count >= g.max_members:
        raise HTTPException(400, "Group is full")
    db.add(StudyGroupMember(group_id=group_id, user_id=user.id))
    db.commit()
    return {"message": "Joined group"}


@router.get("/groups/{group_id}")
def get_group(group_id: int, db: Session = Depends(get_db)):
    g = db.query(StudyGroup).options(joinedload(StudyGroup.members).joinedload(StudyGroupMember.user)).filter(StudyGroup.id == group_id).first()
    if not g:
        raise HTTPException(404, "Group not found")
    return g


# Forums
@router.get("/forums/{course_id}")
def list_threads(course_id: int, db: Session = Depends(get_db)):
    return db.query(ForumThread).options(joinedload(ForumThread.creator)).filter(ForumThread.course_id == course_id).order_by(ForumThread.is_pinned.desc(), ForumThread.created_at.desc()).all()


@router.post("/forums/{course_id}", status_code=201)
def create_thread(course_id: int, body: ThreadCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = ForumThread(course_id=course_id, created_by=user.id, title=body.title, content=body.content)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.get("/forums/thread/{thread_id}")
def get_thread(thread_id: int, db: Session = Depends(get_db)):
    t = db.query(ForumThread).options(joinedload(ForumThread.replies).joinedload(ForumReply.creator), joinedload(ForumThread.creator)).filter(ForumThread.id == thread_id).first()
    if not t:
        raise HTTPException(404, "Thread not found")
    t.view_count += 1
    db.commit()
    return t


@router.post("/forums/thread/{thread_id}/reply", status_code=201)
def reply_to_thread(thread_id: int, body: ReplyCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(ForumThread).filter(ForumThread.id == thread_id).first()
    if not t:
        raise HTTPException(404, "Thread not found")
    if t.is_locked:
        raise HTTPException(400, "Thread is locked")
    r = ForumReply(thread_id=thread_id, created_by=user.id, content=body.content)
    db.add(r)
    db.commit()
    return r
