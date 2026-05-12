from collections import defaultdict, deque
import logging
from queue import Empty, Full, Queue
from threading import Lock, Thread
from typing import Any

from app.core.config import get_settings
from app.database import get_session
import app.models as models
from app.services.contribution.evaluator import process_contribution_analysis
from app.services.contribution.providers.google_gemini import GoogleGeminiContributionProvider
from app.services.contribution.providers.ollama import OllamaContributionProvider


logger = logging.getLogger("uvicorn.error")


class ContributionAssessmentQueue:
    def __init__(self) -> None:
        self._queue: deque[int] = deque()
        self._queued_ids: set[int] = set()
        self._subscribers: dict[int, set[Queue[dict[str, Any]]]] = defaultdict(set)
        self._lock = Lock()
        self._worker: Thread | None = None
        self._running = False

    def enqueue(self, analysis_id: int) -> None:
        project_id = self._project_id_for_analysis(analysis_id)
        if project_id is not None:
            self._supersede_waiting_project_requests(project_id, keep_analysis_id=analysis_id)

        with self._lock:
            if analysis_id in self._queued_ids:
                return
            if project_id is not None:
                stale_ids = [
                    queued_id
                    for queued_id in self._queue
                    if queued_id != analysis_id and self._project_id_for_analysis(queued_id) == project_id
                ]
                if stale_ids:
                    self._queue = deque(queued_id for queued_id in self._queue if queued_id not in stale_ids)
                    self._queued_ids.difference_update(stale_ids)
                    logger.info(
                        "같은 프로젝트의 오래된 AI 기여도 대기 요청을 큐에서 제거했습니다. project_id=%s stale_analysis_ids=%s",
                        project_id,
                        stale_ids,
                    )
            self._queue.append(analysis_id)
            self._queued_ids.add(analysis_id)
            logger.info(
                "AI 기여도 평가 요청이 비동기 큐에 등록되었습니다. analysis_id=%s queue_size=%s",
                analysis_id,
                len(self._queue),
            )
            if self._worker is None or not self._worker.is_alive():
                self._worker = Thread(target=self._run, daemon=True)
                self._worker.start()

    def subscribe(self, project_id: int) -> Queue[dict[str, Any]]:
        subscriber: Queue[dict[str, Any]] = Queue(maxsize=20)
        with self._lock:
            self._subscribers[project_id].add(subscriber)
        return subscriber

    def unsubscribe(self, project_id: int, subscriber: Queue[dict[str, Any]]) -> None:
        with self._lock:
            subscribers = self._subscribers.get(project_id)
            if subscribers is None:
                return
            subscribers.discard(subscriber)
            if not subscribers:
                self._subscribers.pop(project_id, None)

    def publish(
        self,
        project_id: int,
        event_type: str,
        *,
        analysis_id: int | None = None,
        status: str | None = None,
    ) -> None:
        event = {
            "type": event_type,
            "project_id": project_id,
            "analysis_id": analysis_id,
            "status": status,
        }
        with self._lock:
            subscribers = list(self._subscribers.get(project_id, set()))

        for subscriber in subscribers:
            try:
                subscriber.put_nowait(event)
            except Full:
                try:
                    subscriber.get_nowait()
                except Empty:
                    pass
                try:
                    subscriber.put_nowait(event)
                except Full:
                    pass

    def enqueue_pending(self) -> None:
        session = get_session()
        try:
            pending_ids = [
                analysis_id
                for (analysis_id,) in (
                    session.query(models.AiAnalysis.id)
                    .filter(models.AiAnalysis.status.in_(["REQUESTED", "PROCESSING"]))
                    .order_by(models.AiAnalysis.created_at.asc(), models.AiAnalysis.id.asc())
                    .all()
                )
            ]
        finally:
            session.close()

        for analysis_id in pending_ids:
            self.enqueue(analysis_id)

    def is_busy(self) -> bool:
        with self._lock:
            return self._running or bool(self._queue)

    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._queue:
                    self._running = False
                    return
                analysis_id = self._queue.popleft()
                self._queued_ids.discard(analysis_id)
                self._running = True

            self._process_one(analysis_id)

    def _project_id_for_analysis(self, analysis_id: int) -> int | None:
        session = get_session()
        try:
            row = (
                session.query(models.AiAnalysis.project_id)
                .filter(models.AiAnalysis.id == analysis_id)
                .first()
            )
            return int(row[0]) if row else None
        finally:
            session.close()

    def _supersede_waiting_project_requests(self, project_id: int, *, keep_analysis_id: int) -> None:
        session = get_session()
        try:
            stale_analyses = (
                session.query(models.AiAnalysis)
                .filter(
                    models.AiAnalysis.project_id == project_id,
                    models.AiAnalysis.status == "REQUESTED",
                    models.AiAnalysis.id != keep_analysis_id,
                )
                .all()
            )
            if not stale_analyses:
                return
            for analysis in stale_analyses:
                analysis.status = "FAILED"
                analysis.input_summary = "더 최신 기여도 재산정 요청이 등록되어 이 대기 요청은 건너뛰었습니다."
            session.commit()
            logger.info(
                "같은 프로젝트의 오래된 AI 기여도 DB 대기 요청을 건너뛰었습니다. project_id=%s stale_analysis_ids=%s keep_analysis_id=%s",
                project_id,
                [analysis.id for analysis in stale_analyses],
                keep_analysis_id,
            )
        except Exception:
            session.rollback()
            logger.exception(
                "오래된 AI 기여도 대기 요청 정리 중 오류가 발생했습니다. project_id=%s keep_analysis_id=%s",
                project_id,
                keep_analysis_id,
            )
        finally:
            session.close()

    def _process_one(self, analysis_id: int) -> None:
        session = get_session()
        settings = get_settings()
        project_id: int | None = None
        try:
            analysis = session.query(models.AiAnalysis).filter(models.AiAnalysis.id == analysis_id).first()
            if analysis is None or analysis.status not in {"REQUESTED", "PROCESSING"}:
                return

            project_id = analysis.project_id
            analysis.status = "PROCESSING"
            analysis.input_summary = "AI 기여도 평가 결과를 생성 중입니다."
            session.commit()
            logger.info(
                "AI 기여도 평가 비동기 처리를 시작했습니다. 응답을 기다리는 중입니다. project_id=%s analysis_id=%s",
                project_id,
                analysis.id,
            )
            self.publish(project_id, "processing", analysis_id=analysis.id, status=analysis.status)

            provider_name = settings.contribution_ai_provider.lower()
            if provider_name in {"google", "google_gemini", "google_gemma", "gemini", "gemma"}:
                provider = GoogleGeminiContributionProvider(
                    api_key=settings.gemini_api_key,
                    thinking_level=settings.google_genai_thinking_level,
                    thinking_budget=settings.google_genai_thinking_budget,
                    use_response_schema=settings.google_genai_use_response_schema,
                )
            elif provider_name == "ollama":
                provider = OllamaContributionProvider(
                    base_url=settings.ollama_base_url,
                    timeout_seconds=settings.contribution_request_timeout_seconds,
                )
            else:
                raise ValueError(f"Unsupported contribution AI provider: {settings.contribution_ai_provider}")
            process_contribution_analysis(
                session,
                analysis,
                provider=provider,
                settings=settings,
            )
            session.commit()
            logger.info(
                "AI 기여도 평가 비동기 처리가 완료되었습니다. project_id=%s analysis_id=%s status=%s summary=%s",
                project_id,
                analysis.id,
                analysis.status,
                analysis.input_summary,
            )
            self.publish(
                project_id,
                "completed" if analysis.status == "COMPLETED" else "failed",
                analysis_id=analysis.id,
                status=analysis.status,
            )
        except Exception:
            session.rollback()
            failed_session = get_session()
            try:
                failed_analysis = (
                    failed_session.query(models.AiAnalysis)
                    .filter(models.AiAnalysis.id == analysis_id)
                    .first()
                )
                if failed_analysis is not None:
                    project_id = failed_analysis.project_id
                    failed_analysis.status = "FAILED"
                    failed_analysis.input_summary = "AI 기여도 평가 처리 중 서버 오류가 발생했습니다."
                    failed_session.commit()
                    self.publish(
                        project_id,
                        "failed",
                        analysis_id=failed_analysis.id,
                        status=failed_analysis.status,
                    )
            finally:
                failed_session.close()
        finally:
            session.close()


contribution_assessment_queue = ContributionAssessmentQueue()
