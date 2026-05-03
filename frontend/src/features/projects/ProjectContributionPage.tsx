import { useEffect, useState } from "react";
import { ApiError } from "../../lib/api";
import {
  createContributionObjection,
  fetchProjectContributionLatest,
  getProjectContributionEventsUrl,
  runProjectContributionAssessment,
} from "./api";
import type {
  ContributionEventMessage,
  ContributionLatestResponse,
  ContributionResult,
  ProjectDetail,
} from "./types";
import "./ProjectContributionPage.css";

type ProjectContributionPageProps = {
  project: ProjectDetail;
};

const PIE_COLORS = ["#20c997", "#4dabf7", "#845ef7", "#ff922b", "#f06595", "#51cf66", "#ffd43b", "#22b8cf"];
const PIE_CENTER = 160;
const PIE_RADIUS = 140;
const PIE_LABEL_RADIUS = 92;
const OBJECTION_TYPE_OPTIONS = [
  { value: "MY_SCORE_TOO_LOW", label: "내 기여도 상향" },
  { value: "OTHER_SCORE_REVIEW", label: "팀원 기여도 재검토" },
  { value: "MISSING_CONTEXT", label: "반영 누락" },
  { value: "AI_REASON_ERROR", label: "AI 판단 오류" },
] as const;

type ObjectionType = typeof OBJECTION_TYPE_OPTIONS[number]["value"];

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  return new Date(value).toLocaleString();
}

function getReviewStatusLabel(status: string): string {
  switch (status) {
    case "OPEN":
      return "대기 중";
    case "UNDER_REVIEW":
      return "검토 중";
    case "REFLECTED":
      return "반영 완료";
    case "REJECTED":
      return "반려";
    default:
      return status;
  }
}

function hasMeaningfulNote(value: string | null | undefined): value is string {
  const normalized = value?.trim().toLowerCase();
  return Boolean(normalized && !["none", "null", "없음", "-"].includes(normalized));
}

function polarToCartesian(cx: number, cy: number, radius: number, angle: number) {
  const radians = (angle - 90) * Math.PI / 180;
  return {
    x: cx + radius * Math.cos(radians),
    y: cy + radius * Math.sin(radians),
  };
}

function createPiePath(startRatio: number, endRatio: number): string {
  const sweep = endRatio - startRatio;
  if (sweep >= 0.999) {
    return [
      `M ${PIE_CENTER} ${PIE_CENTER - PIE_RADIUS}`,
      `A ${PIE_RADIUS} ${PIE_RADIUS} 0 1 1 ${PIE_CENTER} ${PIE_CENTER + PIE_RADIUS}`,
      `A ${PIE_RADIUS} ${PIE_RADIUS} 0 1 1 ${PIE_CENTER} ${PIE_CENTER - PIE_RADIUS}`,
      "Z",
    ].join(" ");
  }
  const start = polarToCartesian(PIE_CENTER, PIE_CENTER, PIE_RADIUS, startRatio * 360);
  const end = polarToCartesian(PIE_CENTER, PIE_CENTER, PIE_RADIUS, endRatio * 360);
  const largeArcFlag = sweep > 0.5 ? 1 : 0;
  return `M ${PIE_CENTER} ${PIE_CENTER} L ${start.x} ${start.y} A ${PIE_RADIUS} ${PIE_RADIUS} 0 ${largeArcFlag} 1 ${end.x} ${end.y} Z`;
}

function getPieLabelPoint(startRatio: number, endRatio: number) {
  return polarToCartesian(PIE_CENTER, PIE_CENTER, PIE_LABEL_RADIUS, ((startRatio + endRatio) / 2) * 360);
}

