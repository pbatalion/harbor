import { NextResponse } from "next/server";
import { getSupabaseServerClient } from "@/lib/supabase/server";

type RouteContext = {
  params: {
    id: string;
  };
};

const VALID_STATUSES = ["pending_review", "approved", "rejected", "sent"] as const;
type DraftStatus = (typeof VALID_STATUSES)[number];

function isValidStatus(value: unknown): value is DraftStatus {
  return typeof value === "string" && VALID_STATUSES.includes(value as DraftStatus);
}

export async function PATCH(request: Request, { params }: RouteContext) {
  const supabase = getSupabaseServerClient();
  if (!supabase) {
    return NextResponse.json({ error: "Supabase not configured" }, { status: 503 });
  }

  const { id } = params;
  if (!id) {
    return NextResponse.json({ error: "Draft ID is required" }, { status: 400 });
  }

  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (!isValidStatus(body.status)) {
    return NextResponse.json(
      { error: `Invalid status. Must be one of: ${VALID_STATUSES.join(", ")}` },
      { status: 400 }
    );
  }

  const { error } = await supabase.from("assistant_drafts").update({ status: body.status }).eq("id", id);

  if (error) {
    console.error("Failed to update draft:", error);
    return NextResponse.json({ error: "Failed to update draft" }, { status: 500 });
  }

  return NextResponse.json({ success: true, id, status: body.status });
}

export async function DELETE(_: Request, { params }: RouteContext) {
  const supabase = getSupabaseServerClient();
  if (!supabase) {
    return NextResponse.json({ error: "Supabase not configured" }, { status: 503 });
  }

  const { id } = params;
  if (!id) {
    return NextResponse.json({ error: "Draft ID is required" }, { status: 400 });
  }

  const { error } = await supabase.from("assistant_drafts").delete().eq("id", id);

  if (error) {
    console.error("Failed to delete draft:", error);
    return NextResponse.json({ error: "Failed to delete draft" }, { status: 500 });
  }

  return NextResponse.json({ success: true, id });
}
