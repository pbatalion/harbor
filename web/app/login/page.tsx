type LoginPageProps = {
  searchParams?: {
    next?: string;
  };
};

export default function LoginPage({ searchParams }: LoginPageProps) {
  const next = searchParams?.next || "/work";

  return (
    <main className="page-shell">
      <section className="hero">
        <div className="hero-panel">
          <h1>Assistant Access</h1>
          <p>
            This console is intentionally server-rendered and password-gated. It is reading synced run data that may
            include email and meeting context, so it should not be public.
          </p>
        </div>
      </section>

      <section className="panel section" style={{ maxWidth: 520, margin: "0 auto" }}>
        <h2 className="section-title">Sign In</h2>
        <p className="section-subtitle">Set `ASSISTANT_WEB_PASSWORD` in Vercel and in `web/.env.local` for local use.</p>
        <form method="post" action="/api/session" className="list">
          <input type="hidden" name="next" value={next} />
          <label className="item-card">
            <div className="meta">Password</div>
            <input
              type="password"
              name="password"
              required
              style={{
                width: "100%",
                marginTop: 10,
                padding: "14px 16px",
                borderRadius: 16,
                border: "1px solid var(--line)",
                background: "rgba(255,255,255,0.72)",
                color: "var(--ink)",
                fontSize: "1rem",
              }}
            />
          </label>
          <button
            type="submit"
            style={{
              border: "none",
              borderRadius: 999,
              padding: "14px 18px",
              background: "var(--ink)",
              color: "white",
              fontSize: "0.95rem",
              cursor: "pointer",
            }}
          >
            Enter Console
          </button>
        </form>
      </section>
    </main>
  );
}
