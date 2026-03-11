import { AssistantDraft, AssistantItem, AssistantRun, WorkspaceSnapshot, WorkspaceSlug } from "./contracts";
import { getSupabaseServerClient } from "./supabase/server";
import { WORKSPACES } from "./workspaces";

function emptySnapshot(workspaceSlug: WorkspaceSlug): WorkspaceSnapshot {
  return {
    workspace: WORKSPACES[workspaceSlug],
    run: null,
    items: [],
    drafts: [],
    onboardingMode: true,
    stats: {
      actionableCount: 0,
      unreadCount: 0,
      draftCount: 0,
      sourceCount: 0,
    },
  };
}

export async function loadWorkspaceSnapshot(workspaceSlug: WorkspaceSlug): Promise<WorkspaceSnapshot> {
  const supabase = getSupabaseServerClient();
  if (!supabase) {
    return emptySnapshot(workspaceSlug);
  }

  const { data: runRow } = await supabase
    .from("assistant_runs")
    .select("id,status,day_plan,urgent_items,source_counts,digest_location,synced_at")
    .order("synced_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (!runRow) {
    return emptySnapshot(workspaceSlug);
  }

  const run: AssistantRun = {
    id: String(runRow.id),
    status: String(runRow.status),
    dayPlan: String(runRow.day_plan ?? ""),
    urgentItems: Array.isArray(runRow.urgent_items) ? runRow.urgent_items.map(String) : [],
    sourceCounts:
      typeof runRow.source_counts === "object" && runRow.source_counts ? (runRow.source_counts as Record<string, number>) : {},
    digestLocation: String(runRow.digest_location ?? ""),
    syncedAt: String(runRow.synced_at ?? ""),
  };

  const [{ data: itemsRows }, { data: draftsRows }] = await Promise.all([
    supabase
      .from("assistant_items")
      .select("id,run_id,workspace_slug,source,item_type,title,actor,occurred_at,is_actionable,is_unread,payload")
      .eq("run_id", run.id)
      .eq("workspace_slug", workspaceSlug)
      .order("occurred_at", { ascending: false })
      .limit(40),
    supabase
      .from("assistant_drafts")
      .select("id,run_id,workspace_slug,draft_type,recipient,context,draft,status,created_at")
      .eq("run_id", run.id)
      .eq("workspace_slug", workspaceSlug)
      .order("created_at", { ascending: false })
      .limit(20),
  ]);

  const items: AssistantItem[] = (itemsRows ?? []).map((row) => ({
    id: String(row.id),
    runId: String(row.run_id),
    workspaceSlug,
    source: String(row.source),
    itemType: String(row.item_type),
    title: String(row.title),
    actor: String(row.actor ?? ""),
    occurredAt: String(row.occurred_at),
    isActionable: Boolean(row.is_actionable),
    isUnread: Boolean(row.is_unread),
    payload: row.payload && typeof row.payload === "object" ? (row.payload as Record<string, unknown>) : {},
  }));

  const drafts: AssistantDraft[] = (draftsRows ?? []).map((row) => ({
    id: String(row.id),
    runId: String(row.run_id),
    workspaceSlug,
    draftType: String(row.draft_type),
    recipient: String(row.recipient ?? ""),
    context: String(row.context),
    draft: String(row.draft),
    status: String(row.status),
    createdAt: String(row.created_at),
  }));

  return {
    workspace: WORKSPACES[workspaceSlug],
    run,
    items,
    drafts,
    onboardingMode: false,
    stats: {
      actionableCount: items.filter((item) => item.isActionable).length,
      unreadCount: items.filter((item) => item.isUnread).length,
      draftCount: drafts.length,
      sourceCount: Object.keys(run.sourceCounts).length,
    },
  };
}
