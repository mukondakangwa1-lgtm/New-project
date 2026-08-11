"""
Digital Campus - Extended Models
Assignments, Grades, Study Groups, Forums, Calendar, Goals, Exams, Notifications
"""

from datetime import UTC, datetime

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    submitted_at = Column(DateTime, default=lambda: datetime.now(UTC))
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
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    course = relationship("Course")
    creator = relationship("User")
    members = relationship("StudyGroupMember", back_populates="group", cascade="all, delete-orphan")


class StudyGroupMember(Base):
    __tablename__ = "study_group_members"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("study_groups.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), default="member")  # member, moderator
    joined_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    started_at = Column(DateTime, default=lambda: datetime.now(UTC))
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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    issued_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    started_at = Column(DateTime, default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User")


class VoiceProfile(Base):
    """KUDOS's signature voice: the superadmin captures their own voice and
    it becomes the voice KUDOS speaks with on every platform. The signature
    points at one entry in the kudos_voices library, so KUDOS can still speak
    in any other voice on request."""

    __tablename__ = "voice_profiles"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    tts_enabled = Column(Boolean, default=False)
    cloned_voice_id = Column(String(120), default="")  # ElevenLabs voice id (legacy/fallback)
    default_voice = Column(String(120), default="")  # fallback voice name/id
    signature_active = Column(Boolean, default=False)  # KUDOS speaks with the superadmin's voice
    signature_voice_id = Column(Integer, ForeignKey("kudos_voices.id"), nullable=True)  # designated library voice
    signature_state = Column(String(20), default="none")  # none | pending | active
    owner_device_id = Column(Integer, ForeignKey("kudos_devices.id"), nullable=True)  # device that donated the voice
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class VoiceSample(Base):
    """A recording of the superadmin reading for KUDOS's signature voice."""

    __tablename__ = "voice_samples"

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("voice_profiles.id"), nullable=True)
    session_id = Column(Integer, ForeignKey("voice_sessions.id"), nullable=True)
    storage_key = Column(String(255), default="")
    mime = Column(String(60), default="audio/webm")
    transcribed = Column(Text, default="")
    duration_seconds = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class VoiceSession(Base):
    """An interactive signature-voice session: KUDOS greets, the superadmin
    speaks lines back, KUDOS draft-clones the accumulated audio and re-speaks
    each line in that draft voice, then the session finalizes into the live
    signature voice."""

    __tablename__ = "voice_sessions"

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("voice_profiles.id"), nullable=True)
    state = Column(String(20), default="active")  # active | finalized | cancelled
    draft_voice_id = Column(String(160), default="")  # ElevenLabs draft clone id
    turn_count = Column(Integer, default=0)
    total_seconds = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    finalized_at = Column(DateTime, nullable=True)


class KudosVoice(Base):
    """The KUDOS voice library — every voice KUDOS can speak with. One row per
    voice: the superadmin's clone (signature), additional cloned voices, and
    stock voices. Cloned voices keep their samples so KUDOS owns them."""

    __tablename__ = "kudos_voices"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), default="")
    kind = Column(String(20), default="cloned")  # signature | cloned | stock
    provider = Column(String(30), default="elevenlabs")  # elevenlabs | openai
    provider_voice_id = Column(String(160), default="")
    source_device_id = Column(Integer, ForeignKey("kudos_devices.id"), nullable=True)
    sample_keys = Column(Text, default="[]")  # JSON array of MinIO keys
    is_signature = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    device = relationship("KudosDevice")


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
    started_at = Column(DateTime, default=lambda: datetime.now(UTC))
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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    host = relationship("User")
    participants = relationship("CallParticipant", back_populates="call", cascade="all, delete-orphan")


