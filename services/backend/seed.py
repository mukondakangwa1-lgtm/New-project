"""
Digital Campus - Database Seed Script
Run: cd services/backend && .venv/bin/python seed.py
"""
from datetime import date, time, timedelta

from app.core.database import SessionLocal, init_db
from app.core.security import get_password_hash
from app.models import Course, Enrollment, Session as SessionModel, TimetableEntry, User

# Ensure tables exist
init_db()

db = SessionLocal()

# --- Seed admin user ---
admin_email = "admin@campus.edu"
if not db.query(User).filter(User.email == admin_email).first():
    admin = User(
        email=admin_email,
        full_name="Admin User",
        hashed_password=get_password_hash("admin123"),
        is_admin=True,
    )
    db.add(admin)
    print(f"✅ Created admin: {admin_email} / admin123")

# --- Seed sample student ---
student_email = "student@campus.edu"
if not db.query(User).filter(User.email == student_email).first():
    student = User(
        email=student_email,
        full_name="Jane Doe",
        hashed_password=get_password_hash("student123"),
    )
    db.add(student)
    print(f"✅ Created student: {student_email} / student123")

# --- Seed courses ---
courses_data = [
    {
        "code": "CS101",
        "title": "Introduction to Computer Science",
        "description": "Fundamentals of programming, algorithms, and data structures.",
        "instructor": "Dr. Alan Turing",
        "credits": 3,
    },
    {
        "code": "CS201",
        "title": "Data Structures & Algorithms",
        "description": "Trees, graphs, sorting, searching, and complexity analysis.",
        "instructor": "Dr. Grace Hopper",
        "credits": 4,
    },
    {
        "code": "MATH101",
        "title": "Calculus I",
        "description": "Limits, derivatives, integrals, and the fundamental theorem.",
        "instructor": "Prof. Ada Lovelace",
        "credits": 4,
    },
    {
        "code": "ENG101",
        "title": "Academic Writing",
        "description": "Essay structure, research methods, and critical analysis.",
        "instructor": "Prof. Chimamanda Adichie",
        "credits": 3,
    },
    {
        "code": "BUS101",
        "title": "Introduction to Business",
        "description": "Business models, marketing basics, and entrepreneurship.",
        "instructor": "Dr. Strive Masiyiwa",
        "credits": 3,
    },
]

for data in courses_data:
    if not db.query(Course).filter(Course.code == data["code"]).first():
        db.add(Course(**data))
        print(f"✅ Created course: {data['code']} — {data['title']}")

db.commit()

# --- Seed timetable entries ---
# Today's weekday (0=Mon .. 6=Sun)
today = date.today()
today_weekday = today.weekday()

# Create timetable entries for today's weekday so sessions can be generated
courses = db.query(Course).all()
course_map = {c.code: c for c in courses}

timetable_data = [
    {"code": "CS101", "day": today_weekday, "start": time(8, 0), "end": time(9, 30), "room": "Room 101"},
    {"code": "MATH101", "day": today_weekday, "start": time(10, 0), "end": time(11, 30), "room": "Room 203"},
    {"code": "ENG101", "day": today_weekday, "start": time(14, 0), "end": time(15, 0), "room": "Room 105"},
    # Also add entries for other days
    {"code": "CS201", "day": (today_weekday + 1) % 7, "start": time(9, 0), "end": time(10, 30), "room": "Lab A"},
    {"code": "BUS101", "day": (today_weekday + 2) % 7, "start": time(11, 0), "end": time(12, 30), "room": "Room 301"},
]

for data in timetable_data:
    course = course_map.get(data["code"])
    if not course:
        continue
    existing = (
        db.query(TimetableEntry)
        .filter(TimetableEntry.course_id == course.id, TimetableEntry.day_of_week == data["day"])
        .first()
    )
    if not existing:
        entry = TimetableEntry(
            course_id=course.id,
            day_of_week=data["day"],
            start_time=data["start"],
            end_time=data["end"],
            room=data["room"],
        )
        db.add(entry)
        print(f"✅ Timetable: {data['code']} {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][data['day']]} {data['start'].strftime('%H:%M')}-{data['end'].strftime('%H:%M')} ({data['room']})")

db.commit()

# --- Seed enrollments ---
student = db.query(User).filter(User.email == student_email).first()
if student:
    for course in courses:
        existing = (
            db.query(Enrollment)
            .filter(Enrollment.student_id == student.id, Enrollment.course_id == course.id)
            .first()
        )
        if not existing:
            db.add(Enrollment(student_id=student.id, course_id=course.id))
            print(f"✅ Enrolled {student.full_name} in {course.code}")

db.commit()

# --- Generate sessions for today and tomorrow ---
entries = db.query(TimetableEntry).filter(TimetableEntry.is_active == True).all()
for delta in [0, 1]:
    target = today + timedelta(days=delta)
    weekday = target.weekday()
    for entry in entries:
        if entry.day_of_week != weekday:
            continue
        existing = (
            db.query(SessionModel)
            .filter(
                SessionModel.timetable_entry_id == entry.id,
                SessionModel.session_date == target,
            )
            .first()
        )
        if not existing:
            course = db.query(Course).filter(Course.id == entry.course_id).first()
            session = SessionModel(
                timetable_entry_id=entry.id,
                course_id=entry.course_id,
                session_date=target,
                start_time=entry.start_time,
                end_time=entry.end_time,
                room=entry.room,
                is_open=(delta == 0),  # Open today's sessions
            )
            db.add(session)
            day_label = "Today" if delta == 0 else "Tomorrow"
            print(f"✅ Session: {course.code} {day_label} {entry.start_time.strftime('%H:%M')}-{entry.end_time.strftime('%H:%M')} (open={delta == 0})")

db.commit()
db.close()
print("\n🎉 Database seeded successfully!")
