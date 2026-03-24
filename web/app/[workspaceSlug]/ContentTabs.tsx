import Link from "next/link";

type ContentTabsProps = {
  workspaceSlug: string;
  activeTab: string;
  itemCount: number;
  calendarCount: number;
  draftCount: number;
};

export function ContentTabs({
  workspaceSlug,
  activeTab,
  itemCount,
  calendarCount,
  draftCount,
}: ContentTabsProps) {
  return (
    <div className="content-tabs">
      <Link
        href={`/${workspaceSlug}?tab=items`}
        className={`content-tab ${activeTab === "items" ? "active" : ""}`}
      >
        Items
        <span className="badge">{itemCount}</span>
      </Link>
      <Link
        href={`/${workspaceSlug}?tab=calendar`}
        className={`content-tab ${activeTab === "calendar" ? "active" : ""}`}
      >
        Calendar
        <span className="badge">{calendarCount}</span>
      </Link>
      <Link
        href={`/${workspaceSlug}?tab=drafts`}
        className={`content-tab ${activeTab === "drafts" ? "active" : ""}`}
      >
        Drafts
        <span className="badge">{draftCount}</span>
      </Link>
    </div>
  );
}
