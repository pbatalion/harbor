"use server";

import { revalidatePath } from "next/cache";
import { getSupabaseServerClient } from "@/lib/supabase/server";

export async function markItemDone(itemId: string, workspaceSlug: string) {
  const supabase = getSupabaseServerClient();
  if (!supabase) {
    return { success: false, error: "Supabase not configured" };
  }

  const { error } = await supabase
    .from("assistant_items")
    .update({ is_actionable: false, is_unread: false })
    .eq("id", itemId);

  if (error) {
    console.error("Failed to mark item done:", error);
    return { success: false, error: "Failed to update item" };
  }

  revalidatePath(`/${workspaceSlug}`);
  return { success: true };
}

export async function approveDraft(draftId: string, workspaceSlug: string) {
  const supabase = getSupabaseServerClient();
  if (!supabase) {
    return { success: false, error: "Supabase not configured" };
  }

  const { error } = await supabase
    .from("assistant_drafts")
    .update({ status: "approved" })
    .eq("id", draftId);

  if (error) {
    console.error("Failed to approve draft:", error);
    return { success: false, error: "Failed to update draft" };
  }

  revalidatePath(`/${workspaceSlug}`);
  return { success: true };
}

export async function rejectDraft(draftId: string, workspaceSlug: string) {
  const supabase = getSupabaseServerClient();
  if (!supabase) {
    return { success: false, error: "Supabase not configured" };
  }

  const { error } = await supabase
    .from("assistant_drafts")
    .update({ status: "rejected" })
    .eq("id", draftId);

  if (error) {
    console.error("Failed to reject draft:", error);
    return { success: false, error: "Failed to update draft" };
  }

  revalidatePath(`/${workspaceSlug}`);
  return { success: true };
}
