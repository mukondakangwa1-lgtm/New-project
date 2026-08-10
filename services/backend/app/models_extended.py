"""
Digital Campus - Extended Models
Assignments, Grades, Study Groups, Forums, Calendar, Goals, Exams, Notifications
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# ──────────────────────────────────────────────
# ASSIGNMENTS & GRADES
# ──────────────────────────────────────────────

class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    due_date = Column(DateTime, nullable=True)
    max_score = Column(Integer, default=100)
    weight = Column(Float, default=1.0)  # percentage weight in final grade
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    course = relationship("Course")
    creator = relationship("User")
    submissions = relationship("Submission", back_populates="assignment", cascade="all, delete-orphan")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, default="")
    file_url = Column(Text, default="")  # link to external file
    score = Column(Float, nullable=True)
    feedback = Column(Text, default="")
    status = Column(String(20), default="submitted")  # submitted, graded, returned
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    graded_at = Column(DateTime, nullable=True)

    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("User")


class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    letter_grade = Column(String(2), default="")
    gpa_points = Column(Float, default=0.0)
    percentage = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    student = relationship("User")
    course = relationship("Course")


# ──────────────────────────────────────────────
# STUDY GROUPS
# ──────────────────────────────────────────────

class StudyGroup(Base):
    __tablename__ = "study_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    max_members = Column(Integer, default=20)
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    course = relationship("Course")
    creator = relationship("User")
    members = relationship("StudyGroupMember", back_populates="group", cascade="all, delete-orphan")


class StudyGroupMember(Base):
    __tablename__ = "study_group_members"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("study_groups.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), default="member")  # member, moderator
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    group = relationship("StudyGroup", back_populates="members")
    user = relationship("User")


# ──────────────────────────────────────────────
# DISCUSSION FORUMS
# ──────────────────────────────────────────────

class ForumThread(Base):
    __tablename__ = "forum_threads"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, default="")
    is_pinned = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    course = relationship("Course")
    creator = relationship("User")
    replies = relationship("ForumReply", back_populates="thread", cascade="all, delete-orphan")


class ForumReply(Base):
    __tablename__ = "forum_replies"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("forum_threads.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_solution = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    thread = relationship("ForumThread", back_populates="replies")
    creator = relationship("User")


# ──────────────────────────────────────────────
# CALENDAR & GOALS
# ──────────────────────────────────────────────

class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    event_type = Column(String(50), default="custom")  # class, study, assignment, exam, custom
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    location = Column(String(255), default="")
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    reminder_minutes = Column(Integer, default=30)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
    course = relationship("Course")


class StudyGoal(Base):
    __tablename__ = "study_goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    goal_type = Column(String(50), default="daily")  # daily, weekly, monthly, custom
    target_value = Column(Integer, default=1)  # e.g., study 2 hours, complete 3 tasks
    current_value = Column(Integer, default=0)
    deadline = Column(DateTime, nullable=True)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")


# ──────────────────────────────────────────────
# EXAMS & QUIZZES
# ──────────────────────────────────────────────

class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    duration_minutes = Column(Integer, default=60)
    max_score = Column(Integer, default=100)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    course = relationship("Course")
    creator = relationship("User")
    questions = relationship("ExamQuestion", back_populates="exam", cascade="all, delete-orphan")
    attempts = relationship("ExamAttempt", back_populates="exam", cascade="all, delete-orphan")


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(20), default="multiple_choice")  # multiple_choice, true_false, short_answer
    options = Column(Text, default="")  # JSON: ["A", "B", "C", "D"]
    correct_answer = Column(Text, default="")
    points = Column(Integer, default=1)
    order_index = Column(Integer, default=0)

    exam = relationship("Exam", back_populates="questions")


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    answers = Column(Text, default="")  # JSON: {question_id: answer}
    score = Column(Float, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    submitted_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="in_progress")  # in_progress, submitted, graded

    exam = relationship("Exam", back_populates="attempts")
    student = relationship("User")


# ──────────────────────────────────────────────
# NOTIFICATIONS
# ──────────────────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, default="")
    notification_type = Column(String(50), default="info")  # info, warning, assignment, grade, chat, system
    is_read = Column(Boolean, default=False)
    link = Column(Text, default="")  # URL to navigate to
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")


# ──────────────────────────────────────────────
# CERTIFICATES
# ──────────────────────────────────────────────

class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    certificate_number = Column(String(50), unique=True, nullable=False)
    issued_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
    course = relationship("Course")


# ──────────────────────────────────────────────
# STUDIO: SPEAKING, BROADCASTS, VIDEO CALLS, JOURNAL
# ──────────────────────────────────────────────

class SpeakingSession(Base):
    __tablename__ = "speaking_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    prompt = Column(Text, nullable=False)
    difficulty = Column(String(20), default="beginner")
    duration_seconds = Column(Integer, default=120)
    status = Column(String(20), default="active")  # active, completed
    duration_spoken = Column(Integer, default=0)
    self_rating = Column(Integer, nullable=True)  # 1-5
    notes = Column(Text, default="")
    audio_url = Column(Text, default="")  # path to saved recording
    audio_mime = Column(String(60), default="")  # actual container format (webm/ogg/mp4)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User")


class VoiceProfile(Base):
    """KUDOS's signature voice: the superadmin captures their own voice and
    it becomes the voice KUDOS speaks with on every platform."""
    __tablename__ = "voice_profiles"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    tts_enabled = Column(Boolean, default=False)
    cloned_voice_id = Column(String(120), default="")  # ElevenLabs voice id
    default_voice = Column(String(120), default="")    # fallback voice name/id
    signature_active = Column(Boolean, default=False)  # KUDOS speaks with the superadmin's voice
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class VoiceSample(Base):
    """A recording of the superadmin reading for KUDOS's signature voice."""
    __tablename__ = "voice_samples"

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("voice_profiles.id"), nullable=True)
    storage_key = Column(String(255), default="")
    mime = Column(String(60), default="audio/webm")
    transcribed = Column(Text, default="")
    duration_seconds = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    duration_minutes = Column(Integer, default=30)
    is_public = Column(Boolean, default=True)
    status = Column(String(20), default="live")  # live, ended
    listeners = Column(Integer, default=0)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)

    host = relationship("User")


