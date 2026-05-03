import os

from google import genai
from google.genai import types


# 직접 붙여넣어 테스트하려면 아래 값을 채우세요.
# 비워두면 GEMINI_API_KEY 환경 변수를 사용합니다.
GEMINI_API_KEY = ""
MODEL_NAME = "gemini-2.5-flash"


def main() -> None:
    api_key = GEMINI_API_KEY.strip() or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY를 설정하거나 gemma_api_test.py의 GEMINI_API_KEY 값을 채우세요.")

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction="JSON만 반환하는 테스트 도우미다.",
        thinking_config=types.ThinkingConfig(thinking_budget=-1),
        response_mime_type="application/json",
        response_json_schema={
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "message": {"type": "string"},
                "model": {"type": "string"},
            },
            "required": ["ok", "message", "model"],
        },
    )

    print(f"Requesting model={MODEL_NAME}")
    for chunk in client.models.generate_content_stream(
        model=MODEL_NAME,
        contents='{"task":"짧게 연결 테스트를 하고 JSON으로 응답하라."}',
        config=config,
    ):
        if text := chunk.text:
            print(text, end="")
    print()


if __name__ == "__main__":
    main()
