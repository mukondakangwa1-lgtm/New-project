"""
Digital Campus - Course Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models import Course, Enrollment, User
from app.schemas import (
    CourseCreate,
    CourseResponse,
    CourseUpdate,
    EnrollmentCreate,
    EnrollmentResponse,
)

router = APIRouter()


# --- Courses CRUD ---


@router.get("/", response_model=list[CourseResponse])
def list_courses(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all courses (authenticated users only)."""
    return db.query(Course).offset(skip).limit(limit).all()


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a specific course by ID."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.post("/", response_model=CourseResponse, status_code=201)
def create_course(
    course_in: CourseCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Create a new course (admin only)."""
    existing = db.query(Course).filter(Course.code == course_in.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Course code '{course_in.code}' already exists",
        )
    course = Course(**course_in.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.patch("/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: int,
    course_in: CourseUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update a course (admin only)."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    for field, value in course_in.model_dump(exclude_unset=True).items():
        setattr(course, field, value)

    db.commit()
    db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=204)
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete a course (admin only)."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(course)
    db.commit()


# --- Enrollments ---


@router.post("/enroll", response_model=EnrollmentResponse, status_code=201)
def enroll_student(
    enrollment_in: EnrollmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enroll a student in a course. Students enroll themselves; admins may
    enroll any student."""
    student_id = enrollment_in.student_id
    if student_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only enroll yourself",
        )
    # Verify student exists
    student = db.query(User).filter(User.id == enrollment_in.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Verify course exists
    course = db.query(Course).filter(Course.id == enrollment_in.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Check duplicate enrollment
    existing = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == enrollment_in.student_id,
            Enrollment.course_id == enrollment_in.course_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student already enrolled in this course",
        )

    enrollment = Enrollment(**enrollment_in.model_dump())
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


@router.get("/enrollments/{course_id}", response_model=list[EnrollmentResponse])
def list_enrollments(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List enrollments for a course — enrolled students or admins only."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if not current_user.is_admin:
        enrolled = (
            db.query(Enrollment)
            .filter(
                Enrollment.course_id == course_id,
                Enrollment.student_id == current_user.id,
            )
            .first()
        )
        if not enrolled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not enrolled in this course",
            )
    return (
        db.query(Enrollment).filter(Enrollment.course_id == course_id).all()
    )
