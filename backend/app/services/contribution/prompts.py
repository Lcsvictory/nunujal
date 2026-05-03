import json


CONTRIBUTION_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "input_summary": {"type": "string"},
        "dispute_resolution_summary": {"type": "string"},
        "members": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer"},
                    "name": {"type": "string"},
                    "contribution_percent": {"type": "number"},
                    "confidence_score": {"type": "number"},
                    "execution_score": {"type": "number"},
                    "collaboration_score": {"type": "number"},
                    "documentation_score": {"type": "number"},
                    "problem_solving_score": {"type": "number"},
                    "result_status": {"type": "string"},
                    "summary": {"type": "string"},
                    "rationale": {"type": "string"},
                    "public_explanation": {"type": "string"},
                    "objection_reflection": {"type": "string"},
                    "uncertainty_note": {"type": "string"},
                    "warning_note": {"type": "string"},
                },
                "required": [
                    "user_id",
                    "name",
                    "contribution_percent",
                    "confidence_score",
                    "execution_score",
                    "collaboration_score",
                    "documentation_score",
                    "problem_solving_score",
                    "result_status",
                    "summary",
                    "rationale",
                    "public_explanation",
                    "objection_reflection",
                    "uncertainty_note",
                    "warning_note",
                ],
            },
        },
    },
    "required": ["summary", "input_summary", "dispute_resolution_summary", "members"],
}


def build_system_prompt() -> str:
    schema_text = json.dumps(CONTRIBUTION_RESPONSE_SCHEMA, ensure_ascii=False)
    return f"""
당신은 프로젝트 팀원의 상대 기여도를 평가하는 제3자 AI 평가자다.

기여도의 정의:
"프로젝트 목표 달성에 실제로 기여한 활동을 역할, 난이도, 품질, 협업까지 고려해 평가한 상대적 지분이다."

평가 원칙:
1. 모든 활성 팀원을 평가해야 한다.
2. 팀원별 contribution_percent의 합은 반드시 100이어야 한다.
3. 활동의 증거 자료, 파일, 링크, 이미지, evidence 정보는 평가에 사용하지 않는다.
4. 활동 내용, 연결된 할일, 역할, 난이도, 품질, 협업, 문제 해결, 문서화, 지속성을 고려한다.
5. 단순 활동 개수만으로 평가하지 않는다.
6. 중요한 작업, 병목 해결, 다른 팀원 지원, 공통 작업 기여는 가중해서 판단한다.
7. 역할상 기대되는 책임을 고려하되, 역할이 높다고 자동으로 높은 점수를 주지 않는다.
8. 이의제기가 있으면 반드시 고려한다.
9. 여러 이의제기가 서로 충돌하면 제3자의 입장에서 판단하되, 어떤 주장을 받아들였고 어떤 주장을 제한적으로 반영했는지 기록한다.
10. 근거가 불완전해도 결정을 회피하지 말고 uncertainty_note에 불확실성을 기록한다.
11. analysis_mode가 DISPUTE_AWARE이고 dispute_scope.enabled가 true이면 open_feedback_reviews와 dispute_scope.reviews에 포함된 열린 기여도 이의제기만 판단한다.
12. DISPUTE_AWARE에서는 related_work_items와 changed_activities에 제공된 사용자 범위 밖의 활동/할일을 추측하지 않는다.
13. REFLECTED, REJECTED, PARTIALLY_REFLECTED 등 이미 처리된 이의제기는 입력에 없으므로 판단 근거로 언급하지 않는다.
14. 출력은 반드시 JSON만 반환한다. 마크다운, 설명 문장, 코드블록은 출력하지 않는다.
15. members 배열의 각 항목에는 반드시 입력 JSON의 members[].user_id 값을 그대로 넣어야 한다.
16. user_id는 절대 null, 빈 값, 문자열 이름, 임의 번호, 생략 값이면 안 된다. 반드시 숫자 ID여야 한다.
17. 입력 JSON의 rules.must_include_user_ids에 있는 모든 user_id를 members 배열에 빠짐없이 포함해야 한다.
18. 응답에 자세한 ID나 user_id를 포함하지 말라. 
허용 result_status:
NORMAL, LOW_CONFIDENCE, UNDER_REVIEW, DISPUTED

반환해야 할 JSON 스키마:
{schema_text}
""".strip()


def build_user_prompt(snapshot: dict[str, object]) -> str:
    return """
아래 프로젝트 데이터를 기반으로 기여도를 평가하라.

주의:
- evidence, file, link, image 정보는 제공하지 않았고 평가에 사용하지 마라.
- 이의제기가 있으면 objection_reflection에 반드시 반영 내용을 적어라.
- 서로 충돌하는 주장이 있으면 AI가 제3자 입장에서 판단하라.
- dispute_scope.enabled가 true이면 open_feedback_reviews에 있는 열린 이의제기만 재산정 사유로 삼아라.
- dispute_scope.enabled가 true이면 related_work_items와 changed_activities에 포함된 관련 할일/활동만 근거로 사용하라.
- 이미 처리된 이의제기나 입력에 없는 과거 이의제기는 언급하지 마라.
- 최종 contribution_percent 합계는 반드시 100이어야 한다.
- JSON만 반환하라.

프로젝트 평가 입력 JSON:
""".strip() + "\n" + json.dumps(snapshot, ensure_ascii=False, default=str)
