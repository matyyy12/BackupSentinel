import asyncio
import logging
from datetime import datetime, timezone

from starlette.concurrency import run_in_threadpool

from verification_app.celery_app import app
from verification_app.database import session_scope
from verification_app.repository import VerificationResultOutboxRepository

logger = logging.getLogger(__name__)


async def publish_pending() -> int:
    async with session_scope() as session:
        pending = await VerificationResultOutboxRepository(session).get_pending()
        for result in pending:
            await run_in_threadpool(
                app.send_task, "backup_results", kwargs={"request": result.payload},
            )
            result.sent_at = datetime.now(timezone.utc)
        return len(pending)


async def main() -> None:
    while True:
        try:
            await publish_pending()
        except Exception:
            logger.exception("Failed to publish verification results")
        await asyncio.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