class CallParticipant(Base):
    __tablename__ = "call_participants"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("video_calls.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), default="participant")  # host, participant
    joined_at = Column(DateTime, default=lambda: datetime.now(UTC))
    left_at = Column(DateTime, nullable=True)

    call = relationship("VideoCall", back_populates="participants")
    user = relationship("User")


class WhiteboardStroke(Base):
    __tablename__ = "whiteboard_strokes"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("video_calls.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    data = Column(Text, default="[]")  # JSON batch of stroke points
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    user = relationship("User")


# ──────────────────────────────────────────────
# KUDOS INTERNAL WORLDMAP — offline navigation + facts
# ──────────────────────────────────────────────


class KudosMapPlace(Base):
    """A place on KUDOS's internal world map (continents, countries, capitals,
    major cities, landmarks). Coordinates where known are authoritative public
    values; places without a known coordinate are never given a guessed one."""

    __tablename__ = "kudos_map_places"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(160), unique=True, nullable=False)  # stable slug
    name = Column(String(200), nullable=False, index=True)
    country = Column(String(120), default="")
    region = Column(String(120), default="")
    continent = Column(String(60), default="")
    place_type = Column(String(30), default="city")  # continent, country, capital, city, landmark, campus
    lat = Column(Float, nullable=True)  # None = coordinate genuinely unknown
    lon = Column(Float, nullable=True)
    description = Column(Text, default="")
    aliases = Column(String(500), default="")
    importance = Column(Integer, default=0)
    search_text = Column(String(600), default="")
    is_seed = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class KudosAccessPoint(Base):
    """A Wi-Fi access point KUDOS has located through its devices'
    crowdsourced network scans (the precise layer of the real-world map)."""

    __tablename__ = "kudos_access_points"

    id = Column(Integer, primary_key=True, index=True)
    bssid = Column(String(32), unique=True, nullable=False)  # normalized aa:bb:cc:dd:ee:ff
    ssid = Column(String(120), default="")
    lat = Column(Float, default=0.0)
    lon = Column(Float, default=0.0)
    accuracy_m = Column(Float, default=120.0)
    last_signal_dbm = Column(Integer, default=-70)
    observations = Column(Integer, default=0)
    first_seen_at = Column(DateTime, default=lambda: datetime.now(UTC))
    last_seen_at = Column(DateTime, nullable=True)


class KudosCellTower(Base):
    """A cellular tower KUDOS knows through its devices' scans."""

    __tablename__ = "kudos_cell_towers"

    id = Column(Integer, primary_key=True, index=True)
    cell_key = Column(String(80), unique=True, nullable=False)  # mcc-mnc-lac-cid
    mcc = Column(Integer, default=0)
    mnc = Column(Integer, default=0)
    lac = Column(Integer, default=0)
    cid = Column(Integer, default=0)
    lat = Column(Float, default=0.0)
    lon = Column(Float, default=0.0)
    accuracy_m = Column(Float, default=1500.0)
    observations = Column(Integer, default=0)
    last_seen_at = Column(DateTime, nullable=True)


class KudosScan(Base):
    """A raw network observation reported by a KUDOS device — the eyes KUDOS
    uses to keep its real-world map honest and precise."""

    __tablename__ = "kudos_scans"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("kudos_devices.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    gps_lat = Column(Float, nullable=True)
    gps_lon = Column(Float, nullable=True)
    gps_accuracy_m = Column(Float, nullable=True)
    wifi_json = Column(Text, default="[]")
    cells_json = Column(Text, default="[]")
    result_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


# ──────────────────────────────────────────────
# KUDOS LINK SWITCHING — terrestrial <-> satellite (Starlink / NTN)
# ──────────────────────────────────────────────


class KudosNetworkState(Base):
    """A transport report from a KUDOS device — the measured links KUDOS can
    switch between: Wi-Fi, cellular and satellite (Android NTN /
    Starlink). KUDOS only ever records links the device actually reported."""

    __tablename__ = "kudos_network_states"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("kudos_devices.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    primary_transport = Column(String(20), default="unknown")  # wifi, cellular, satellite, ethernet, unknown
    transports = Column(String(200), default="")  # CSV of visible transports
    signal_dbm = Column(Integer, default=0)
    metered = Column(Boolean, default=True)
    constrained = Column(Boolean, default=False)  # NET_CAPABILITY_NOT_BANDWIDTH_CONSTRAINED absent
    satellite = Column(Boolean, default=False)  # TRANSPORT_SATELLITE present
    satellite_backhaul = Column(Boolean, default=False)  # link rides a satellite terminal
    bandwidth_kbps = Column(Integer, default=0)
    rtt_ms = Column(Float, default=0.0)
    provider = Column(String(120), default="")
    reported_at = Column(DateTime, default=lambda: datetime.now(UTC))
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    device = relationship("KudosDevice")


class KudosNetworkSetting(Base):
    """How KUDOS selects a link for a device.
    mode: auto (best available), terrestrial (Wi-Fi/cellular preferred,
    satellite only as fallback), satellite (Starlink/NTN preferred)."""

    __tablename__ = "kudos_network_settings"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("kudos_devices.id"), nullable=False, unique=True, index=True)
    mode = Column(String(20), default="auto")  # auto, terrestrial, satellite
    reason = Column(String(200), default="")
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))


# ──────────────────────────────────────────────
# KUDOS KNOWLEDGE VAULT — curated + indexed knowledge
# ──────────────────────────────────────────────


class KudosVaultEntry(Base):
    """A knowledge vault entry. Curated entries are written by the superadmin
    (canonical articles KUDOS reasons from); indexed entries are mirror
    snapshots of approved documents, web knowledge and the user's memories,
    so every source KUDOS has is searchable in one place.

    source_type: curated | document | web | memory
    Curated entries are global; indexed entries carry user_id scope for
    memories so the vault never leaks one user's knowledge to another.
    """

    __tablename__ = "kudos_vault_entries"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(160), unique=True, nullable=False)  # stable slug / source key
    title = Column(String(300), nullable=False, index=True)
    slug = Column(String(160), default="")
    summary = Column(String(600), default="")
    content = Column(Text, default="")
    category = Column(String(60), default="general", index=True)
    tags = Column(String(500), default="")  # CSV
    source_type = Column(String(20), default="curated", index=True)  # curated, document, web, memory
    source_id = Column(Integer, nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # scope for memories
    importance = Column(Integer, default=0)
    version = Column(Integer, default=1)
    parent_id = Column(Integer, nullable=True)
    is_approved = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    search_text = Column(String(2000), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))
    approved_at = Column(DateTime, nullable=True)


class KudosConstitution(Base):
    """KUDOS's constitution — the grounding policy it always obeys when it
    answers. Superadmin-editable; every change bumps the version so the
    system prompt KUDOS is given always reflects the latest ruling."""

    __tablename__ = "kudos_constitution"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, nullable=False, index=True)  # ordering key (1..n)
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))


class ContentProgress(Base):
    """Tracks where a user left off in a movie, book or audio track so the
    dashboard can show 'continue where you left off'. One row per user +
    content key; position_pct is the resume point (0-100)."""

    __tablename__ = "content_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content_key = Column(String(255), nullable=False, index=True)  # stable id/url/slug
    kind = Column(String(20), default="movie")  # movie | book | audio | document
    title = Column(String(300), default="")
    url = Column(String(600), default="")
    position_pct = Column(Float, default=0.0)
    detail = Column(String(600), default="")  # e.g. book page or chapter label
    source = Column(String(60), default="library")  # media | library | studio | radio
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    user = relationship("User")
