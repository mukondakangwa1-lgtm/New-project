"""
Digital Campus - SQLAlchemy Models
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    enrollments = relationship("Enrollment", back_populates="student")
    attendances = relationship("Attendance", back_populates="student")

    def __repr__(self):
        return f"<User {self.email}>"


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    code = Column(String(20), unique=True, index=True, nullable=False)
    description = Column(Text, default="")
    instructor = Column(String(255), default="")
    credits = Column(Integer, default=3)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    enrollments = relationship("Enrollment", back_populates="course")
    timetable_entries = relationship("TimetableEntry", back_populates="course")

    def __repr__(self):
        return f"<Course {self.code}: {self.title}>"


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    enrolled_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    grade = Column(String(2), default="")

    # Relationships
    student = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")


class TimetableEntry(Base):
    """Recurring class schedule — the template for auto-generating sessions."""
    __tablename__ = "timetable_entries"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday .. 6=Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    room = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    course = relationship("Course", back_populates="timetable_entries")
    sessions = relationship("Session", back_populates="timetable_entry")


class Session(Base):
    """An individual attendance session — auto-generated from timetable."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    timetable_entry_id = Column(Integer, ForeignKey("timetable_entries.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    session_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    room = Column(String(100), default="")
    is_open = Column(Boolean, default=False)  # True = accepting check-ins
    is_cancelled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    timetable_entry = relationship("TimetableEntry", back_populates="sessions")
    course = relationship("Course")
    attendances = relationship("Attendance", back_populates="session")


class Attendance(Base):
    """A student's check-in record for a session."""
    __tablename__ = "attendances"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    checked_in_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(20), default="present")  # present, late, absent, excused
    notes = Column(Text, default="")

    # Relationships
    session = relationship("Session", back_populates="attendances")
    student = relationship("User", back_populates="attendances")


# ──────────────────────────────────────────────
# SOCIAL HUB MODELS
# ──────────────────────────────────────────────


class Post(Base):
    """A social post linking to external storage — no files stored on platform."""
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    storage_url = Column(Text, nullable=False)  # S3 key (s3) or external URL (link/youtube/image)
    storage_type = Column(String(50), default="link")  # connected: s3 (MinIO/R2), link, youtube, image (dead gdrive/dropbox removed)
    content_type = Column(String(100), default="")  # mime type hint: image, video, document, audio
    thumbnail_url = Column(Text, default="")
    is_public = Column(Boolean, default=True)
    tags = Column(String(500), default="")  # comma-separated
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    reactions = relationship("Reaction", back_populates="post", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    post = relationship("Post", back_populates="comments")
    user = relationship("User")


class Reaction(Base):
    """Like / emoji reaction on a post."""
    __tablename__ = "reactions"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    emoji = Column(String(10), default="👍")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    post = relationship("Post", back_populates="reactions")
    user = relationship("User")


# ──────────────────────────────────────────────
# CHAT MODELS
# ──────────────────────────────────────────────


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    is_group = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    messages = relationship("ChatMessage", back_populates="room", cascade="all, delete-orphan")
    members = relationship("ChatMember", back_populates="room", cascade="all, delete-orphan")


class ChatMember(Base):
    __tablename__ = "chat_members"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    room = relationship("ChatRoom", back_populates="members")
    user = relationship("User")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="text")  # text, image, file, link
    is_offline = Column(Boolean, default=False)  # created while offline, synced later
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    room = relationship("ChatRoom", back_populates="messages")
    user = relationship("User")


# ──────────────────────────────────────────────
# KUDOS AI MODELS
# ──────────────────────────────────────────────


class KudosDocument(Base):
    """Document uploaded to KUDOS for learning."""
    __tablename__ = "kudos_documents"

    id = Column(Integer, primary_key=True, index=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), default="")  # txt, md, pdf, docx
    content = Column(Text, default="")  # extracted text content
    summary = Column(Text, default="")  # auto-generated summary
    tags = Column(String(500), default="")
    is_approved = Column(Boolean, default=False)  # superadmin must approve
    is_active = Column(Boolean, default=True)
    chunk_count = Column(Integer, default=0)  # how many chunks stored
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    chunks = relationship("KudosChunk", back_populates="document", cascade="all, delete-orphan")
    uploader = relationship("User")


class KudosChunk(Base):
    """A chunk of text from a document — used for retrieval."""
    __tablename__ = "kudos_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("kudos_documents.id"), nullable=False)
    chunk_index = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    word_count = Column(Integer, default=0)
    keywords = Column(Text, default="")  # extracted keywords for matching
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("KudosDocument", back_populates="chunks")


class KudosWebKnowledge(Base):
    """Web page content learned by KUDOS."""
    __tablename__ = "kudos_web_knowledge"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(Text, nullable=False)
    title = Column(String(255), default="")
    content = Column(Text, default="")  # extracted text
    summary = Column(Text, default="")
    is_approved = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    learned_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    learner = relationship("User")


class KudosConversation(Base):
    """A conversation thread with KUDOS."""
    __tablename__ = "kudos_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), default="New Conversation")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
    messages = relationship("KudosMessage", back_populates="conversation", cascade="all, delete-orphan")


class KudosMessage(Base):
    """A single message in a KUDOS conversation."""
    __tablename__ = "kudos_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("kudos_conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, kudos
    content = Column(Text, nullable=False)
    sources = Column(Text, default="")  # JSON: which documents were referenced
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("KudosConversation", back_populates="messages")


# ──────────────────────────────────────────────
# KUDOS CONNECTOR MODELS
# ──────────────────────────────────────────────


class KudosConnector(Base):
    """
    A connected source: GitHub repo, website, API endpoint, RSS feed, etc.
    KUDOS learns from all connected sources.
    """
    __tablename__ = "kudos_connectors"

    id = Column(Integer, primary_key=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    connector_type = Column(String(50), nullable=False)  # github, website, api, rss, gitlab, npm, pypi
    source_url = Column(Text, nullable=False)  # the URL to connect to
    config = Column(Text, default="{}")  # JSON config (e.g. file patterns, auth token ref, depth)
    status = Column(String(20), default="active")  # active, paused, error
    last_synced_at = Column(DateTime, nullable=True)
    items_learned = Column(Integer, default=0)
    error_message = Column(Text, default="")
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    creator = relationship("User")
    sync_logs = relationship("KudosSyncLog", back_populates="connector", cascade="all, delete-orphan")


class KudosSyncLog(Base):
    """Log of sync operations for connectors."""
    __tablename__ = "kudos_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    connector_id = Column(Integer, ForeignKey("kudos_connectors.id"), nullable=False)
    action = Column(String(50), nullable=False)  # sync, crawl, fetch, error
    items_found = Column(Integer, default=0)
    items_new = Column(Integer, default=0)
    items_updated = Column(Integer, default=0)
    details = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    connector = relationship("KudosConnector", back_populates="sync_logs")


class KudosKnowledgePack(Base):
    """
    An exportable/importable knowledge pack for offline use.
    Contains chunks, metadata, and source info.
    """
    __tablename__ = "kudos_knowledge_packs"

    id = Column(Integer, primary_key=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    pack_data = Column(Text, default="")  # JSON: serialized knowledge chunks
    item_count = Column(Integer, default=0)
    size_bytes = Column(Integer, default=0)
    is_shared = Column(Boolean, default=False)  # can other users import it?
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    creator = relationship("User")
