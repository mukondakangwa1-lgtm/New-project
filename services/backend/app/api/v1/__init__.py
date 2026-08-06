"""
Digital Campus API v1 - API Router
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    health, auth, users, courses, timetable, social, chat,
    kudos, connectors, guardian, search_connectors, arena, social_learning, llm_api,
    assignments, study_groups, calendar_goals, exams, analytics, code_agent,
    internet_archive, auto_learner, speaking,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(courses.router, prefix="/courses", tags=["Courses"])
api_router.include_router(timetable.router, prefix="/register", tags=["Register & Attendance"])
api_router.include_router(social.router, prefix="/social", tags=["Social Hub"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(kudos.router, prefix="/kudos", tags=["KUDOS AI"])
api_router.include_router(connectors.router, prefix="/kudos/connectors", tags=["KUDOS Connectors"])
api_router.include_router(guardian.router, prefix="/kudos/guardian", tags=["KUDOS Guardian"])
api_router.include_router(search_connectors.router, prefix="/kudos/search", tags=["KUDOS Search"])
api_router.include_router(arena.router, prefix="/kudos/arena", tags=["KUDOS Arena AI"])
api_router.include_router(social_learning.router, prefix="/kudos/social", tags=["KUDOS Social Learning"])
api_router.include_router(llm_api.router, prefix="/kudos/llm", tags=["KUDOS LLM"])
api_router.include_router(assignments.router, prefix="/academic", tags=["Assignments & Grades"])
api_router.include_router(study_groups.router, prefix="/groups", tags=["Study Groups & Forums"])
api_router.include_router(calendar_goals.router, prefix="/planner", tags=["Calendar & Goals"])
api_router.include_router(exams.router, prefix="/exams", tags=["Exams & Quizzes"])
api_router.include_router(analytics.router, prefix="/admin/analytics", tags=["Admin Analytics"])
api_router.include_router(code_agent.router, prefix="/kudos/agent", tags=["KUDOS Code Agent"])
api_router.include_router(internet_archive.router, prefix="/kudos/archive", tags=["Internet Archive"])
api_router.include_router(auto_learner.router, prefix="/kudos/learn", tags=["KUDOS Auto-Learner"])
api_router.include_router(speaking.router, prefix="/studio", tags=["Speaking & Broadcasting"])
