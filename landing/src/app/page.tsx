import Link from "next/link";

const GITHUB = "https://github.com/Matthew-Selvam/open-dispatch";

const PLATFORMS = [
  { name: "Twitter / X",   icon: "𝕏",  color: "#e5e7eb" },
  { name: "Bluesky",       icon: "🦋", color: "#0085ff" },
  { name: "Instagram",     icon: "📷", color: "#e1306c" },
  { name: "Threads",       icon: "🧵", color: "#e5e7eb" },
  { name: "LinkedIn",      icon: "💼", color: "#0a66c2" },
  { name: "Telegram",      icon: "✈️",  color: "#2ca5e0" },
  { name: "YouTube Shorts",icon: "▶️",  color: "#ff0000" },
];

const FEATURES = [
  {
    icon: "⚡",
    title: "API-first",
    body: "Every action reachable via a single HTTP call. No dashboard lock-in — automate from cron, n8n, AI agents, or your own app.",
  },
  {
    icon: "🖥️",
    title: "Web UI included",
    body: "HTMX-powered dark dashboard. Compose, retry, and watch the queue live — same port, zero JS build step.",
  },
  {
    icon: "🏗️",
    title: "3 queue backends",
    body: "JSONL on disk (zero infra), Redis (multi-worker), or Postgres (ACID + SKIP LOCKED). Swap with one env var.",
  },
  {
    icon: "🤖",
    title: "AI caption adaptation",
    body: "One source text → per-platform rewrites. Ollama-first, OpenRouter fallback, heuristic safety net. Never 500s.",
  },
  {
    icon: "🖼️",
    title: "Media transcoding",
    body: "10 platform image specs out of the box (square, reels, 16:9, portrait…). REST endpoint + Python API.",
  },
  {
    icon: "🔌",
    title: "n8n community node",
    body: "Native n8n integration: Dispatch, Adapt, Get Row, Retry, List Queue — all 5 ops, zero JSON wiring.",
  },
];

const DISPATCH_SNIPPET = `curl -X POST http://localhost:8000/dispatch \\
  -H "Content-Type: application/json" \\
  -d '{
  "targets": [
    "twitter:default",
    "bluesky:default",
    "telegram:default",
    "threads:default"
  ],
  "formats": {
    "twitter_thread":   { "tweets": ["just shipped v0.4"] },
    "bluesky_post":     { "text": "just shipped v0.4" },
    "telegram_message": { "text": "just shipped v0.4" },
    "threads_post":     { "text": "just shipped v0.4" }
  }
}'`;

const QUICKSTART_SNIPPET = `git clone https://github.com/Matthew-Selvam/open-dispatch
cd open-dispatch
cp .env.example .env   # fill in the creds you actually use
docker compose up -d
curl http://localhost:8000/healthz   # → {"status":"ok"}
open http://localhost:8000/          # web UI`;

