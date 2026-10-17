import asyncio
import datetime
import os
import logging

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from starlette.concurrency import run_in_threadpool

from backup_app.celery_app import app
from backup_app.repository import OutboxRepository


logger = logging.getLogger(__name__)


async def publish_pending() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as session:
            repository = OutboxRepository(session)
            tasks = await repository.get_pending()
            if tasks:
                for task in tasks:
                    try:
                        await run_in_threadpool(app.send_task, task.task_name, kwargs=task.payload)
                        task.sent_at = datetime.datetime.now(datetime.timezone.utc)
                        await repository.commit()
                    except Exception:
                        await repository.rollback()
                        raise
    finally:
        await engine.dispose()

async def main() -> None:
    while True:
        try:
            await publish_pending()
        except Exception:
            logger.exception("Failed to publish pending backups")
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())