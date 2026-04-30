const projectStatusLabelMap: Record<string, string> = {
  PLANNING: "계획 중",
  IN_PROGRESS: "진행 중",
  DONE: "완료",
};

const joinPolicyLabelMap: Record<string, string> = {
  AUTO_APPROVE: "즉시 참여",
  LEADER_APPROVE: "승인 필요",
};

const activityTypeLabelMap: Record<string, string> = {
  MATERIAL_COLLECTION: "자료 수집",
  MEETING_RECORD: "회의 기록",
  CONTENT_EDITING: "콘텐츠 편집",
  FINALIZATION: "최종 정리",
};

const reviewStateLabelMap: Record<string, string> = {
  NORMAL: "정상",
  UNDER_REVIEW: "검토 중",
  DISPUTED: "이의 제기",
  RESOLVED: "승인됨",
};

function formatDateValue(value: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat("ko-KR", options).format(new Date(value));
}

export function formatDateRange(startDate: string, endDate: string): string {
  return `${formatDateValue(startDate, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  })} - ${formatDateValue(endDate, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  })}`;
}

export function formatShortDate(value: string): string {
  return formatDateValue(value, {
    month: "short",
    day: "numeric",
  });
}

export function formatDateTime(value: string): string {
  return formatDateValue(value, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatProjectStatus(status: string): string {
  return projectStatusLabelMap[status] ?? status;
}

export function formatJoinPolicy(joinPolicy: string): string {
  return joinPolicyLabelMap[joinPolicy] ?? joinPolicy;
}

export function formatActivityType(activityType: string): string {
  return activityTypeLabelMap[activityType] ?? activityType;
}

export function formatReviewState(reviewState: string): string {
  return reviewStateLabelMap[reviewState] ?? reviewState;
}
