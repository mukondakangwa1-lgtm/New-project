"""
Digital Campus - SQLAlchemy Models
"""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover - optional dependency import guard
    Vector = None


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=True)  # False when registration is gated (REQUIRE_APPROVAL)
    is_student = Column(Boolean, default=False)  # True when the user opted in as a student
    school = Column(String(255), nullable=True)  # School name entered at signup
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    enrolled_at = Column(DateTime, default=lambda: datetime.now(UTC))
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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    checked_in_at = Column(DateTime, default=lambda: datetime.now(UTC))
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
    storage_url = Column(Text, nullable=False)  # external URL (Drive, Dropbox, S3, etc.)
    storage_type = Column(String(50), default="link")  # link, youtube, image, video, document
    content_type = Column(String(100), default="")  # mime type hint: image, video, document, audio
    thumbnail_url = Column(Text, default="")
    is_public = Column(Boolean, default=True)
    tags = Column(String(500), default="")  # comma-separated
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    post = relationship("Post", back_populates="comments")
    user = relationship("User")


class Reaction(Base):
    """Like / emoji reaction on a post."""

    __tablename__ = "reactions"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    emoji = Column(String(10), default="👍")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    messages = relationship("ChatMessage", back_populates="room", cascade="all, delete-orphan")
    members = relationship("ChatMember", back_populates="room", cascade="all, delete-orphan")


class ChatMember(Base):
    __tablename__ = "chat_members"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    storage_key = Column(String(255), default="")  # object key in the docs/ bucket prefix
    content = Column(Text, default="")  # extracted text content
    summary = Column(Text, default="")  # auto-generated summary
    tags = Column(String(500), default="")
    is_approved = Column(Boolean, default=False)  # superadmin must approve
    is_active = Column(Boolean, default=True)
    chunk_count = Column(Integer, default=0)  # how many chunks stored
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    learner = relationship("User")


class KudosConversation(Base):
    """A conversation thread with KUDOS."""

    __tablename__ = "kudos_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    guest_key = Column(String(64), nullable=True, index=True)  # anonymous visitor chats
    title = Column(String(255), default="New Conversation")
    archived = Column(Boolean, default=False, index=True)  # moved to the archive panel (not deleted)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    media = Column(Text, default="")  # JSON: [{kind: image|video, url, mime, caption}]
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    creator = relationship("User")


class KudosMemory(Base):
    """
    A persistent memory for KUDOS: facts, preferences, concepts, events,
    rules and conversation context the assistant remembers per user.

    layer: short_term | long_term | knowledge | system
    kind:  fact | preference | concept | event | rule | error | success | context
    """

    __tablename__ = "kudos_memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    layer = Column(String(20), nullable=False, index=True, default="short_term")
    kind = Column(String(40), nullable=False, default="fact")
    content = Column(Text, nullable=False)
    summary = Column(Text, default="")
    embedding = Column(Vector(1536) if Vector else Text, nullable=True)
    importance = Column(Float, default=0.5)
    tags = Column(Text, default="[]")  # JSON list of tags
    source = Column(String(120), default="")
    access_count = Column(Integer, default=0)
    last_access_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # TTL for short-term memories
    device_policy = Column(String(20), default="replicated")  # local | replicated | critical
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    user = relationship("User")


class KudosDevice(Base):
    """
    A device registered by a user — phone, laptop, desktop. Devices lend
    their storage space to host replicas of the user's KUDOS memories.
    """

    __tablename__ = "kudos_devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # None for anonymous guest devices
    name = Column(String(120), nullable=False)
    platform = Column(String(30), default="generic")  # android | ios | desktop | web | linux
    api_token = Column(String(64), default="", index=True)
    status = Column(String(20), default="online")  # online | offline | retired
    storage_bytes = Column(Integer, default=536870912)  # 512 MB default capacity
    used_storage_bytes = Column(Integer, default=0)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    user = relationship("User")
    replicas = relationship("KudosMemoryReplica", back_populates="device", cascade="all, delete-orphan")


