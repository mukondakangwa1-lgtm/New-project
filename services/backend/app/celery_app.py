"""
Minimal Celery app configuration for Digital Campus.
This file registers a Celery instance and autodiscovers tasks within the app package.
Replace task implementations in app.tasks when adding connector syncs, crawlers, or long-running jobs.
"""
import os
from celery import Celery

REDIS_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://redis:6379/0"))

celery = Celery(
    "digital_campus",
    broker=REDIS_URL,
)

# Optional: load backend-specific config from env
celery.conf.update(
    result_backend=os.getenv("CELERY_RESULT_BACKEND", REDIS_URL),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Auto-discover tasks in installed apps (looks for tasks.py modules)
celery.autodiscover_tasks(['app'])
