type ProjectGanttChartProps = {
  startDate: string;
  endDate: string;
  completionRate: number;
};

type GanttMonth = {
  key: string;
  label: string;
};

type GanttPhase = {
  id: string;
  label: string;
  owner: string;
  note: string;
  startOffsetPercent: number;
  widthPercent: number;
  status: "done" | "active" | "planned";
};

const dayInMilliseconds = 1000 * 60 * 60 * 24;

function toDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function calculateInclusiveDays(startDate: Date, endDate: Date): number {
  return Math.max(1, Math.floor((endDate.getTime() - startDate.getTime()) / dayInMilliseconds) + 1);
}

function buildMonthLabels(startDate: Date, endDate: Date): GanttMonth[] {
  const formatter = new Intl.DateTimeFormat("ko-KR", { month: "long" });
  const labels: GanttMonth[] = [];
  const cursor = new Date(startDate.getFullYear(), startDate.getMonth(), 1);
  const finalMonth = new Date(endDate.getFullYear(), endDate.getMonth(), 1);

  while (cursor <= finalMonth) {
    labels.push({
      key: `${cursor.getFullYear()}-${cursor.getMonth() + 1}`,
      label: formatter.format(cursor),
    });
    cursor.setMonth(cursor.getMonth() + 1);
  }

  return labels;
}

function buildPrototypePhases(
  startDate: Date,
  endDate: Date,
  completionRate: number,
): GanttPhase[] {
  const totalDays = calculateInclusiveDays(startDate, endDate);
  const completionProgress = completionRate / 100;
  const segments = [
    {
      id: "scope",
      label: "기획 및 요구사항 정리",
      owner: "PM · 팀장",
      note: "범위 정의, 목표 확정, 역할 분담",
      share: 0.16,
    },
    {
      id: "design",
      label: "화면 설계 및 구조 정리",
      owner: "프론트 · 기획",
      note: "플로우 정리, 정보 구조, 화면 초안",
      share: 0.18,
    },
    {
      id: "build",
      label: "핵심 기능 구현",
      owner: "프론트 · 백엔드",
      note: "업무 기능, 프로젝트 구조, API 연결",
      share: 0.34,
    },
    {
      id: "analysis",
      label: "AI 기여도 분석 연동",
      owner: "AI · 데이터",
      note: "기여도 계산 흐름, 검증용 지표 정리",
      share: 0.18,
    },
    {
      id: "qa",
      label: "검수 및 발표 준비",
      owner: "전체 팀",
      note: "QA, 피드백 반영, 발표 자료 준비",
      share: 0.14,
    },
  ];

  let consumedDays = 0;

  return segments.map((segment, index) => {
    const remainingDays = totalDays - consumedDays;
    const phaseDays =
      index === segments.length - 1
        ? remainingDays
        : Math.max(1, Math.round(totalDays * segment.share));
    const safePhaseDays = index === segments.length - 1 ? remainingDays : Math.min(phaseDays, remainingDays);
    const phaseStartDay = consumedDays;
    const phaseEndDay = consumedDays + safePhaseDays;
    const startFraction = phaseStartDay / totalDays;
    const endFraction = phaseEndDay / totalDays;

    let status: GanttPhase["status"] = "planned";
    if (completionProgress >= endFraction) {
      status = "done";
    } else if (completionProgress > startFraction) {
      status = "active";
    }

    consumedDays += safePhaseDays;

    return {
      id: segment.id,
      label: segment.label,
      owner: segment.owner,
      note: segment.note,
      startOffsetPercent: startFraction * 100,
      widthPercent: (safePhaseDays / totalDays) * 100,
      status,
    };
  });
}

export function ProjectGanttChart({
  startDate,
  endDate,
  completionRate,
}: ProjectGanttChartProps) {
  const start = toDate(startDate);
  const end = toDate(endDate);
  const months = buildMonthLabels(start, end);
  const phases = buildPrototypePhases(start, end, completionRate);
  const gridTemplateColumns = `240px minmax(${Math.max(4, months.length) * 120}px, 1fr)`;

  return (
    <section className="surface-panel gantt-card">
      <div className="section-heading">
        <div>
          <p className="section-label">gantt chart</p>
          <h2>프로젝트 간트차트</h2>
          <p className="gantt-caption">
            현재는 프로젝트 기간을 기준으로 한 프로토타입 일정입니다. 구조가
            확정되면 실제 업무 일정 데이터로 치환하면 됩니다.
          </p>
        </div>

        <div className="gantt-legend">
          <span className="gantt-legend-item">
            <i className="gantt-legend-dot gantt-legend-dot-done" />
            완료
          </span>
          <span className="gantt-legend-item">
            <i className="gantt-legend-dot gantt-legend-dot-active" />
            진행 중
          </span>
          <span className="gantt-legend-item">
            <i className="gantt-legend-dot gantt-legend-dot-planned" />
            예정
          </span>
        </div>
      </div>

      <div className="gantt-scroll">
        <div className="gantt-table">
          <div className="gantt-grid gantt-grid-header" style={{ gridTemplateColumns }}>
            <div className="gantt-label-cell">단계</div>
            <div className="gantt-header-track">
              <div
                className="gantt-month-grid"
                style={{ gridTemplateColumns: `repeat(${months.length}, minmax(120px, 1fr))` }}
              >
                {months.map((month) => (
                  <div key={month.key} className="gantt-month-cell">
                    {month.label}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {phases.map((phase) => (
            <div key={phase.id} className="gantt-grid gantt-grid-row" style={{ gridTemplateColumns }}>
              <div className="gantt-label-cell gantt-phase-copy">
                <strong>{phase.label}</strong>
                <span>{phase.owner}</span>
                <p>{phase.note}</p>
              </div>

              <div className="gantt-track-cell">
                <div
                  className="gantt-track-grid"
                  style={{ gridTemplateColumns: `repeat(${months.length}, minmax(120px, 1fr))` }}
                >
                  {months.map((month) => (
                    <div key={`${phase.id}-${month.key}`} className="gantt-track-slot" />
                  ))}
                </div>
                <div
                  className={`gantt-bar gantt-bar-${phase.status}`}
                  style={{
                    left: `${phase.startOffsetPercent}%`,
                    width: `${phase.widthPercent}%`,
                  }}
                >
                  {phase.status === "done"
                    ? "완료"
                    : phase.status === "active"
                      ? "진행 중"
                      : "예정"}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