export default function Page() {
  return (
    <>
      {/* ── NAV ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-bg)]/90 backdrop-blur">
        <div className="mx-auto max-w-6xl px-6 h-14 flex items-center justify-between">
          <span className="font-mono text-sm font-semibold text-[var(--color-fg)] tracking-tight">
            open<span className="text-[var(--color-accent)]">-dispatch</span>
          </span>
          <nav className="flex items-center gap-6 text-sm text-[var(--color-body)]">
            <a href="#features" className="hover:text-[var(--color-fg)] transition-colors">Features</a>
            <a href="#quickstart" className="hover:text-[var(--color-fg)] transition-colors">Quickstart</a>
            <a href="#api" className="hover:text-[var(--color-fg)] transition-colors">API</a>
            <Link
              href={GITHUB}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 flex items-center gap-1.5 rounded border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium text-[var(--color-fg)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors"
            >
              <GitHubIcon /> GitHub
            </Link>
          </nav>
        </div>
      </header>

      <main>
        {/* ── HERO ──────────────────────────────────────────────────────── */}
        <section className="relative overflow-hidden border-b border-[var(--color-border)]">
          {/* subtle grid bg */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-[0.04]"
            style={{
              backgroundImage:
                "linear-gradient(var(--color-fg) 1px, transparent 1px), linear-gradient(90deg, var(--color-fg) 1px, transparent 1px)",
              backgroundSize: "40px 40px",
            }}
          />
          <div className="relative mx-auto max-w-6xl px-6 py-24 md:py-36 grid md:grid-cols-2 gap-16 items-center">
            {/* copy */}
            <div>
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1 text-xs font-mono text-[var(--color-body)]">
                <span className="size-1.5 rounded-full bg-green-400 animate-pulse" />
                v0.4.0 — MIT licensed
              </div>
              <h1 className="font-sans text-5xl sm:text-6xl font-bold leading-[1.1] tracking-tight text-[var(--color-fg)]">
                One API to{" "}
                <span className="text-[var(--color-accent)]">dispatch</span>
                <br />
                your content
                <br />
                anywhere.
              </h1>
              <p className="mt-6 text-base text-[var(--color-body)] leading-relaxed max-w-lg">
                API-first infrastructure layer for content distribution. Like
                Stripe for payments — except for posting. One HTTP call, seven
                platforms, zero vendor lock-in. Self-host free.
              </p>

              {/* platform chips */}
              <div className="mt-6 flex flex-wrap gap-2">
                {PLATFORMS.map((p) => (
                  <span
                    key={p.name}
                    className="flex items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1 text-xs text-[var(--color-body)]"
                  >
                    {p.icon} {p.name}
                  </span>
                ))}
              </div>

              {/* CTAs */}
              <div className="mt-10 flex flex-wrap gap-3">
                <Link
                  href={GITHUB}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded bg-[var(--color-accent)] px-5 py-2.5 text-sm font-semibold text-white hover:opacity-90 transition-opacity"
                >
                  <GitHubIcon /> Star on GitHub
                </Link>
                <a
                  href="#quickstart"
                  className="inline-flex items-center gap-2 rounded border border-[var(--color-border)] px-5 py-2.5 text-sm font-semibold text-[var(--color-fg)] hover:border-[var(--color-accent)] transition-colors"
                >
                  Quick start →
                </a>
              </div>
            </div>

            {/* code card */}
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden shadow-2xl shadow-black/50">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--color-border)]">
                <span className="size-3 rounded-full bg-red-500/60" />
                <span className="size-3 rounded-full bg-yellow-500/60" />
                <span className="size-3 rounded-full bg-green-500/60" />
                <span className="ml-3 font-mono text-xs text-[var(--color-muted)]">dispatch.sh</span>
              </div>
              <pre className="overflow-x-auto p-5 text-xs font-mono leading-relaxed text-[var(--color-body)] whitespace-pre">
                <HighlightedCurl code={DISPATCH_SNIPPET} />
              </pre>
            </div>
          </div>
        </section>

        {/* ── FEATURES ──────────────────────────────────────────────────── */}
        <section id="features" className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <h2 className="text-center text-2xl font-bold tracking-tight text-[var(--color-fg)] mb-12">
              Everything you need. Nothing you don&apos;t.
            </h2>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {FEATURES.map((f) => (
                <div
                  key={f.title}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6"
                >
                  <div className="text-2xl mb-3">{f.icon}</div>
                  <h3 className="font-semibold text-[var(--color-fg)] mb-2">{f.title}</h3>
                  <p className="text-sm text-[var(--color-body)] leading-relaxed">{f.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── QUICK START ───────────────────────────────────────────────── */}
        <section id="quickstart" className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20 grid md:grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-[var(--color-fg)] mb-4">
                Up in 60 seconds.
              </h2>
              <p className="text-[var(--color-body)] leading-relaxed mb-6">
                Clone, drop in your platform credentials, and run. No database
                setup, no cloud account — it works out of the box with a flat
                JSONL queue. Upgrade to Redis or Postgres when you need
                multi-worker throughput.
              </p>
              <ul className="space-y-3 text-sm text-[var(--color-body)]">
                {[
                  "Docker Compose self-host — one command",
                  "JSONL queue (zero infra) → Redis → Postgres",
                  "Credentials stay in your .env, never leave your host",
                  "Web UI + REST API on the same port",
                  "n8n node, CLI, and Python API also included",
                ].map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="text-[var(--color-accent)] shrink-0">✓</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--color-border)]">
                <span className="size-3 rounded-full bg-red-500/60" />
                <span className="size-3 rounded-full bg-yellow-500/60" />
                <span className="size-3 rounded-full bg-green-500/60" />
                <span className="ml-3 font-mono text-xs text-[var(--color-muted)]">quickstart</span>
              </div>
              <pre className="overflow-x-auto p-5 text-xs font-mono leading-relaxed text-[var(--color-body)] whitespace-pre">
                {QUICKSTART_SNIPPET}
              </pre>
            </div>
          </div>
        </section>

        {/* ── API REFERENCE ─────────────────────────────────────────────── */}
        <section id="api" className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <h2 className="text-2xl font-bold tracking-tight text-[var(--color-fg)] mb-3">
              Simple, stable API.
            </h2>
            <p className="text-[var(--color-body)] mb-10 max-w-2xl">
              Every endpoint is available via HTTP. Content negotiation on{" "}
              <code className="text-xs font-mono bg-[var(--color-surface)] border border-[var(--color-border)] px-1.5 py-0.5 rounded">
                /queue/&#123;id&#125;
              </code>
              {" "}— browsers get the HTML detail page, API clients get JSON.
            </p>
            <div className="overflow-x-auto rounded-xl border border-[var(--color-border)]">
              <table className="w-full text-sm font-mono">
                <thead>
                  <tr className="border-b border-[var(--color-border)] bg-[var(--color-surface)]">
                    <th className="px-5 py-3 text-left text-xs font-semibold text-[var(--color-muted)] uppercase tracking-wider">Method</th>
                    <th className="px-5 py-3 text-left text-xs font-semibold text-[var(--color-muted)] uppercase tracking-wider">Path</th>
                    <th className="px-5 py-3 text-left text-xs font-semibold text-[var(--color-muted)] uppercase tracking-wider">Purpose</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {[
                    ["GET",  "/healthz",            "Liveness probe"],
                    ["POST", "/dispatch",           "Enqueue a ContentUnit"],
                    ["GET",  "/queue?status=…",     "List rows (queued/publishing/published/failed/dead)"],
                    ["GET",  "/queue/{id}",         "One row — JSON or HTML (content-negotiated)"],
                    ["POST", "/queue/{id}/retry",   "Re-queue a failed or dead row"],
                    ["POST", "/ai/adapt",           "Rewrite a caption for each platform"],
                    ["POST", "/media/transcode",    "Resize image to a platform spec"],
                    ["GET",  "/media/specs",        "List all 10 platform image specs"],
                  ].map(([method, path, purpose]) => (
                    <tr key={path} className="hover:bg-[var(--color-surface)]/50 transition-colors">
                      <td className="px-5 py-3 text-xs">
                        <span className={`font-semibold ${method === "GET" ? "text-[var(--color-accent)]" : "text-green-400"}`}>
                          {method}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-xs text-[var(--color-fg)]">{path}</td>
                      <td className="px-5 py-3 text-xs text-[var(--color-body)]">{purpose}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* ── ARCHITECTURE ──────────────────────────────────────────────── */}
        <section className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20 grid md:grid-cols-2 gap-16 items-start">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-[var(--color-fg)] mb-4">
                Adapter contract: 80 LOC.
              </h2>
              <p className="text-[var(--color-body)] leading-relaxed mb-4">
                Every platform adapter exposes one function. Adding a new
                platform is a single file — no framework magic, no base classes.
                The worker does the rest.
              </p>
              <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
                <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--color-border)]">
                  <span className="ml-1 font-mono text-xs text-[var(--color-muted)]">adapters/myplatform.py</span>
                </div>
                <pre className="p-5 text-xs font-mono leading-relaxed whitespace-pre">
<span className="token-keyword">def</span> <span className="text-[var(--color-fg)]">publish</span>(<span className="text-[var(--color-fg)]">unit</span>: <span className="token-keyword">ContentUnit</span>, <span className="text-[var(--color-fg)]">account</span>: <span className="token-keyword">str | None</span>){"\n"}  <span className="token-comment">-&gt; tuple[bool, str, str]:</span>{"\n"}    <span className="token-comment">"""Returns (ok, post_id, error_message)."""</span>{"\n"}    <span className="token-comment">...</span>
                </pre>
              </div>
            </div>

            <div>
              <h2 className="text-2xl font-bold tracking-tight text-[var(--color-fg)] mb-4">
                Architecture at a glance.
              </h2>
              <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
                <pre className="p-5 text-xs font-mono leading-[1.9] text-[var(--color-body)] whitespace-pre">
{`POST /dispatch
   │
   ▼
Queue (JSONL │ Redis │ Postgres)
   │
   ▼
scheduler/worker.py
   │
   ├─▶ adapters/twitter.py
   ├─▶ adapters/bluesky.py
   ├─▶ adapters/instagram.py
   ├─▶ adapters/telegram.py
   ├─▶ adapters/linkedin.py
   ├─▶ adapters/threads.py
   └─▶ adapters/youtube.py
          │
          ▼  on publish / fail
      webhook_url`}
                </pre>
              </div>
            </div>
          </div>
        </section>

        {/* ── N8N ───────────────────────────────────────────────────────── */}
        <section className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20 text-center">
            <div className="text-4xl mb-4">🔌</div>
            <h2 className="text-2xl font-bold tracking-tight text-[var(--color-fg)] mb-3">
              Native n8n integration.
            </h2>
            <p className="text-[var(--color-body)] max-w-xl mx-auto mb-8">
              Community node ships in the repo. Five operations, zero JSON
              wiring. Dispatch, adapt, get row, retry, list queue — all from
              the visual editor.
            </p>
            <div className="inline-flex flex-wrap justify-center gap-3">
              {["Dispatch", "Adapt Caption", "Get Row", "Retry Row", "List Queue"].map((op) => (
                <span
                  key={op}
                  className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2 text-sm text-[var(--color-body)]"
                >
                  {op}
                </span>
              ))}
            </div>
            <div className="mt-8 font-mono text-xs text-[var(--color-muted)] bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-5 py-3 inline-block">
              cd n8n-node &amp;&amp; npm install &amp;&amp; npm run build
            </div>
          </div>
        </section>

        {/* ── FINAL CTA ─────────────────────────────────────────────────── */}
        <section>
          <div className="mx-auto max-w-6xl px-6 py-24 text-center">
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[var(--color-fg)] mb-4">
              Ready to dispatch?
            </h2>
            <p className="text-[var(--color-body)] max-w-lg mx-auto mb-10">
              MIT licensed. Self-host forever free. No accounts, no API keys
              to us — just your platform credentials in a .env file.
            </p>
            <div className="flex flex-wrap justify-center gap-4">
              <Link
                href={GITHUB}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded bg-[var(--color-accent)] px-6 py-3 text-sm font-semibold text-white hover:opacity-90 transition-opacity"
              >
                <GitHubIcon /> View on GitHub
              </Link>
              <Link
                href={`${GITHUB}/releases`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded border border-[var(--color-border)] px-6 py-3 text-sm font-semibold text-[var(--color-fg)] hover:border-[var(--color-accent)] transition-colors"
              >
                Release notes
              </Link>
            </div>
            <p className="mt-8 text-xs text-[var(--color-muted)]">
              129 tests · 7 platforms · 3 queue backends · 0 cloud dependencies
            </p>
          </div>
        </section>
      </main>

      {/* ── FOOTER ────────────────────────────────────────────────────────── */}
      <footer className="border-t border-[var(--color-border)] py-8">
        <div className="mx-auto max-w-6xl px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[var(--color-muted)]">
          <span className="font-mono">open-dispatch — MIT License</span>
          <div className="flex gap-6">
            <Link href={GITHUB} target="_blank" rel="noopener noreferrer" className="hover:text-[var(--color-fg)] transition-colors">GitHub</Link>
            <Link href={`${GITHUB}/releases`} target="_blank" rel="noopener noreferrer" className="hover:text-[var(--color-fg)] transition-colors">Releases</Link>
            <Link href={`${GITHUB}/blob/main/CONTRIBUTING.md`} target="_blank" rel="noopener noreferrer" className="hover:text-[var(--color-fg)] transition-colors">Contributing</Link>
            <Link href={`${GITHUB}/blob/main/SECURITY.md`} target="_blank" rel="noopener noreferrer" className="hover:text-[var(--color-fg)] transition-colors">Security</Link>
          </div>
        </div>
      </footer>
    </>
  );
}

/* ── helpers ──────────────────────────────────────────────────────────────── */

function GitHubIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" aria-hidden>
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

/** Very lightweight curl syntax highlighter — no dependencies. */
function HighlightedCurl({ code }: { code: string }) {
  // Split by lines and apply inline spans. Good enough for a static landing page.
  const lines = code.split("\n");
  return (
    <>
      {lines.map((line, i) => {
        if (line.startsWith("curl")) {
          return (
            <span key={i}>
              <span className="text-[#79d1ff]">curl</span>
              {line.slice(4)}
              {"\n"}
            </span>
          );
        }
        if (line.trim().startsWith('"') && line.includes(":")) {
          const colonIdx = line.indexOf(":");
          return (
            <span key={i}>
              <span className="token-key">{line.slice(0, colonIdx + 1)}</span>
              {line.slice(colonIdx + 1)}
              {"\n"}
            </span>
          );
        }
        if (line.trim() === "'") {
          return <span key={i}>{line}{"\n"}</span>;
        }
        return <span key={i}>{line}{"\n"}</span>;
      })}
    </>
  );
}
