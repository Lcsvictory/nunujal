import json
import logging
import time

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
    candidates = [stripped]
    object_start = stripped.find("{")
    object_end = stripped.rfind("}")
    if object_start != -1 and object_end != -1 and object_start < object_end:
        candidates.append(stripped[object_start : object_end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise HTTPException(status_code=502, detail="Google Gemma response is not valid JSON.")


class GoogleGemmaContributionProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        thinking_level: str = "HIGH",
        thinking_budget: int | None = -1,
        use_response_schema: bool = True,
    ) -> None:
        self.api_key = api_key
        self.thinking_level = thinking_level
        self.thinking_budget = thinking_budget
        self.use_response_schema = use_response_schema

    def evaluate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, object],
    ) -> dict[str, object]:
        if not self.api_key:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise HTTPException(
                status_code=500,
                detail="google-genai is not installed. Run: pip install google-genai",
            ) from exc

        client = genai.Client(api_key=self.api_key)
        thinking_config_kwargs: dict[str, object]
        if model.startswith("gemini-2.5"):
            thinking_config_kwargs = {}
            if self.thinking_budget is not None:
                thinking_config_kwargs["thinking_budget"] = self.thinking_budget
        else:
            thinking_config_kwargs = {"thinking_level": self.thinking_level}

        config_kwargs: dict[str, object] = {
            "system_instruction": system_prompt,
            "thinking_config": types.ThinkingConfig(**thinking_config_kwargs),
        }
        if self.use_response_schema:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_json_schema"] = response_schema

        config = types.GenerateContentConfig(**config_kwargs)

        started_at = time.perf_counter()
        logger.info(
            "Google GenAI API 스트리밍 요청을 전송하고 응답을 기다리는 중입니다. model=%s thinking_level=%s thinking_budget=%s use_response_schema=%s system_prompt_chars=%s user_prompt_chars=%s",
            model,
            self.thinking_level,
            self.thinking_budget,
            self.use_response_schema,
            len(system_prompt),
            len(user_prompt),
        )

        content_parts: list[str] = []
        chunk_count = 0
        first_content_seconds: float | None = None
        last_progress_at = started_at

        try:
            for chunk in client.models.generate_content_stream(
                model=model,
                contents=user_prompt,
                config=config,
            ):
                text = chunk.text
                if not text:
                    continue
                chunk_count += 1
                content_parts.append(text)
                now = time.perf_counter()
                if first_content_seconds is None:
                    first_content_seconds = now - started_at
                    logger.info(
                        "Google Gemma API 첫 content 청크를 수신했습니다. model=%s first_content_seconds=%.2f",
                        model,
                        first_content_seconds,
                    )
                if now - last_progress_at >= 10:
                    logger.info(
                        "Google Gemma API 스트리밍 응답 생성 중입니다. model=%s elapsed_seconds=%.2f chunks=%s content_chars=%s",
                        model,
                        now - started_at,
                        chunk_count,
                        sum(len(part) for part in content_parts),
                    )
                    last_progress_at = now
        except Exception as exc:
            elapsed_seconds = time.perf_counter() - started_at
            logger.exception(
                "Google Gemma API 응답 대기 중 오류가 발생했습니다. model=%s elapsed_seconds=%.2f",
                model,
                elapsed_seconds,
            )
            raise HTTPException(status_code=502, detail=f"Google Gemma request failed: {exc}") from exc

        elapsed_seconds = time.perf_counter() - started_at
        logger.info(
            "Google Gemma API 스트리밍 응답을 수신했습니다. model=%s elapsed_seconds=%.2f chunks=%s content_chars=%s first_content_seconds=%s",
            model,
            elapsed_seconds,
            chunk_count,
            sum(len(part) for part in content_parts),
            f"{first_content_seconds:.2f}" if first_content_seconds is not None else None,
        )

        content = "".join(content_parts)
        if not content.strip():
            raise HTTPException(status_code=502, detail="Google Gemma returned an empty response.")
        return _parse_json_content(content)
