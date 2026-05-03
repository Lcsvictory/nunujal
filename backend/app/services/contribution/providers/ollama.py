import json
import logging
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException


logger = logging.getLogger("uvicorn.error")


def _strip_markdown_fence(value: str) -> str:
    stripped = value.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_json_content(content: str) -> dict[str, object]:
    stripped = _strip_markdown_fence(content)
    print("Ollama raw content:", repr(content))
    candidates = [stripped]
    object_start = stripped.find("{")
    object_end = stripped.rfind("}")
    if object_start != -1 and object_end != -1 and object_start < object_end:
        candidates.append(stripped[object_start : object_end + 1])

    for candidate in list(candidates):
        repaired = re.sub(r'([{\[,]\s*)\$\s*(?=")', r"\1", candidate)
        if repaired != candidate:
            candidates.append(repaired)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise HTTPException(status_code=502, detail="Ollama response is not valid JSON.")


class OllamaContributionProvider:
    def __init__(self, *, base_url: str, timeout_seconds: int = 600) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def evaluate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, object],
    ) -> dict[str, object]:
        _ = response_schema
        payload = {
            "model": model,
            "stream": True,
            "think": True,
            "keep_alive": "30m",
            "options": {
                "temperature": 0.2,
            },
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        endpoint = f"{self.base_url}/api/chat"
        started_at = time.perf_counter()
        logger.info(
            "Ollama AI 스트리밍 요청을 전송하고 응답을 기다리는 중입니다. model=%s endpoint=%s timeout_seconds=%s system_prompt_chars=%s user_prompt_chars=%s",
            model,
            endpoint,
            self.timeout_seconds,
            len(system_prompt),
            len(user_prompt),
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                status_code = getattr(response, "status", None)
                content_parts: list[str] = []
                last_progress_at = started_at
                chunk_count = 0
                first_chunk_seconds: float | None = None
                first_content_seconds: float | None = None
                final_chunk: dict[str, object] | None = None

                logger.info(
                    "Ollama AI 스트림 연결이 열렸습니다. model=%s status_code=%s",
                    model,
                    status_code,
                )

                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue

                    chunk_count += 1
                    now = time.perf_counter()
                    if first_chunk_seconds is None:
                        first_chunk_seconds = now - started_at
                        logger.info(
                            "Ollama AI 첫 스트리밍 청크를 수신했습니다. model=%s first_chunk_seconds=%.2f",
                            model,
                            first_chunk_seconds,
                        )
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise HTTPException(status_code=502, detail="Ollama stream chunk is not valid JSON.") from exc

                    if chunk.get("error"):
                        raise HTTPException(status_code=502, detail=f"Ollama error: {chunk['error']}")

                    message = chunk.get("message")
                    if isinstance(message, dict):
                        content_piece = message.get("content")
                        if isinstance(content_piece, str):
                            content_parts.append(content_piece)
                            if content_piece and first_content_seconds is None:
                                first_content_seconds = time.perf_counter() - started_at
                                logger.info(
                                    "Ollama AI 첫 content 토큰을 수신했습니다. model=%s first_content_seconds=%.2f",
                                    model,
                                    first_content_seconds,
                                )

                    now = time.perf_counter()
                    if now - started_at > self.timeout_seconds:
                        raise HTTPException(
                            status_code=502,
                            detail=f"Ollama request exceeded total timeout: {self.timeout_seconds}s",
                        )
                    if now - last_progress_at >= 10:
                        logger.info(
                            "Ollama AI 스트리밍 응답 생성 중입니다. model=%s elapsed_seconds=%.2f chunks=%s content_chars=%s",
                            model,
                            now - started_at,
                            chunk_count,
                            sum(len(part) for part in content_parts),
                        )
                        last_progress_at = now

                    if chunk.get("done"):
                        final_chunk = chunk
                        break

                elapsed_seconds = time.perf_counter() - started_at
                logger.info(
                    "Ollama AI 스트리밍 응답을 수신했습니다. model=%s status_code=%s elapsed_seconds=%.2f chunks=%s done_reason=%s first_chunk_seconds=%s first_content_seconds=%s total_duration_ns=%s prompt_eval_count=%s prompt_eval_duration_ns=%s eval_count=%s eval_duration_ns=%s",
                    model,
                    status_code,
                    elapsed_seconds,
                    chunk_count,
                    final_chunk.get("done_reason") if final_chunk else None,
                    f"{first_chunk_seconds:.2f}" if first_chunk_seconds is not None else None,
                    f"{first_content_seconds:.2f}" if first_content_seconds is not None else None,
                    final_chunk.get("total_duration") if final_chunk else None,
                    final_chunk.get("prompt_eval_count") if final_chunk else None,
                    final_chunk.get("prompt_eval_duration") if final_chunk else None,
                    final_chunk.get("eval_count") if final_chunk else None,
                    final_chunk.get("eval_duration") if final_chunk else None,
                )
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            elapsed_seconds = time.perf_counter() - started_at
            logger.exception(
                "Ollama AI 응답 대기 중 오류가 발생했습니다. model=%s elapsed_seconds=%.2f",
                model,
                elapsed_seconds,
            )
            raise HTTPException(status_code=502, detail=f"Ollama request failed: {exc}") from exc

        content = "".join(content_parts)
        if not content.strip():
            raise HTTPException(status_code=502, detail="Ollama returned an empty response.")

        return _parse_json_content(content)
