import Link from "next/link";
import { notFound } from "next/navigation";
import { loadWorkspaceSnapshot } from "@/lib/dashboard";
import { isWorkspaceSlug, WORKSPACES } from "@/lib/workspaces";
import { AssistantItem } from "@/lib/contracts";
import { MarkDoneButton, DraftActionButtons } from "./ActionButtons";

type PageProps = {
  params: {
    workspaceSlug: string;
  };
};

function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function getItemSummary(item: AssistantItem): string {
  const snippet = typeof item.payload.snippet === "string" ? item.payload.snippet.trim() : "";
  if (snippet) {
    return snippet;
  }

  const summary = typeof item.payload.summary === "string" ? item.payload.summary.trim() : "";
  if (summary) {
    return summary;
  }

  if (item.itemType === "calendar") {
    const start = typeof item.payload.start === "string" ? item.payload.start : "";
    return start ? `Scheduled for ${formatDate(start)}.` : "Calendar event synced.";
  }

  if (item.itemType === "github") {
    return "GitHub issue or workflow activity synced into this workspace.";
  }

  if (item.itemType === "transcript") {
    return "Meeting transcript or action item synced from Hedy.";
  }

  return "No additional preview available yet.";
}

function getItemTone(item: AssistantItem): "priority" | "active" | "watch" {
  if (item.isActionable) {
    return "priority";
  }
  if (item.isUnread) {
    return "active";
  }
  return "watch";
}

