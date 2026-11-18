from celery import Celery

app = Celery(broker="redis://redis:6379/0", include=["backup_app.tasks"])
app.conf.task_routes = {
    "verification_restore": {"queue": "verification"}
}
app.conf.update(
    broker_transport_options={"visibility_timeout": 600},
    result_backend_transport_options={"visibility_timeout": 600},
    visibility_timeout=600,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_soft_shutdown_timeout=30,
    worker_enable_soft_shutdown_on_idle=True,
)
