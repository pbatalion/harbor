import { NextResponse } from "next/server";
import { loadWorkspaceSnapshot } from "@/lib/dashboard";
import { isWorkspaceSlug } from "@/lib/workspaces";

type RouteContext = {
  params: {
    workspaceSlug: string;
  };
};

export async function GET(_: Request, { params }: RouteContext) {
  if (!isWorkspaceSlug(params.workspaceSlug)) {
    return NextResponse.json({ error: "unknown workspace" }, { status: 404 });
  }

  const snapshot = await loadWorkspaceSnapshot(params.workspaceSlug);
  return NextResponse.json(snapshot);
}
