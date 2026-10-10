from celery import Celery

app = Celery(broker="redis://redis:6379/0", include=["backup_app.tasks"])
app.conf.task_routes = {
    "verification_restore": {"queue": "verification"}
}