export default async function WorkspacePage({ params }: PageProps) {
  if (!isWorkspaceSlug(params.workspaceSlug)) {
    notFound();
  }

  const snapshot = await loadWorkspaceSnapshot(params.workspaceSlug);
  const actionableItems = snapshot.items.filter((item) => item.isActionable);
  const unreadItems = snapshot.items.filter((item) => item.isUnread);
  const focusItems = snapshot.items.filter((item) => item.isActionable || item.isUnread).slice(0, 8);
  const watchItems = snapshot.items.filter((item) => !item.isActionable).slice(0, 10);
  const sourceSummary = Object.entries(snapshot.run?.sourceCounts ?? {}).sort((a, b) => b[1] - a[1]);

  return (
    <main className="page-shell">
      <section className="hero">
        <div className="hero-panel">
          <div className="hero-topline">
            <div className="workspace-nav">
              {Object.values(WORKSPACES).map((workspace) => (
                <Link
                  key={workspace.slug}
                  href={`/${workspace.slug}`}
                  className={`workspace-pill ${workspace.slug === snapshot.workspace.slug ? "active" : ""}`}
                  style={{ color: workspace.accent }}
                >
                  {workspace.name}
                </Link>
              ))}
            </div>
            {snapshot.run ? <span className="hero-sync">Synced {formatDate(snapshot.run.syncedAt)}</span> : null}
          </div>
          <h1>Assistant Console</h1>
          <p>
            Harbor keeps work and Downer separate, shows what actually needs attention, and keeps draft replies close
            to the activity that created them.
          </p>
          <div className="hero-callout">
            <strong>Right now:</strong>{" "}
            {snapshot.run
              ? `${actionableItems.length} items likely need action, ${unreadItems.length} are unread, and ${snapshot.drafts.length} drafts are waiting.`
              : "Connect a synced run to turn this into a live workspace queue."}
          </div>
        </div>
      </section>

      <div className="dashboard-grid">
        <section className="panel" style={{ background: snapshot.workspace.surface }}>
          <div className="workspace-header" style={{ color: snapshot.workspace.accent }}>
            <div className="eyebrow">
              <span className="dot" />
              {snapshot.workspace.name}
            </div>
            <h2>{snapshot.workspace.strapline}</h2>
            <p>
              {snapshot.run
                ? `Latest run ${snapshot.run.id.slice(0, 8)} completed ${formatDate(snapshot.run.syncedAt)}. Start with the focus queue, then work drafts from the right rail.`
                : "Connect Supabase and let the worker sync completed runs to populate this workspace."}
            </p>

            <div className="stat-grid">
              <div className="stat-card">
                <span>Actionable</span>
                <strong>{snapshot.stats.actionableCount}</strong>
              </div>
              <div className="stat-card">
                <span>Unread</span>
                <strong>{snapshot.stats.unreadCount}</strong>
              </div>
              <div className="stat-card">
                <span>Drafts</span>
                <strong>{snapshot.stats.draftCount}</strong>
              </div>
              <div className="stat-card">
                <span>Sources</span>
                <strong>{snapshot.stats.sourceCount}</strong>
              </div>
            </div>
          </div>

          <div className="section">
            <div className="section-heading">
              <div>
                <h3 className="section-title">Focus Queue</h3>
                <p className="section-subtitle">Prioritized items that are either actionable or still unread.</p>
              </div>
              <div className="tag-row">
                <span className="tag emphasis">Do now {actionableItems.length}</span>
                <span className="tag">Unread {unreadItems.length}</span>
              </div>
            </div>
            {focusItems.length === 0 ? (
              <div className="empty-state">
                {snapshot.onboardingMode
                  ? "No Supabase connection yet. Add the web env vars and sync completed runs from the Python worker."
                  : "No current focus items for this workspace."}
              </div>
            ) : (
              <div className="queue-list">
                {focusItems.map((item) => (
                  <article className={`item-card queue-card tone-${getItemTone(item)}`} key={item.id}>
                    <div className="item-row">
                      <div>
                        <h3>{item.title}</h3>
                        <p className="meta">{item.actor || item.source}</p>
                      </div>
                      <div className="item-actions">
                        <span className="tag">{formatDate(item.occurredAt)}</span>
                        {item.isActionable ? (
                          <MarkDoneButton itemId={item.id} workspaceSlug={snapshot.workspace.slug} />
                        ) : null}
                      </div>
                    </div>
                    <p className="summary-copy">{getItemSummary(item)}</p>
                    <div className="tag-row">
                      <span className="tag">{item.source}</span>
                      <span className="tag">{item.itemType}</span>
                      {item.isActionable ? <span className="tag emphasis">needs action</span> : null}
                      {item.isUnread ? <span className="tag active">unread</span> : null}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>

          <div className="section">
            <div className="section-heading">
              <div>
                <h3 className="section-title">Recent Activity</h3>
                <p className="section-subtitle">Everything else that landed recently but is less urgent.</p>
              </div>
            </div>
            {watchItems.length === 0 ? (
              <div className="empty-state">No lower-priority items are queued right now.</div>
            ) : (
              <div className="list compact-list">
                {watchItems.map((item) => (
                  <article className="item-card compact-card" key={item.id}>
                    <div className="item-row">
                      <h3>{item.title}</h3>
                      <span className="tag subtle">{formatDate(item.occurredAt)}</span>
                    </div>
                    <p className="meta">{item.actor || item.source}</p>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>

        <aside className="stack">
          <section className="panel section">
            <div className="section-heading">
              <div>
                <h3 className="section-title">Draft Review</h3>
                <p className="section-subtitle">Prepared replies and follow-ups, ready for copy/edit/send.</p>
              </div>
              <span className="tag emphasis">{snapshot.drafts.length} ready</span>
            </div>
            {snapshot.drafts.length === 0 ? (
              <div className="empty-state">No drafts synced for this workspace.</div>
            ) : (
              <div className="list">
                {snapshot.drafts.map((draft) => (
                  <article className="item-card" key={draft.id}>
                    <div className="item-row">
                      <h3>{draft.context}</h3>
                      <span className="tag emphasis">{draft.draftType}</span>
                    </div>
                    <p className="meta">{draft.recipient || "No explicit recipient"}</p>
                    <p className="draft-copy mono">{draft.draft}</p>
                    {draft.status === "pending_review" ? (
                      <DraftActionButtons draftId={draft.id} workspaceSlug={snapshot.workspace.slug} />
                    ) : (
                      <span className="tag">{draft.status}</span>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="panel section">
            <h3 className="section-title">Run Snapshot</h3>
            {snapshot.run ? (
              <div className="list">
                <div className="item-card">
                  <div className="item-row">
                    <h3>Recommended Plan</h3>
                    <span className="tag emphasis">{snapshot.run.status}</span>
                  </div>
                  <p className="summary-copy">{snapshot.run.dayPlan || "No day plan generated."}</p>
                </div>
                <div className="item-card">
                  <div className="item-row">
                    <h3>Urgent Items</h3>
                    <span className="tag active">{snapshot.run.urgentItems.length}</span>
                  </div>
                  {snapshot.run.urgentItems.length === 0 ? (
                    <p className="meta">No urgent items flagged.</p>
                  ) : (
                    <div className="list compact-list">
                      {snapshot.run.urgentItems.map((item) => (
                        <p key={item} className="summary-copy">
                          {item}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
                <div className="item-card">
                  <div className="item-row">
                    <h3>Source Mix</h3>
                    <span className="tag">{sourceSummary.length}</span>
                  </div>
                  <div className="tag-row">
                    {sourceSummary.map(([source, count]) => (
                      <span key={source} className="tag subtle">
                        {source} {count}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="item-card">
                  <div className="item-row">
                    <h3>Digest Artifact</h3>
                    <span className="tag mono">{snapshot.run.id.slice(0, 8)}</span>
                  </div>
                  <p className="meta mono">{snapshot.run.digestLocation || "No local digest path stored."}</p>
                </div>
              </div>
            ) : (
              <div className="empty-state">No completed run is synced yet.</div>
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}
