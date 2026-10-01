from celery import Celery
from app.config import settings
celery_app = Celery("socialscope", broker=settings.REDIS_URL, backend=settings.REDIS_URL,
                    include=["app.workers.tasks"])
celery_app.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json",
    timezone="UTC", enable_utc=True, task_track_started=True, task_acks_late=True,
    worker_prefetch_multiplier=1, worker_concurrency=settings.COLLECTION_WORKER_CONCURRENCY,
    task_routes={"app.workers.tasks.run_collection_job": {"queue": "collection"}, "app.workers.tasks.reconcile_abandoned_collection_jobs": {"queue":"default"}},
    beat_schedule={"reconcile-abandoned-collection-jobs": {
        "task": "app.workers.tasks.reconcile_abandoned_collection_jobs",
        "schedule": settings.COLLECTION_ABANDONED_RECONCILE_INTERVAL_SECONDS,
        "options": {"expires": settings.COLLECTION_ABANDONED_RECONCILE_INTERVAL_SECONDS}}})
