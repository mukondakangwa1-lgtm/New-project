"""
Digital Campus - Pydantic Schemas
"""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str
    is_student: bool = False
    school: str | None = None


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_admin: bool
    is_approved: bool
    is_student: bool
    school: str | None = None
    created_at: datetime


class UserLogin(BaseModel):
    email: EmailStr
    password: str


# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: str | None = None


# --- Course Schemas ---
class CourseBase(BaseModel):
    title: str
    code: str
    description: str = ""
    instructor: str = ""
    credits: int = 3


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    instructor: str | None = None
    credits: int | None = None


class CourseResponse(CourseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


# --- Enrollment Schemas ---
class EnrollmentCreate(BaseModel):
    student_id: int
    course_id: int


class EnrollmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    course_id: int
    enrolled_at: datetime
    grade: str


# --- Timetable Schemas ---
class TimetableEntryBase(BaseModel):
    course_id: int
    day_of_week: int  # 0=Mon .. 6=Sun
    start_time: time
    end_time: time
    room: str = ""


class TimetableEntryCreate(TimetableEntryBase):
    pass


class TimetableEntryUpdate(BaseModel):
    day_of_week: int | None = None
    start_time: time | None = None
    end_time: time | None = None
    room: str | None = None
    is_active: bool | None = None


class TimetableEntryResponse(TimetableEntryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime


class TimetableEntryWithCourse(TimetableEntryResponse):
    course: CourseResponse | None = None


# --- Session Schemas ---
class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timetable_entry_id: int
    course_id: int
    session_date: date
    start_time: time
    end_time: time
    room: str
    is_open: bool
    is_cancelled: bool
    created_at: datetime


class SessionWithCourse(SessionResponse):
    course: CourseResponse | None = None


class SessionOpenClose(BaseModel):
    is_open: bool


class SessionBulkGenerate(BaseModel):
    """Generate sessions for a date range."""

    start_date: date
    end_date: date
    course_id: int | None = None  # None = all courses


class SessionBulkGenerateResponse(BaseModel):
    sessions_created: int
    start_date: date
    end_date: date


# --- Attendance Schemas ---
class AttendanceCheckIn(BaseModel):
    session_id: int
    status: str = "present"  # present, late
    notes: str = ""


class AttendanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    student_id: int
    checked_in_at: datetime
    status: str
    notes: str


class AttendanceWithStudent(AttendanceResponse):
    student: UserResponse | None = None


class AttendanceMark(BaseModel):
    """Admin marks attendance for a student."""

    student_id: int
    status: str = "present"  # present, late, absent, excused
    notes: str = ""


class AttendanceReport(BaseModel):
    """Summary for a student in a course."""

    student: UserResponse
    course: CourseResponse
    total_sessions: int
    present: int
    late: int
    absent: int
    excused: int
    attendance_rate: float  # percentage


# --- Health Check ---
class HealthCheck(BaseModel):
    status: str
    version: str
    message: str


# ──────────────────────────────────────────────
# SOCIAL HUB SCHEMAS
# ──────────────────────────────────────────────


class PostBase(BaseModel):
    title: str
    description: str = ""
    storage_url: str
    storage_type: str = "link"  # link, gdrive, dropbox, onedrive, s3, youtube, image
    content_type: str = ""  # image, video, document, audio
    thumbnail_url: str = ""
    is_public: bool = True
    tags: str = ""


class PostCreate(PostBase):
    pass


class PostUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    storage_url: str | None = None
    storage_type: str | None = None
    content_type: str | None = None
    thumbnail_url: str | None = None
    is_public: bool | None = None
    tags: str | None = None


class PostResponse(PostBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    view_count: int
    created_at: datetime
    updated_at: datetime


class PostWithAuthor(PostResponse):
    author: UserResponse | None = None
    reaction_count: int = 0
    comment_count: int = 0


class CommentCreate(BaseModel):
    content: str


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    user_id: int
    content: str
    created_at: datetime


class CommentWithAuthor(CommentResponse):
    user: UserResponse | None = None


class ReactionCreate(BaseModel):
    emoji: str = "👍"


class ReactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    user_id: int
    emoji: str
    created_at: datetime


# ──────────────────────────────────────────────
# CHAT SCHEMAS
# ──────────────────────────────────────────────


class ChatRoomCreate(BaseModel):
    name: str
    is_group: bool = False
    member_ids: list[int] = []  # user IDs to add


class ChatRoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_group: bool
    created_by: int
    created_at: datetime


class ChatRoomWithMembers(ChatRoomResponse):
    members: list = []


class ChatMessageCreate(BaseModel):
    content: str
    message_type: str = "text"  # text, image, file, link
    is_offline: bool = False


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    user_id: int
    content: str
    message_type: str
    is_offline: bool
    created_at: datetime


class ChatMessageWithUser(ChatMessageResponse):
    user: UserResponse | None = None


class ChatSyncPayload(BaseModel):
    """For syncing offline messages when coming back online."""

    messages: list[ChatMessageCreate]
    room_id: int


# ──────────────────────────────────────────────
# KUDOS AI SCHEMAS
# ──────────────────────────────────────────────


class KudosDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uploaded_by: int
    title: str
    filename: str
    file_type: str
    summary: str
    tags: str
    is_approved: bool
    is_active: bool
    chunk_count: int
    created_at: datetime


class KudosDocumentUpdate(BaseModel):
    title: str | None = None
    tags: str | None = None
    is_approved: bool | None = None
    is_active: bool | None = None


class KudosWebLearn(BaseModel):
    url: str
    title: str = ""


class KudosWebKnowledgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: str
    summary: str
    is_approved: bool
    is_active: bool
    learned_by: int
    created_at: datetime


class KudosAskRequest(BaseModel):
    question: str
    conversation_id: int | None = None


class GuestAskRequest(BaseModel):
    """Public ask from an anonymous visitor (no login required)."""

    question: str
    guest_id: str = Field(min_length=8, max_length=64, description="Browser-generated anonymous id (UUID)")


class KudosAskResponse(BaseModel):
    answer: str
    sources: list[dict] = []  # [{document_id, title, chunk_preview}]
    conversation_id: int
    media: list[dict] = []  # [{kind: image|video, url, mime, caption}] generated in this answer


class ChatSendResponse(BaseModel):
    answer: str
    conversation_id: int
    learned: list[dict] = []  # what KUDOS ingested from attachments
    media: list[dict] = []  # generated/sent media to render


class ToolRegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    method: str = "GET"
    url: str
    headers: str = "{}"
    body_schema: str = "{}"
    auth_type: str = "none"
    auth_value: str = ""
    auth_header_name: str = "Authorization"


class ToolCallRequest(BaseModel):
    tool_id: int
    args: dict = {}


class VisitRecord(BaseModel):
    guest_id: str = ""
    path: str = ""
    referrer: str = ""
    share_token: str = ""  # signed ?u= identity token


class GuestProfileUpdate(BaseModel):
    guest_id: str = Field(min_length=8, max_length=64)
    name: str = ""
    ai_name: str = ""


class GuestProfileResponse(BaseModel):
    guest_id: str
    name: str = ""
    ai_name: str = ""
    visit_count: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class MemoryCreate(BaseModel):
    """Write a memory KUDOS should keep."""

    content: str = Field(min_length=1, max_length=5000)
    layer: str = "short_term"  # short_term | long_term | knowledge | system
    kind: str = "fact"  # fact | preference | concept | event | rule | error | success | context
    importance: float = 0.5
    tags: list[str] = []
    source: str = Field(default="", max_length=120)
    expires_at: datetime | None = None


class MemoryResponse(BaseModel):
    id: int
    layer: str
    kind: str
    content: str
    summary: str = ""
    importance: float
    tags: list[str] = []
    source: str = ""
    access_count: int = 0
    expires_at: datetime | None = None
    created_at: datetime | None = None
    replicas: list[dict] = []


class MemoryRetrieveResponse(BaseModel):
    query: str
    memories: list[MemoryResponse]


class MemoryClearResponse(BaseModel):
    deleted: int


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    platform: str = Field(default="generic", max_length=30)
    storage_bytes: int = Field(default=512 * 1024 * 1024, ge=1)


class DeviceResponse(BaseModel):
    id: int
    name: str
    platform: str
    status: str
    storage_bytes: int
    used_storage_bytes: int
    last_seen_at: datetime | None = None
    api_token: str = ""


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    status: str | None = Field(default=None, max_length=20)  # online | offline
    used_storage_bytes: int | None = Field(default=None, ge=0)


class SyncAckRequest(BaseModel):
    memory_ids: list[int]


class SyncAckResponse(BaseModel):
    acknowledged: int


class SyncEntry(BaseModel):
    memory_id: int
    content: str
    layer: str
    kind: str
    importance: float
    tags: str = "[]"
    source: str = ""
    summary: str = ""
    expires_at: datetime | None = None
    device_role: str = "replica"
    device_status: str = "pending"
    embedding: list | None = None


class SyncManifestResponse(BaseModel):
    device_id: int
    entries: list[SyncEntry]


class SyncStatusResponse(BaseModel):
    devices: list[dict]
    total_memories: int
    healthy_replicated: int
    last_check: str


class ProfileUpdate(BaseModel):
    tone: str | None = Field(default=None, max_length=20)
    verbosity: str | None = Field(default=None, max_length=20)
    emoji_enabled: bool | None = None
    interests: list[str] | None = None
    greeting: str | None = Field(default=None, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=255)


class ProfileResponse(BaseModel):
    tone: str
    verbosity: str
    emoji_enabled: bool
    interests: list[str] = []
    greeting: str = ""
    avatar_url: str = ""


class SoulUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    personality: list[str] | None = None
    values: list[str] | None = None
    desires: list[str] | None = None
    dreams: list[str] | None = None
    goals: list[dict] | None = None


class SoulResponse(BaseModel):
    name: str
    personality: list[str] = []
    values: list[str] = []
    desires: list[str] = []
    dreams: list[str] = []
    goals: list[dict] = []


class LLMConfigureRequest(BaseModel):
    """Configure a provider for the current process.

    Production deployments should set provider keys through the environment
    or a secret manager. This endpoint is intended for local/LAN admin use and
    keeps the key out of URLs and access logs.
    """

    provider: str = Field(min_length=1, max_length=50)
    api_key: str = Field(min_length=1, max_length=500)


class KudosConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    archived: bool = False
    created_at: datetime


class KudosMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    sources: str
    media: str = ""
    created_at: datetime


class KudosStats(BaseModel):
    total_documents: int
    approved_documents: int
    total_chunks: int
    total_web_knowledge: int
    total_conversations: int
    total_messages: int
    total_connectors: int = 0
    total_knowledge_packs: int = 0


# ──────────────────────────────────────────────
# KUDOS CONNECTOR SCHEMAS
# ──────────────────────────────────────────────


class KudosConnectorCreate(BaseModel):
    name: str
    connector_type: str  # github, gitlab, website, api, rss, npm, pypi
    source_url: str
    config: str = "{}"  # JSON string with options


class KudosConnectorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: int
    name: str
    connector_type: str
    source_url: str
    config: str
    status: str
    last_synced_at: datetime | None = None
    items_learned: int
    error_message: str
    is_approved: bool
    created_at: datetime


class KudosSyncLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    connector_id: int
    action: str
    items_found: int
    items_new: int
    items_updated: int
    details: str
    created_at: datetime


class KudosSyncResult(BaseModel):
    connector_id: int
    items_found: int
    items_new: int
    items_updated: int
    details: str


# ──────────────────────────────────────────────
# KUDOS KNOWLEDGE PACK SCHEMAS
# ──────────────────────────────────────────────


class KudosPackCreate(BaseModel):
    name: str
    description: str = ""
    is_shared: bool = False


class KudosPackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: int
    name: str
    description: str
    item_count: int
    size_bytes: int
    is_shared: bool
    created_at: datetime


class KudosPackImport(BaseModel):
    pack_id: int
