import { AssistantItem } from "@/lib/contracts";

type CalendarPanelProps = {
  items: AssistantItem[];
  workspaceSlug: string;
};

function formatCalendarDate(value: string): { day: string; month: string; time: string } {
  try {
    const date = new Date(value);
    return {
      day: date.getDate().toString(),
      month: date.toLocaleDateString("en-US", { month: "short" }).toUpperCase(),
      time: date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }),
    };
  } catch {
    return { day: "?", month: "???", time: "" };
  }
}

function CalendarCard({ item }: { item: AssistantItem }) {
  const startDate =
    typeof item.payload.start === "string" ? item.payload.start : item.occurredAt;
  const { day, month, time } = formatCalendarDate(startDate);

  const attendees: string[] = Array.isArray(item.payload.attendees)
    ? item.payload.attendees.map(String).slice(0, 5)
    : [];

  const location =
    typeof item.payload.location === "string" ? item.payload.location : "";

  return (
    <div className="calendar-card">
      <div className="calendar-date">
        <span className="day">{day}</span>
        <span className="month">{month}</span>
        {time && <span className="time">{time}</span>}
      </div>
      <div className="calendar-details">
        <div className="calendar-title">{item.title}</div>
        <div className="calendar-meta">
          {location && <span>{location}</span>}
          {!location && item.actor && <span>Organized by {item.actor}</span>}
        </div>
        {attendees.length > 0 && (
          <div className="calendar-attendees">
            {attendees.map((attendee, idx) => (
              <span key={idx} className="attendee-chip">
                {attendee.split("@")[0]}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function CalendarPanel({ items, workspaceSlug }: CalendarPanelProps) {
  // Sort by start date
  const sorted = [...items].sort((a, b) => {
    const aStart = typeof a.payload.start === "string" ? a.payload.start : a.occurredAt;
    const bStart = typeof b.payload.start === "string" ? b.payload.start : b.occurredAt;
    return new Date(aStart).getTime() - new Date(bStart).getTime();
  });

  if (sorted.length === 0) {
    return (
      <div className="board">
        <div className="empty-state">
          <div className="empty-state-icon">📅</div>
          <div className="empty-state-title">No calendar events</div>
          <div className="empty-state-desc">
            Calendar events for this workspace will appear here.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="calendar-list">
      {sorted.map((item) => (
        <CalendarCard key={item.id} item={item} />
      ))}
    </div>
  );
}
