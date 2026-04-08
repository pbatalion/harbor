import { AssistantRun } from "@/lib/contracts";

type TodayPanelProps = {
  run: AssistantRun | null;
  workspaceSlug: string;
};

export function TodayPanel({ run, workspaceSlug }: TodayPanelProps) {
  // Only show on Downer workspace since context is Camp Downer focused
  if (workspaceSlug !== "downer") return null;
  
  if (!run) return null;
  
  const hasDayPlan = run.dayPlan && run.dayPlan.trim().length > 0;
  const hasUrgent = run.urgentItems && run.urgentItems.length > 0;
  
  if (!hasDayPlan && !hasUrgent) return null;

  return (
    <div className="today-panel">
      {hasUrgent && (
        <div className="urgent-section">
          <div className="section-header">
            <span className="urgent-icon">⚡</span>
            <span className="section-title">Urgent</span>
          </div>
          <ul className="urgent-list">
            {run.urgentItems.map((item, idx) => (
              <li key={idx} className="urgent-item">{item}</li>
            ))}
          </ul>
        </div>
      )}
      
      {hasDayPlan && (
        <div className="day-plan-section">
          <div className="section-header">
            <span className="plan-icon">📋</span>
            <span className="section-title">Today's Focus</span>
          </div>
          <div className="day-plan-content">
            {run.dayPlan.split('\n').map((line, idx) => (
              <p key={idx}>{line}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
