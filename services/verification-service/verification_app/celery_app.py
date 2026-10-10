from celery import Celery

app = Celery(broker="redis://redis:6379/0", include=["verification_app.tasks"])
app.conf.task_routes = {"backup_results": {"queue": "backup"}}