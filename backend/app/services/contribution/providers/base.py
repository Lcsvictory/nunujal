from typing import Protocol


class ContributionAiProvider(Protocol):
    def evaluate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, object],
    ) -> dict[str, object]:
        ...
