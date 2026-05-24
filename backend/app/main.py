import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

import app.models as models
from app.api.router import api_router
from app.api.routes.chats import cleanup_expired_chat_attachments_once
from app.core.config import get_settings
from app.database import get_engine
from app.services.contribution.queue import contribution_assessment_queue

settings = get_settings()
logger = logging.getLogger("uvicorn.error")
KST = timezone(timedelta(hours=9))


def _seconds_until_next_chat_attachment_cleanup() -> float:
    now = datetime.now(KST)
    next_run = now.replace(hour=0, minute=10, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return max((next_run - now).total_seconds(), 1.0)


async def _chat_attachment_cleanup_scheduler() -> None:
    while True:
        await asyncio.sleep(_seconds_until_next_chat_attachment_cleanup())
        try:
            cleaned_count = await asyncio.to_thread(cleanup_expired_chat_attachments_once)
            logger.info("만료된 채팅 첨부 파일 정리를 완료했습니다. cleaned_count=%s", cleaned_count)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("만료된 채팅 첨부 파일 정리 중 오류가 발생했습니다.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    models.Base.metadata.create_all(bind=get_engine())
    contribution_assessment_queue.enqueue_pending()
    cleanup_task = asyncio.create_task(_chat_attachment_cleanup_scheduler())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title=settings.app_name, lifespan=lifespan)

cors_origins = list(dict.fromkeys([settings.frontend_url, settings.local_frontend_url]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site="lax")

app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=settings.server_port, reload=True)
