"use client";

import { useTransition } from "react";
import { AssistantDraft } from "@/lib/contracts";
import { approveDraft, rejectDraft } from "./actions";

type DraftsPanelProps = {
  drafts: AssistantDraft[];
  workspaceSlug: string;
};

function DraftCard({
  draft,
  workspaceSlug,
}: {
  draft: AssistantDraft;
  workspaceSlug: string;
}) {
  const [isPending, startTransition] = useTransition();

  const handleApprove = () => {
    startTransition(() => {
      approveDraft(draft.id, workspaceSlug);
    });
  };

  const handleReject = () => {
    startTransition(() => {
      rejectDraft(draft.id, workspaceSlug);
    });
  };

  // Extract email context from the draft
  const subject = draft.context || "No subject";
  const recipient = draft.recipient || "Unknown recipient";

  // Parse recipients if they contain multiple
  const allRecipients = recipient.split(/[,;]/).map((r) => r.trim()).filter(Boolean);
  const toRecipients = allRecipients.slice(0, 3);
  const moreCount = allRecipients.length - 3;

  const isPendingReview = draft.status === "pending_review";

  return (
    <div className="draft-card" style={{ opacity: isPending ? 0.5 : 1 }}>
      <div className="draft-header">
        <div className="draft-context">
          <span className="draft-type">{draft.draftType}</span>
          <div className="draft-subject">{subject}</div>
          <div className="draft-recipients">
            <strong>To:</strong>{" "}
            {toRecipients.join(", ")}
            {moreCount > 0 && ` +${moreCount} more`}
          </div>
        </div>
        {!isPendingReview && (
          <span className={`status-pill ${draft.status === "approved" ? "done" : "watch"}`}>
            {draft.status}
          </span>
        )}
      </div>

      <div className="draft-body">
        <div className="draft-warning">
          <span>⚠</span>
          <span>Approving marks this draft as ready. It does NOT send the email automatically.</span>
        </div>

        <div className="draft-section">
          <div className="draft-section-label">Original Context</div>
          <div className="draft-email-preview">
            {draft.context || "No original email context available."}
          </div>
        </div>

        <div className="draft-section">
          <div className="draft-section-label">Suggested Response</div>
          <div className="draft-response">{draft.draft}</div>
        </div>
      </div>

      {isPendingReview && (
        <div className="draft-actions">
          <button
            className="action-btn success"
            onClick={handleApprove}
            disabled={isPending}
          >
            Approve Draft
          </button>
          <button
            className="action-btn danger"
            onClick={handleReject}
            disabled={isPending}
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}

export function DraftsPanel({ drafts, workspaceSlug }: DraftsPanelProps) {
  // Show pending first, then approved, then rejected
  const sorted = [...drafts].sort((a, b) => {
    const order = { pending_review: 0, approved: 1, rejected: 2 };
    const aOrder = order[a.status as keyof typeof order] ?? 3;
    const bOrder = order[b.status as keyof typeof order] ?? 3;
    return aOrder - bOrder;
  });

  if (sorted.length === 0) {
    return (
      <div className="board">
        <div className="empty-state">
          <div className="empty-state-icon">✉</div>
          <div className="empty-state-title">No drafts ready</div>
          <div className="empty-state-desc">
            When the assistant generates reply suggestions, they'll appear here for your review.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="drafts-grid">
      {sorted.map((draft) => (
        <DraftCard key={draft.id} draft={draft} workspaceSlug={workspaceSlug} />
      ))}
    </div>
  );
}