export function ProjectContributionPage({ project }: ProjectContributionPageProps) {
  const [data, setData] = useState<ContributionLatestResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAssessing, setIsAssessing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [objectionTarget, setObjectionTarget] = useState<ContributionResult | null>(null);
  const [objectionType, setObjectionType] = useState<ObjectionType>("MY_SCORE_TOO_LOW");
  const [objectionContent, setObjectionContent] = useState("");
  const [hoveredResultId, setHoveredResultId] = useState<number | null>(null);
  const [expandedReviewUserId, setExpandedReviewUserId] = useState<number | null>(null);
  const [expandedDetailResultId, setExpandedDetailResultId] = useState<number | null>(null);

  const loadContribution = async () => {
    setErrorMessage(null);
    try {
      const response = await fetchProjectContributionLatest(project.id);
      setData(response);
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : "기여도 정보를 불러오지 못했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadContribution();
  }, [project.id]);

  useEffect(() => {
    const eventSource = new EventSource(getProjectContributionEventsUrl(project.id), {
      withCredentials: true,
    });

    eventSource.addEventListener("contribution", (event) => {
      try {
        const message = JSON.parse((event as MessageEvent<string>).data) as ContributionEventMessage;
        setData(message.payload);
        setIsLoading(false);
        setErrorMessage(null);
      } catch {
        setErrorMessage("기여도 실시간 응답을 처리하지 못했습니다.");
      }
    });

    eventSource.addEventListener("contribution_error", (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent<string>).data) as { detail?: string };
        setErrorMessage(payload.detail ?? "기여도 실시간 연결에서 오류가 발생했습니다.");
      } catch {
        setErrorMessage("기여도 실시간 연결에서 오류가 발생했습니다.");
      }
    });

    return () => eventSource.close();
  }, [project.id]);

  const handleRunAssessment = async () => {
    setIsAssessing(true);
    setErrorMessage(null);
    try {
      const response = await runProjectContributionAssessment(project.id);
      const queuedAnalysis = response.analysis;
      setData((previous) => previous ? {
        ...previous,
        active_analysis: queuedAnalysis ?? previous.active_analysis,
        has_my_pending_assessment: true,
      } : previous);
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : "기여도 측정에 실패했습니다.");
    } finally {
      setIsAssessing(false);
    }
  };

  const handleSubmitObjection = async () => {
    if (!objectionTarget || !objectionContent.trim()) {
      return;
    }
    setIsAssessing(true);
    setErrorMessage(null);
    try {
      const selectedType = OBJECTION_TYPE_OPTIONS.find((option) => option.value === objectionType);
      const typedContent = `이의 유형: ${selectedType?.label ?? "기타"}\n내용: ${objectionContent.trim()}`;
      const response = await createContributionObjection(project.id, objectionTarget.id, typedContent);
      setObjectionTarget(null);
      setObjectionContent("");
      setObjectionType("MY_SCORE_TOO_LOW");
      const queuedAnalysis = response.analysis;
      setData((previous) => {
        if (!previous) {
          return previous;
        }
        const nextOpenReviews = [
          response.feedback_review,
          ...previous.open_feedback_reviews.filter((review) => review.id !== response.feedback_review.id),
        ];
        const nextRecentReviews = [
          response.feedback_review,
          ...previous.recent_feedback_reviews.filter((review) => review.id !== response.feedback_review.id),
        ].slice(0, 10);
        return {
          ...previous,
          active_analysis: queuedAnalysis ?? previous.active_analysis,
          has_my_pending_assessment: true,
          open_feedback_reviews: nextOpenReviews,
          recent_feedback_reviews: nextRecentReviews,
        };
      });
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : "이의제기 처리에 실패했습니다.");
    } finally {
      setIsAssessing(false);
    }
  };

  const analysis = data?.analysis;
  const activeAnalysis = data?.active_analysis;
  const results = analysis?.results ?? [];
  const myResult = results.find((result) => result.target_user?.id === data?.my_user_id) ?? null;
  const teammateResults = results.filter((result) => result.id !== myResult?.id);
  const openDisputes = data?.open_feedback_reviews ?? [];
  const recentDisputes = data?.recent_feedback_reviews ?? [];
  const canAssess = data?.can_assess ?? false;
  const isGenerating = Boolean(activeAnalysis && ["REQUESTED", "PROCESSING"].includes(activeAnalysis.status));
  const hasMyPendingAssessment = data?.has_my_pending_assessment ?? false;
  const isAssessmentButtonDisabled = isAssessing || hasMyPendingAssessment;
  const assessmentButtonLabel = isAssessing
    ? "요청 등록 중..."
    : hasMyPendingAssessment
      ? "요청 반영 대기 중"
      : isGenerating
        ? "재측정 요청 추가"
        : "기여도 측정";
  const totalScore = results.reduce((sum, result) => sum + Math.max(0, result.reference_score), 0) || 1;
  let cursor = 0;
  const pieSegments = results.map((result, index) => {
    const value = Math.max(0, result.reference_score) / totalScore;
    const segment = {
      result,
      color: PIE_COLORS[index % PIE_COLORS.length],
      start: cursor,
      end: cursor + value,
    };
    cursor += value;
    return segment;
  });
  const highlightedResult = results.find((result) => result.id === hoveredResultId) ?? myResult ?? results[0] ?? null;

  const getReviewsForResult = (result: ContributionResult) => {
    const targetUserId = result.target_user?.id;
    const reviews = [...recentDisputes, ...result.feedback_reviews].filter((review) => (
      review.contribution_result_id === result.id || (targetUserId != null && review.target_user?.id === targetUserId)
    ));
    return Array.from(new Map(reviews.map((review) => [review.id, review])).values())
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  };
  const myReviews = myResult ? getReviewsForResult(myResult) : [];
  const myActiveReviews = myReviews.filter((review) => ["OPEN", "UNDER_REVIEW"].includes(review.request_status));
  const isMyReviewsExpanded = Boolean(myResult?.target_user?.id && expandedReviewUserId === myResult.target_user.id);

  const formatReviewToggleText = (activeCount: number, totalCount: number) => (
    activeCount ? `이의 ${activeCount}건 처리 중` : `이의 내역 ${totalCount}건`
  );

  return (
    <div className="contribution-page">
      <header className="contribution-header">
        <div>
          <h2>기여도</h2>
          <p>내 기여도와 팀 전체 분포를 한눈에 확인합니다.</p>
        </div>
        <div className="contribution-actions">
          {canAssess ? (
            <button className="button button-primary" disabled={isAssessmentButtonDisabled} onClick={handleRunAssessment}>
              {assessmentButtonLabel}
            </button>
          ) : null}
        </div>
      </header>

      {errorMessage ? <div className="contribution-error">{errorMessage}</div> : null}

      {isLoading ? (
        <div className="contribution-empty">기여도 정보를 불러오는 중입니다.</div>
      ) : (
        <>
          {results.length === 0 ? (
            <div className="contribution-empty">표시할 기여도 결과가 없습니다.</div>
          ) : (
            <>
              {isGenerating ? (
                <div className="contribution-status-banner">
                  AI가 새 기여도 결과를 생성 중입니다. 완료되면 자동으로 화면이 갱신됩니다.
                  {openDisputes.length ? ` 처리 대기 중인 이의제기 ${openDisputes.length}건이 반영됩니다.` : ""}
                </div>
              ) : null}

              <section className="contribution-overview">
                <div className="contribution-panel contribution-pie-panel">
                  <div className="contribution-panel-title">
                    <strong>팀 기여도 분포</strong>
                    {analysis?.completed_at ? <span>마지막 산정: {formatDateTime(analysis.completed_at)}</span> : null}
                  </div>
                  <div className="contribution-pie-layout">
                    <svg className="contribution-pie" viewBox="0 0 320 320" role="img" aria-label="팀원별 기여도 원형 그래프">
                      {pieSegments.map((segment) => (
                        <path
                          key={segment.result.id}
                          d={createPiePath(segment.start, segment.end)}
                          fill={segment.color}
                          className={segment.result.id === highlightedResult?.id ? "contribution-pie-slice contribution-pie-slice-active" : "contribution-pie-slice"}
                          onMouseEnter={() => setHoveredResultId(segment.result.id)}
                          onMouseLeave={() => setHoveredResultId(null)}
                        />
                      ))}
                      {pieSegments.map((segment) => {
                        const labelPoint = getPieLabelPoint(segment.start, segment.end);
                        const score = segment.result.reference_score;
                        const label = segment.result.target_user?.name ?? "팀원";
                        const labelClassName = score < 7
                          ? "contribution-pie-label contribution-pie-label-small"
                          : "contribution-pie-label";
                        return (
                          <text
                            key={`label-${segment.result.id}`}
                            x={labelPoint.x}
                            y={labelPoint.y}
                            className={labelClassName}
                            onMouseEnter={() => setHoveredResultId(segment.result.id)}
                            onMouseLeave={() => setHoveredResultId(null)}
                          >
                            <tspan x={labelPoint.x} dy="-0.15em">{label}</tspan>
                            <tspan x={labelPoint.x} dy="1.2em">{score.toFixed(1)}%</tspan>
                          </text>
                        );
                      })}
                    </svg>
                    <div className="contribution-pie-focus">
                      <span>{highlightedResult?.target_user?.name ?? "팀원"}</span>
                      <strong>{(highlightedResult?.reference_score ?? 0).toFixed(1)}%</strong>
                      <p>{highlightedResult?.summary}</p>
                    </div>
                  </div>
                </div>
              </section>

              {myResult ? (
                <section className="contribution-panel contribution-my-panel">
                  <div className="contribution-my-main">
                    <div>
                      <span className="contribution-section-label">내 기여도</span>
                      <strong>{myResult.reference_score.toFixed(1)}%</strong>
                      <p>{myResult.summary}</p>
                      <p>{myResult.rationale}</p>
                    </div>
                    <div className="contribution-my-actions">
                      {myReviews.length ? (
                        <button
                          type="button"
                          className="contribution-review-toggle"
                          onClick={() => setExpandedReviewUserId(isMyReviewsExpanded ? null : myResult.target_user?.id ?? null)}
                        >
                          {formatReviewToggleText(myActiveReviews.length, myReviews.length)}
                        </button>
                      ) : null}
                      <button
                        className="button button-secondary"
                        disabled={isAssessing || myActiveReviews.length > 0}
                        onClick={() => {
                          setObjectionTarget(myResult);
                          setObjectionType("MY_SCORE_TOO_LOW");
                          setObjectionContent("");
                        }}
                      >
                        이의제기
                      </button>
                    </div>
                  </div>
                  {isMyReviewsExpanded ? (
                    <div className="contribution-review-list">
                      {myReviews.map((review) => (
                        <div key={review.id} className="contribution-review-item">
                          <div>
                            <strong>이의제기 내용</strong>
                            <span>{getReviewStatusLabel(review.request_status)} · {formatDateTime(review.reviewed_at ?? review.created_at)}</span>
                          </div>
                          <p>{review.content}</p>
                          {review.resolution_note ? <p><strong>AI 반영 결과:</strong> {review.resolution_note}</p> : null}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </section>
              ) : null}

              {teammateResults.length ? (
                <div className="contribution-detail-heading">
                  <strong>팀원별 상세</strong>
                  <span>기여도 높은 순으로 표시합니다.</span>
                </div>
              ) : null}
              <div className="contribution-list">
                {teammateResults.map((result) => {
                const user = result.target_user;
                const score = Math.max(0, Math.min(100, result.reference_score));
	                const reviews = getReviewsForResult(result);
	                const activeReviews = reviews.filter((review) => ["OPEN", "UNDER_REVIEW"].includes(review.request_status));
	                const hasActiveReview = activeReviews.length > 0;
	                const isExpanded = user?.id === expandedReviewUserId;
                const isDetailExpanded = result.id === expandedDetailResultId;
                return (
                  <article key={result.id} className="contribution-card">
                    <div className="contribution-card-header">
                      <div className="contribution-member">
                        <div className="contribution-avatar">
                          {user?.profile_image_url ? (
                            <img src={user.profile_image_url} alt={user.name} />
                          ) : (
                            user?.name?.charAt(0) ?? "?"
                          )}
                        </div>
                        <strong>{user?.name ?? "알 수 없음"}</strong>
                      </div>
                    </div>
                    <div className="contribution-card-score-panel">
                      <span className="contribution-section-label">기여도</span>
                      <strong>{score.toFixed(1)}%</strong>
                    </div>
                    <p className="contribution-card-summary">{result.summary}</p>
                    <div className="contribution-card-footer">
                      <button
                        type="button"
                        className="contribution-review-toggle"
                        onClick={() => setExpandedDetailResultId(isDetailExpanded ? null : result.id)}
                      >
                        {isDetailExpanded ? "상세 접기" : "상세 보기"}
                      </button>
                      {reviews.length ? (
                        <button
                          type="button"
                          className="contribution-review-toggle"
                          onClick={() => setExpandedReviewUserId(isExpanded ? null : user?.id ?? null)}
                        >
                          {formatReviewToggleText(activeReviews.length, reviews.length)}
                        </button>
                      ) : null}
	                      <button
	                        type="button"
	                        className="button button-secondary"
	                        disabled={isAssessing || hasActiveReview}
	                        onClick={() => {
                          setObjectionTarget(result);
                          setObjectionType("OTHER_SCORE_REVIEW");
                          setObjectionContent("");
                        }}
                      >
                        이의제기
                      </button>
                    </div>
                    {isDetailExpanded ? (
                      <div className="contribution-card-detail">
                        <p><strong>판단 근거:</strong> {result.rationale}</p>
                        <p><strong>팀 공유 설명:</strong> {result.public_explanation}</p>
                        {hasMeaningfulNote(result.uncertainty_note) ? <p><strong>불확실성:</strong> {result.uncertainty_note}</p> : null}
                        {hasMeaningfulNote(result.warning_note) ? <p><strong>주의:</strong> {result.warning_note}</p> : null}
                        <div className="contribution-metrics">
                          <div className="contribution-metric"><strong>신뢰도</strong>{result.confidence_score.toFixed(1)}</div>
                          <div className="contribution-metric"><strong>실행</strong>{result.execution_score.toFixed(1)}</div>
                          <div className="contribution-metric"><strong>협업</strong>{result.collaboration_score.toFixed(1)}</div>
                          <div className="contribution-metric"><strong>문서화</strong>{result.documentation_score.toFixed(1)}</div>
                          <div className="contribution-metric"><strong>문제 해결</strong>{result.problem_solving_score.toFixed(1)}</div>
                        </div>
                      </div>
                    ) : null}
                    {isExpanded ? (
                      <div className="contribution-review-list">
                        {reviews.map((review) => (
                          <div key={review.id} className="contribution-review-item">
                            <div>
                              <strong>이의제기 내용</strong>
                              <span>{getReviewStatusLabel(review.request_status)} · {formatDateTime(review.reviewed_at ?? review.created_at)}</span>
                            </div>
                            <p>{review.content}</p>
                            {review.resolution_note ? <p><strong>AI 반영 결과:</strong> {review.resolution_note}</p> : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </article>
                );
              })}
              </div>
            </>
          )}
        </>
      )}

      {objectionTarget ? (
        <div className="contribution-objection-overlay" onClick={() => setObjectionTarget(null)}>
          <div className="contribution-objection-modal" onClick={(event) => event.stopPropagation()}>
            <h3>이의제기</h3>
            <p>
              {objectionTarget.target_user?.id === data?.my_user_id ? "내" : `${objectionTarget.target_user?.name ?? "대상"}님의`} 현재 기여도
              {` ${objectionTarget.reference_score.toFixed(1)}%`}에 대한 의견을 작성하세요. 제출하면 AI 재측정 큐에 등록됩니다.
            </p>
            <label className="contribution-objection-field">
              <span>이의 유형</span>
              <select
                value={objectionType}
                onChange={(event) => setObjectionType(event.target.value as ObjectionType)}
              >
                {OBJECTION_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            <label className="contribution-objection-field">
              <span>내용</span>
              <textarea
                value={objectionContent}
                onChange={(event) => setObjectionContent(event.target.value)}
                placeholder="어떤 활동이나 판단이 다시 고려되어야 하는지 작성하세요."
              />
            </label>
            <div className="contribution-modal-actions">
              <button className="button button-secondary" onClick={() => setObjectionTarget(null)}>취소</button>
              <button className="button button-primary" disabled={isAssessing || !objectionContent.trim()} onClick={handleSubmitObjection}>
                {isAssessing ? "등록 중..." : "제출"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
