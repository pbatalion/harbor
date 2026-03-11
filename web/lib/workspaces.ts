import { WorkspaceSlug } from "./contracts";

export const WORKSPACES: Record<
  WorkspaceSlug,
  { slug: WorkspaceSlug; name: string; strapline: string; accent: string; surface: string }
> = {
  work: {
    slug: "work",
    name: "Work",
    strapline: "Network Craze inbox, GitHub and operating queue.",
    accent: "var(--tone-work)",
    surface: "var(--surface-work)",
  },
  downer: {
    slug: "downer",
    name: "Downer",
    strapline: "Camp Downer follow-through, calendar and meeting drift.",
    accent: "var(--tone-downer)",
    surface: "var(--surface-downer)",
  },
};

export function isWorkspaceSlug(value: string): value is WorkspaceSlug {
  return value === "work" || value === "downer";
}
