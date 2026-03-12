"use client";

import { useTransition } from "react";
import { markItemDone, approveDraft, rejectDraft } from "./actions";

type MarkDoneButtonProps = {
  itemId: string;
  workspaceSlug: string;
};

export function MarkDoneButton({ itemId, workspaceSlug }: MarkDoneButtonProps) {
  const [isPending, startTransition] = useTransition();

  return (
    <button
      className="action-btn"
      disabled={isPending}
      onClick={() => {
        startTransition(async () => {
          await markItemDone(itemId, workspaceSlug);
        });
      }}
    >
      {isPending ? "..." : "Done"}
    </button>
  );
}

type DraftActionButtonsProps = {
  draftId: string;
  workspaceSlug: string;
};

export function DraftActionButtons({ draftId, workspaceSlug }: DraftActionButtonsProps) {
  const [isPending, startTransition] = useTransition();

  return (
    <div className="action-btn-group">
      <button
        className="action-btn action-btn-approve"
        disabled={isPending}
        onClick={() => {
          startTransition(async () => {
            await approveDraft(draftId, workspaceSlug);
          });
        }}
      >
        {isPending ? "..." : "Approve"}
      </button>
      <button
        className="action-btn action-btn-reject"
        disabled={isPending}
        onClick={() => {
          startTransition(async () => {
            await rejectDraft(draftId, workspaceSlug);
          });
        }}
      >
        {isPending ? "..." : "Reject"}
      </button>
    </div>
  );
}
