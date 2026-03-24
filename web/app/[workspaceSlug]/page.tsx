import Link from "next/link";
import { notFound } from "next/navigation";
import { loadWorkspaceSnapshot } from "@/lib/dashboard";
import { isWorkspaceSlug, WORKSPACES } from "@/lib/workspaces";
import { ItemBoard } from "./ItemBoard";
import { DraftsPanel } from "./DraftsPanel";
import { CalendarPanel } from "./CalendarPanel";
import { ContentTabs } from "./ContentTabs";

type PageProps = {
  params: Promise<{
    workspaceSlug: string;
  }>;
  searchParams: Promise<{
    tab?: string;
    filter?: string;
  }>;
};

function formatSyncTime(value: string): string {
  try {
    const date = new Date(value);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

export default async function WorkspacePage(props: PageProps) {
  const params = await props.params;
  const searchParams = await props.searchParams;

  if (!isWorkspaceSlug(params.workspaceSlug)) {
    notFound();
  }

  const snapshot = await loadWorkspaceSnapshot(params.workspaceSlug);
  const activeTab = searchParams.tab || "items";
  const activeFilter = searchParams.filter || "all";

  // Filter items based on active filter
  let filteredItems = snapshot.items;
  if (activeFilter === "actionable") {
    filteredItems = snapshot.items.filter((item) => item.isActionable);
  } else if (activeFilter === "unread") {
    filteredItems = snapshot.items.filter((item) => item.isUnread);
  }

  // Extract calendar items
  const calendarItems = snapshot.items.filter((item) => item.itemType === "calendar");

  const workspaceClass = `workspace-${params.workspaceSlug}`;

  return (
    <div className={`harbor-shell ${workspaceClass}`}>
      <header className="harbor-header">
        <div className="harbor-header-inner">
          <div className="harbor-brand">
            <div className="harbor-logo">H</div>
            <div>
              <div className="harbor-title">Harbor</div>
              <div className="harbor-subtitle">Control Deck</div>
            </div>
          </div>

          <nav className="workspace-switcher">
            {Object.values(WORKSPACES).map((ws) => (
              <Link
                key={ws.slug}
                href={`/${ws.slug}`}
                className={`workspace-tab ${ws.slug} ${ws.slug === params.workspaceSlug ? "active" : ""}`}
              >
                {ws.name}
              </Link>
            ))}
          </nav>

          {snapshot.run && (
            <div className="sync-badge">
              <span className="sync-dot" />
              Synced {formatSyncTime(snapshot.run.syncedAt)}
            </div>
          )}
        </div>
      </header>

      <main className="harbor-main">
        {/* Stats Bar - Clickable Filters */}
        <div className="stats-bar">
          <Link
            href={`/${params.workspaceSlug}?filter=actionable`}
            className={`stat-chip filter-actionable ${activeFilter === "actionable" ? "active" : ""}`}
          >
            <span className="stat-value">{snapshot.stats.actionableCount}</span>
            <span className="stat-label">Needs Action</span>
          </Link>
          <Link
            href={`/${params.workspaceSlug}?filter=unread`}
            className={`stat-chip filter-unread ${activeFilter === "unread" ? "active" : ""}`}
          >
            <span className="stat-value">{snapshot.stats.unreadCount}</span>
            <span className="stat-label">Unread</span>
          </Link>
          <Link
            href={`/${params.workspaceSlug}?tab=drafts`}
            className={`stat-chip filter-drafts ${activeTab === "drafts" ? "active" : ""}`}
          >
            <span className="stat-value">{snapshot.stats.draftCount}</span>
            <span className="stat-label">Drafts Ready</span>
          </Link>
          {activeFilter !== "all" && (
            <Link href={`/${params.workspaceSlug}`} className="stat-chip">
              <span className="stat-label">Clear Filter</span>
            </Link>
          )}
        </div>

        {/* Content Tabs */}
        <ContentTabs
          workspaceSlug={params.workspaceSlug}
          activeTab={activeTab}
          itemCount={filteredItems.length}
          calendarCount={calendarItems.length}
          draftCount={snapshot.drafts.length}
        />

        {/* Tab Content */}
        {activeTab === "items" && (
          <ItemBoard
            items={filteredItems}
            workspaceSlug={params.workspaceSlug}
            filter={activeFilter}
          />
        )}

        {activeTab === "calendar" && (
          <CalendarPanel items={calendarItems} workspaceSlug={params.workspaceSlug} />
        )}

        {activeTab === "drafts" && (
          <DraftsPanel drafts={snapshot.drafts} workspaceSlug={params.workspaceSlug} />
        )}
      </main>
    </div>
  );
}
