"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Global error:", error);
  }, [error]);

  return (
    <main className="page-shell">
      <section className="hero">
        <div className="hero-panel">
          <h1>Something went wrong</h1>
          <p>An unexpected error occurred while loading the page.</p>
          <div className="hero-callout">
            <strong>Error:</strong> {error.message || "Unknown error"}
          </div>
          <button
            onClick={() => reset()}
            style={{
              marginTop: "1rem",
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
        </div>
      </section>
    </main>
  );
}
