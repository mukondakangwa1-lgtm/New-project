"""
Digital Campus - Pydantic Schemas
"""
from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional
from datetime import date, datetime, time


# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime


class UserLogin(BaseModel):
    email: EmailStr
    password: str


# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


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
    title: Optional[str] = None
    description: Optional[str] = None
    instructor: Optional[str] = None
    credits: Optional[int] = None


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
    day_of_week: Optional[int] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    room: Optional[str] = None
    is_active: Optional[bool] = None


class TimetableEntryResponse(TimetableEntryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime


class TimetableEntryWithCourse(TimetableEntryResponse):
    course: Optional[CourseResponse] = None


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
    course: Optional[CourseResponse] = None


class SessionOpenClose(BaseModel):
    is_open: bool


class SessionBulkGenerate(BaseModel):
    """Generate sessions for a date range."""
    start_date: date
    end_date: date
    course_id: Optional[int] = None  # None = all courses


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
    student: Optional[UserResponse] = None


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
    storage_type: str = "link"  # connected: s3 (MinIO/R2), link, youtube, image | dead gdrive/dropbox/onedrive removed -> use s3
    content_type: str = ""  # image, video, document, audio
    thumbnail_url: str = ""
    is_public: bool = True
    tags: str = ""


class PostCreate(PostBase):
    pass


class PostUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    storage_url: Optional[str] = None
    storage_type: Optional[str] = None
    content_type: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_public: Optional[bool] = None
    tags: Optional[str] = None


class PostResponse(PostBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    view_count: int
    created_at: datetime
    updated_at: datetime


class PostWithAuthor(PostResponse):
    author: Optional[UserResponse] = None
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
    user: Optional[UserResponse] = None


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
    user: Optional[UserResponse] = None


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
    title: Optional[str] = None
    tags: Optional[str] = None
    is_approved: Optional[bool] = None
    is_active: Optional[bool] = None


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
    conversation_id: Optional[int] = None


class KudosAskResponse(BaseModel):
    answer: str
    sources: list[dict] = []  # [{document_id, title, chunk_preview}]
    conversation_id: int


class KudosConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    created_at: datetime


class KudosMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    sources: str
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
    last_synced_at: Optional[datetime] = None
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
