import { NextResponse } from "next/server";
import { getSupabaseServerClient } from "@/lib/supabase/server";

type RouteContext = {
  params: {
    id: string;
  };
};

type ItemUpdatePayload = {
  is_actionable?: boolean;
  is_unread?: boolean;
};

export async function PATCH(request: Request, { params }: RouteContext) {
  const supabase = getSupabaseServerClient();
  if (!supabase) {
    return NextResponse.json({ error: "Supabase not configured" }, { status: 503 });
  }

  const { id } = params;
  if (!id) {
    return NextResponse.json({ error: "Item ID is required" }, { status: 400 });
  }

  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const updates: ItemUpdatePayload = {};

  if (typeof body.is_actionable === "boolean") {
    updates.is_actionable = body.is_actionable;
  }
  if (typeof body.is_unread === "boolean") {
    updates.is_unread = body.is_unread;
  }

  if (Object.keys(updates).length === 0) {
    return NextResponse.json({ error: "No valid fields to update" }, { status: 400 });
  }

  const { error } = await supabase.from("assistant_items").update(updates).eq("id", id);

  if (error) {
    console.error("Failed to update item:", error);
    return NextResponse.json({ error: "Failed to update item" }, { status: 500 });
  }

  return NextResponse.json({ success: true, id, updates });
}
