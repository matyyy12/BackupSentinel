from celery import Celery

app = Celery(
    broker="redis://redis:6379/0",
    include=["monitoring_app.tasks"],
)

app.conf.task_routes = {"monitoring": {"queue": "monitoring"}}
app.conf.beat_schedule = {
    "check-backups-every-30-seconds":{
        "task": "monitoring",
        "schedule": 30.0,
    }
}