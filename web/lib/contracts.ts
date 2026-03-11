export type WorkspaceSlug = "work" | "downer";

export type AssistantRun = {
  id: string;
  status: string;
  dayPlan: string;
  urgentItems: string[];
  sourceCounts: Record<string, number>;
  digestLocation: string;
  syncedAt: string;
};

export type AssistantItem = {
  id: string;
  runId: string;
  workspaceSlug: WorkspaceSlug;
  source: string;
  itemType: string;
  title: string;
  actor: string;
  occurredAt: string;
  isActionable: boolean;
  isUnread: boolean;
  payload: Record<string, unknown>;
};

export type AssistantDraft = {
  id: string;
  runId: string;
  workspaceSlug: WorkspaceSlug;
  draftType: string;
  recipient: string;
  context: string;
  draft: string;
  status: string;
  createdAt: string;
};

export type WorkspaceSnapshot = {
  workspace: {
    slug: WorkspaceSlug;
    name: string;
    strapline: string;
    accent: string;
    surface: string;
  };
  run: AssistantRun | null;
  items: AssistantItem[];
  drafts: AssistantDraft[];
  onboardingMode: boolean;
  stats: {
    actionableCount: number;
    unreadCount: number;
    draftCount: number;
    sourceCount: number;
  };
};
