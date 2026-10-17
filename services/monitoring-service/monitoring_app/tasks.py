import asyncio

from monitoring_app.celery_app import app
from monitoring_app.monitor import monitor

@app.task(name="monitoring")
def monitoring():
    asyncio.run(monitor())