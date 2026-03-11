import Link from "next/link";
import { notFound } from "next/navigation";
import { loadWorkspaceSnapshot } from "@/lib/dashboard";
import { isWorkspaceSlug, WORKSPACES } from "@/lib/workspaces";

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

export default async function WorkspacePage({ params }: PageProps) {
  if (!isWorkspaceSlug(params.workspaceSlug)) {
    notFound();
  }

  const snapshot = await loadWorkspaceSnapshot(params.workspaceSlug);

  return (
    <main className="page-shell">
      <section className="hero">
        <div className="hero-panel">
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
          <h1>Assistant Console</h1>
          <p>
            A workspace-first command surface for follow-through. The Python worker keeps ingesting Gmail,
            GitHub, calendar and Hedy; this UI turns the resulting queue into something you can actually work from.
          </p>
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
                ? `Last sync ${formatDate(snapshot.run.syncedAt)}. Latest run ${snapshot.run.id.slice(0, 8)}.`
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
            <h3 className="section-title">Action Queue</h3>
            <p className="section-subtitle">The latest synced items for this workspace, sorted by event time.</p>
            {snapshot.items.length === 0 ? (
              <div className="empty-state">
                {snapshot.onboardingMode
                  ? "No Supabase connection yet. Add the web env vars and sync completed runs from the Python worker."
                  : "No synced items for this workspace yet."}
              </div>
            ) : (
              <div className="list">
                {snapshot.items.slice(0, 14).map((item) => (
                  <article className="item-card" key={item.id}>
                    <div className="item-row">
                      <h3>{item.title}</h3>
                      <span className="tag">{formatDate(item.occurredAt)}</span>
                    </div>
                    <p className="meta">{item.actor || item.source}</p>
                    <div className="tag-row">
                      <span className="tag">{item.source}</span>
                      <span className="tag">{item.itemType}</span>
                      {item.isActionable ? <span className="tag">actionable</span> : null}
                      {item.isUnread ? <span className="tag">unread</span> : null}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>

        <aside className="stack">
          <section className="panel section">
            <h3 className="section-title">Draft Review</h3>
            <p className="section-subtitle">Draft-only mode stays intact. Edit here later, send elsewhere for now.</p>
            {snapshot.drafts.length === 0 ? (
              <div className="empty-state">No drafts synced for this workspace.</div>
            ) : (
              <div className="list">
                {snapshot.drafts.map((draft) => (
                  <article className="item-card" key={draft.id}>
                    <div className="item-row">
                      <h3>{draft.context}</h3>
                      <span className="tag">{draft.draftType}</span>
                    </div>
                    <p className="meta">{draft.recipient || "No explicit recipient"}</p>
                    <p className="meta mono">{draft.draft}</p>
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
                    <h3>Day Plan</h3>
                    <span className="tag">{snapshot.run.status}</span>
                  </div>
                  <p className="meta">{snapshot.run.dayPlan || "No day plan generated."}</p>
                </div>
                <div className="item-card">
                  <div className="item-row">
                    <h3>Urgent Items</h3>
                    <span className="tag">{snapshot.run.urgentItems.length}</span>
                  </div>
                  {snapshot.run.urgentItems.length === 0 ? (
                    <p className="meta">No urgent items flagged.</p>
                  ) : (
                    <div className="list">
                      {snapshot.run.urgentItems.map((item) => (
                        <p key={item} className="meta">
                          {item}
                        </p>
                      ))}
                    </div>
                  )}
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