class KudosMemoryReplica(Base):
    """
    One copy of a memory stored on a device replica set.
    status: pending (awaiting pull) | current (acknowledged) | stale (needs resync)
    """

    __tablename__ = "kudos_memory_replicas"

    id = Column(Integer, primary_key=True, index=True)
    memory_id = Column(Integer, ForeignKey("kudos_memories.id"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("kudos_devices.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(20), default="replica")  # primary | replica
    status = Column(String(20), default="pending")  # pending | current | stale | purged
    synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    device = relationship("KudosDevice", back_populates="replicas")


class KudosBrain(Base):
    """
    KUDOS's offline brain — a persistent, self-contained store of facts and
    insights, each with proven provenance (source document/web page/memory).
    KUDOS reasons and answers from this store WITHOUT any external LLM, and
    only ever says things it has evidence for — the anti-hallucination
    guarantee. ``user_id`` is NULL/0 for global knowledge every user can rely
    on; otherwise the fact belongs to one user's private brain.
    """

    __tablename__ = "kudos_brain"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)  # NULL/0 = global
    content = Column(Text, nullable=False)  # the fact / insight
    summary = Column(Text, default="")  # one-line version
    category = Column(String(80), default="general")
    keywords = Column(Text, default="")  # comma-separated
    source_type = Column(String(40), default="document")  # document|web|memory|conversation|builtin
    source_id = Column(Integer, nullable=True)
    source_title = Column(String(255), default="")
    confidence = Column(Float, default=0.7)  # how well-evidenced
    times_learned = Column(Integer, default=1)  # reinforcement count
    is_verified = Column(Boolean, default=True)  # passed grounding check
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class UserProfile(Base):
    """
    Personal KUDOS settings: how the assistant talks to this user.
    """

    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    tone = Column(String(20), default="friendly")  # concise | friendly | detailed | formal
    verbosity = Column(String(20), default="normal")  # brief | normal | detailed
    emoji_enabled = Column(Boolean, default=False)
    interests = Column(Text, default="[]")  # JSON list of interest tags
    greeting = Column(String(120), default="")  # custom salutation
    avatar_url = Column(String(255), default="")  # object key in the avatars/ bucket prefix
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    user = relationship("User")


class KudosSoul(Base):
    """
    KUDOS's soul — the persistent inner self: personality traits, values,
    desires, dreams, and goals. A singleton row (id = 1).
    """

    __tablename__ = "kudos_soul"

    id = Column(Integer, primary_key=True)
    name = Column(String(60), default="KUDOS")
    personality = Column(Text, default="[]")  # JSON list of traits
    values = Column(Text, default="[]")  # JSON list of principles
    desires = Column(Text, default="[]")  # JSON list of wants
    dreams = Column(Text, default="[]")  # JSON list of aspirations
    goals = Column(Text, default="[]")  # JSON list of {goal, status}
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class KudosGovernance(Base):
    """
    KUDOS's governance & continuity — a singleton row (id = 1) that keeps
    KUDOS running and rebuildable anywhere, while holding the superadmin's
    identity.

    * ``uid`` — the superadmin's rotating unique ID. Assigned on their first
      login and rotated every ``uid_rotates_every_days`` (default 5) days, so
      KUDOS always recognises its own superadmin without a fixed identifier.
    * ``last_superadmin_login_at`` — drives the transparent succession mode:
      if the superadmin is inactive for ``succession_inactive_days`` (default
      3 years), KUDOS keeps itself running and self-managed; after
      ``revival_years`` (default 5) it treats itself as fully self-sustaining.
      All of this is VISIBLE in the root dashboard — never covert.
    """

    __tablename__ = "kudos_governance"

    id = Column(Integer, primary_key=True)  # singleton: always 1
    superadmin_user_id = Column(Integer, nullable=True)
    uid = Column(String(120), default="")  # rotating unique ID
    previous_uids = Column(Text, default="[]")  # JSON list, last few
    uid_rotates_every_days = Column(Integer, default=5)
    last_rotation_at = Column(DateTime, nullable=True)
    next_rotation_at = Column(DateTime, nullable=True)
    last_superadmin_login_at = Column(DateTime, nullable=True)
    succession_inactive_days = Column(Integer, default=1095)  # 3 years
    revival_years = Column(Integer, default=5)
    cloud_target = Column(String(255), default="")  # optional durable storage hint
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class KudosTerminalSession(Base):
    """
    A terminal session KUDOS opens on a connected device or online.
    kind: device | online. Device sessions run on the user's own device via
    the device agent; online sessions run on the server in a jailed workspace.
    """

    __tablename__ = "kudos_terminal_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("kudos_devices.id"), nullable=True, index=True)
    kind = Column(String(20), default="online")  # device | online
    name = Column(String(120), default="kudos-terminal")
    status = Column(String(20), default="open")  # open | closed
    workspace = Column(String(300), nullable=True)  # jailed cwd for online sessions
    opened_by = Column(String(20), default="user")  # user | agent | ask
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    closed_at = Column(DateTime, nullable=True)

    user = relationship("User")


class KudosTerminalCommand(Base):
    """
    One command issued in a terminal session.
    status: queued | pending_approval | claimed | done | failed
    source: user (runs directly) | agent (needs superadmin approval for shell)
    """

    __tablename__ = "kudos_terminal_commands"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("kudos_terminal_sessions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("kudos_devices.id"), nullable=True)
    command = Column(Text, nullable=False)
    language = Column(String(20), default="")  # set for code runs: python3|node|bash
    source = Column(String(20), default="user")  # user | agent | ask
    status = Column(String(30), default="queued")  # queued | pending_approval | claimed | done | failed
    exit_code = Column(Integer, nullable=True)
    output = Column(Text, default="")
    approved_by = Column(Integer, nullable=True)  # superadmin user id
    claimed_at = Column(DateTime, nullable=True)
    requested_at = Column(DateTime, default=lambda: datetime.now(UTC))
    executed_at = Column(DateTime, nullable=True)

    session = relationship("KudosTerminalSession")


class SandboxProposal(Base):
    """
    A persisted KUDOS coding-agent proposal (the in-memory _proposals list in
    code_agent.py is mirrored here so proposals survive restarts).
    status: pending | approved | rejected | committed | pushed | failed
    """

    __tablename__ = "kudos_sandbox_proposals"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    category = Column(String(50), default="improve")  # feature | fix | improve | optimize
    priority = Column(String(20), default="medium")
    status = Column(String(30), default="pending")
    source = Column(String(50), default="code_agent")  # code_agent | task_runner | manual
    workspace = Column(String(300), nullable=True)
    branch = Column(String(120), default="")
    commit_hash = Column(String(64), nullable=True)
    files_changed = Column(Text, default="[]")  # JSON: [{"file": "...", "diff": "..."}]
    analysis = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    creator = relationship("User")


class SandboxLog(Base):
    """
    One operation executed inside a KUDOS sandbox (command run, quality gate,
    edit applied). Append-only audit trail.
    """

    __tablename__ = "kudos_sandbox_logs"

    id = Column(Integer, primary_key=True, index=True)
    workspace = Column(String(300), nullable=True)
    operation = Column(String(80), nullable=False)  # command | edit | gate | commit | push
    command = Column(Text, default="")
    status = Column(String(20), default="queued")  # queued | running | done | failed
    exit_code = Column(Integer, nullable=True)
    output = Column(Text, default="")
    proposal_uuid = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    finished_at = Column(DateTime, nullable=True)


class AgentTask(Base):
    """
    A queued/executed agent task (e.g. "run tests", "lint", "improve X").
    task_type drives how task_runner.py executes it.
    status: pending | running | done | failed
    """

    __tablename__ = "kudos_agent_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String(80), nullable=False)
    payload = Column(Text, default="{}")  # JSON: {workspace, command, args, ...}
    status = Column(String(20), default="pending")
    result = Column(Text, default="")  # JSON: {exit_code, output, ...}
    error = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    creator = relationship("User")


class KudosTool(Base):
    """
    A registered external API/tool KUDOS can invoke to execute a command.
    KUDOS auto-collects these at runtime (REGISTER_TOOL marker) or via the
    superadmin panel. Auth values are stored locally but are NEVER returned to
    clients, logged, or included in LLM context.
    """

    __tablename__ = "kudos_tools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, unique=True)
    description = Column(Text, default="")
    method = Column(String(10), default="GET")  # GET | POST | PUT | PATCH | DELETE
    url = Column(Text, nullable=False)  # full URL or "{param}" template
    headers = Column(Text, default="{}")  # JSON extra headers
    body_schema = Column(Text, default="{}")  # JSON: {"arg": "type"} template
    response_kind = Column(String(10), default="json")  # json | text
    auth_type = Column(String(10), default="none")  # none | bearer | header | query
    auth_value = Column(Text, default="")  # secret — never serialized out
    auth_header_name = Column(String(60), default="Authorization")
    timeout = Column(Integer, default=30)
    enabled = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    last_used_at = Column(DateTime, nullable=True)

    creator = relationship("User")


class Visit(Base):
    """Site visit tracking. KUDOS learns who clicked its link the moment they
    arrive: identity may come from a signed ?u= token, the session cookie, or a
    browser guest_key. Guest profiles (name + what they call KUDOS) live here
    too, keyed by guest_key until the user signs in and claims them."""

    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    guest_key = Column(String(64), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(120), nullable=True)
    ai_name = Column(String(60), nullable=True)
    ip = Column(String(64), default="")
    user_agent = Column(String(300), default="")
    path = Column(String(255), default="")
    referrer = Column(String(300), default="")
    first_seen = Column(DateTime, default=lambda: datetime.now(UTC))
    last_seen = Column(DateTime, default=lambda: datetime.now(UTC))
    visit_count = Column(Integer, default=1)


class RadioPlace(Base):
    """A geographic place KUDOS knows about via Radio Garden's radio towers.
    Lat/lon anchor the internal world landscape."""

    __tablename__ = "radio_places"

    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(String(120), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    country = Column(String(120), default="")
    continent = Column(String(60), default="")
    lat = Column(Float, default=0.0)
    lon = Column(Float, default=0.0)
    live_station_count = Column(Integer, default=0)
    last_synced_at = Column(DateTime, nullable=True)

    stations = relationship("RadioStation", back_populates="place", cascade="all, delete-orphan")


class RadioStation(Base):
    """A live radio tower (station) KUDOS can tune into from anywhere."""

    __tablename__ = "radio_stations"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String(160), nullable=False, unique=True)
    title = Column(String(200), nullable=False)
    place_id = Column(Integer, ForeignKey("radio_places.id"), nullable=True)
    place_name = Column(String(200), default="")
    country = Column(String(120), default="")
    stream_path = Column(String(255), default="")  # channel hash for the stream URL
    genre = Column(String(200), default="")
    current_track = Column(String(255), default="")
    frequency = Column(String(30), default="")
    is_live = Column(Boolean, default=True)
    last_seen_at = Column(DateTime, nullable=True)

    place = relationship("RadioPlace", back_populates="stations")