class VideoCall(Base):
    __tablename__ = "video_calls"

    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), default="Video Call")
    is_group = Column(Boolean, default=False)
    max_participants = Column(Integer, default=10)
    enable_whiteboard = Column(Boolean, default=True)
    enable_screen_share = Column(Boolean, default=True)
    status = Column(String(20), default="active")  # active, ended
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    host = relationship("User")
    participants = relationship("CallParticipant", back_populates="call", cascade="all, delete-orphan")


class CallParticipant(Base):
    __tablename__ = "call_participants"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("video_calls.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), default="participant")  # host, participant
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    left_at = Column(DateTime, nullable=True)

    call = relationship("VideoCall", back_populates="participants")
    user = relationship("User")


class WhiteboardStroke(Base):
    __tablename__ = "whiteboard_strokes"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("video_calls.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    data = Column(Text, default="[]")  # JSON batch of stroke points
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    call = relationship("VideoCall")
    author = relationship("User")


class WebRtcSignal(Base):
    __tablename__ = "webrtc_signals"

    id = Column(Integer, primary_key=True, index=True)
    room_type = Column(String(20), nullable=False)  # call, broadcast
    room_id = Column(Integer, nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    signal_type = Column(String(20), nullable=False)  # offer, answer, ice
    payload = Column(Text, nullable=False)  # JSON SDP / ICE candidate
    is_consumed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_id])


class JournalBlock(Base):
    __tablename__ = "journal_blocks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    block_type = Column(String(30), default="webpage")
    url = Column(Text, default="")
    content = Column(Text, default="")
    position = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
