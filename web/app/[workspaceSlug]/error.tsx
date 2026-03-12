"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function WorkspaceError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Workspace error:", error);
  }, [error]);

  return (
    <main className="page-shell">
      <section className="hero">
        <div className="hero-panel">
          <div className="hero-topline">
            <Link href="/" className="workspace-pill">
              Back to Home
            </Link>
          </div>
          <h1>Workspace Error</h1>
          <p>Failed to load this workspace. This might be a temporary issue with Supabase or data sync.</p>
          <div className="hero-callout">
            <strong>Error:</strong> {error.message || "Unknown error"}
          </div>
          <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem" }}>
            <button
              onClick={() => reset()}
              style={{
                padding: "0.5rem 1rem",
                background: "var(--accent-work)",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
              }}
            >
              Try again
            </button>
            <Link
              href="/"
              style={{
                padding: "0.5rem 1rem",
                background: "var(--surface-alt)",
                color: "var(--text-primary)",
                border: "1px solid var(--border)",
                borderRadius: "4px",
                textDecoration: "none",
              }}
            >
              Go Home
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
