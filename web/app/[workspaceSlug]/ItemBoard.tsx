"use client";

import { useState, useTransition } from "react";
import { AssistantItem } from "@/lib/contracts";
import { markItemDone, prioritizeItem, archiveItem } from "./actions";

type ItemBoardProps = {
  items: AssistantItem[];
  workspaceSlug: string;
  filter: string;
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

function getStatusLabel(item: AssistantItem): { label: string; className: string } {
  if (item.isActionable) {
    return { label: "Action", className: "action" };
  }
  if (item.isUnread) {
    return { label: "Unread", className: "unread" };
  }
  return { label: "Seen", className: "watch" };
}

function getSourceIcon(source: string): string {
  if (source.includes("gmail")) return "✉";
  if (source.includes("github")) return "⚡";
  if (source.includes("calendar")) return "📅";
  if (source.includes("hedy")) return "🎙";
  return "📌";
}

function ItemRow({
  item,
  workspaceSlug,
}: {
  item: AssistantItem;
  workspaceSlug: string;
}) {
  const [isPending, startTransition] = useTransition();
  const status = getStatusLabel(item);
  const snippet =
    typeof item.payload.snippet === "string"
      ? item.payload.snippet
      : typeof item.payload.summary === "string"
        ? item.payload.summary
        : "";

  const handleDone = () => {
    startTransition(() => {
      markItemDone(item.id, workspaceSlug);
    });
  };

  const handlePrioritize = () => {
    startTransition(() => {
      prioritizeItem(item.id, workspaceSlug);
    });
  };

  const handleArchive = () => {
    startTransition(() => {
      archiveItem(item.id, workspaceSlug);
    });
  };

  const rowClass = item.isActionable ? "priority" : "";

  return (
    <div className={`board-row ${rowClass}`} style={{ opacity: isPending ? 0.5 : 1 }}>
      <div className="row-main">
        <div className="row-title">{item.title}</div>
        <div className="row-meta">
          <span className="row-source">
            {getSourceIcon(item.source)} {item.source.replace("gmail_", "").replace("_", " ")}
          </span>
          {item.actor && <span>{item.actor}</span>}
        </div>
        {snippet && <div className="row-snippet">{snippet}</div>}
      </div>

      <div className={`status-pill ${status.className}`}>{status.label}</div>

      <div className="row-date">{formatDate(item.occurredAt)}</div>

      <div className="row-actions">
        {item.isActionable ? (
          <button className="action-btn success" onClick={handleDone} disabled={isPending}>
            Done
          </button>
        ) : (
          <button className="action-btn" onClick={handlePrioritize} disabled={isPending}>
            Focus
          </button>
        )}
        <button className="action-btn danger" onClick={handleArchive} disabled={isPending}>
          Archive
        </button>
      </div>
    </div>
  );
}

export function ItemBoard({ items, workspaceSlug, filter }: ItemBoardProps) {
  if (items.length === 0) {
    return (
      <div className="board">
        <div className="empty-state">
          <div className="empty-state-icon">
            {filter === "actionable" ? "✓" : filter === "unread" ? "📭" : "📋"}
          </div>
          <div className="empty-state-title">
            {filter === "actionable"
              ? "All caught up!"
              : filter === "unread"
                ? "No unread items"
                : "No items yet"}
          </div>
          <div className="empty-state-desc">
            {filter === "actionable"
              ? "No items need your attention right now."
              : filter === "unread"
                ? "You've seen everything in this workspace."
                : "Items will appear here once the worker syncs data."}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="board">
      <div className="board-header">
        <div>Item</div>
        <div>Status</div>
        <div>Date</div>
        <div style={{ textAlign: "right" }}>Actions</div>
      </div>
      {items.map((item) => (
        <ItemRow key={item.id} item={item} workspaceSlug={workspaceSlug} />
      ))}
    </div>
  );
}
