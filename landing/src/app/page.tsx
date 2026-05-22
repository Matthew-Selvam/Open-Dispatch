"use client";

import Link from "next/link";
import { useState } from "react";

const GITHUB = "https://github.com/Matthew-Selvam/Open-Dispatch";

const PLATFORMS = [
  { name: "Twitter / X",    icon: "𝕏" },
  { name: "Bluesky",        icon: "🦋" },
  { name: "Instagram",      icon: "📷" },
  { name: "Threads",        icon: "🧵" },
  { name: "LinkedIn",       icon: "💼" },
  { name: "Telegram",       icon: "✈️" },
  { name: "YouTube Shorts", icon: "▶️" },
];

const FEATURES = [
  { icon: "⚡", title: "API-first",         body: "Every action reachable via one HTTP call. Automate from cron, n8n, AI agents, or your own app — no dashboard required." },
  { icon: "🖥️", title: "Web UI included",   body: "HTMX-powered dark dashboard: compose, retry, watch the queue live. Same port as the API — zero JS build step." },
  { icon: "🏗️", title: "3 queue backends",  body: "JSONL on disk (zero infra), Redis (multi-worker), or Postgres (ACID + SKIP LOCKED). Swap with a single env var." },
  { icon: "🤖", title: "AI caption adapt",  body: "One source text → per-platform rewrites. Ollama-first, OpenRouter fallback, heuristic safety net. Never 500s." },
  { icon: "🖼️", title: "Media transcoding", body: "10 platform image specs built in — square, reels, 16:9, portrait. REST endpoint + Python API." },
  { icon: "🔌", title: "n8n node",          body: "Native integration: Dispatch, Adapt, Get Row, Retry, List Queue — all 5 ops, zero JSON wiring." },
];

// ── install methods ────────────────────────────────────────────────────────────
type InstallKey = "brew" | "curl" | "docker" | "pip" | "dmg";

const INSTALL: Record<InstallKey, { label: string; icon: string; snippet: string; note?: string }> = {
  brew: {
    label: "Homebrew",
    icon: "🍺",
    snippet:
`# Add the tap (formula lives in the main repo)
brew tap matthew-selvam/open-dispatch \\
  https://github.com/Matthew-Selvam/Open-Dispatch
brew install open-dispatch

# Set up credentials
$EDITOR ~/.open-dispatch/.env

# Start (foreground)
open-dispatch

# Or run as a background service (auto-starts on login)
brew services start open-dispatch`,
    note: "Installs dispatch + open-dispatch + open-dispatch-worker. brew services wires launchd so it starts at login.",
  },
  curl: {
    label: "install.sh",
    icon: "⬇️",
    snippet:
`curl -fsSL \\
  https://raw.githubusercontent.com/Matthew-Selvam/Open-Dispatch/main/install.sh \\
  | bash

# Set up credentials
$EDITOR ~/.open-dispatch/.env

# Start server
open-dispatch

# macOS: start at login via launchd
launchctl load ~/Library/LaunchAgents/dev.open-dispatch.plist

# Linux: start via systemd user session
systemctl --user enable --now open-dispatch`,
    note: "Works on macOS (14+) and Linux. Writes a launchd plist or systemd user unit automatically.",
  },
  docker: {
    label: "Docker",
    icon: "🐳",
    snippet:
`git clone https://github.com/Matthew-Selvam/Open-Dispatch
cd Open-Dispatch
cp .env.example .env   # fill in your platform creds
docker compose up -d

# Check it's live
curl http://localhost:8000/healthz   # → {"status":"ok"}

# Open the dashboard
open http://localhost:8000

# Optional: add Redis for multi-worker throughput
docker compose --profile redis up -d`,
    note: "Zero Python setup required. Multi-arch image (amd64 + arm64). Bundled Redis profile for scaling.",
  },
  pip: {
    label: "pip",
    icon: "🐍",
    snippet:
`# Install from GitHub (PyPI publish pending)
pip install git+https://github.com/Matthew-Selvam/Open-Dispatch.git

# Optional extras
pip install "open-dispatch[redis]"     # Redis queue backend
pip install "open-dispatch[postgres]"  # Postgres queue backend

# Start the server
uvicorn api.app:app --reload

# Worker (separate terminal)
python -m scheduler.worker

# CLI
dispatch send --platforms bluesky --text "hello world"`,
    note: "Best for Python developers who want to integrate Open-Dispatch into existing code.",
  },
  dmg: {
    label: "macOS App",
    icon: "🍎",
    snippet:
`# 1. Download Open-Dispatch-0.4.0.dmg from GitHub Releases:
#    https://github.com/Matthew-Selvam/Open-Dispatch/releases

# 2. Drag Open-Dispatch.app to /Applications

# 3. Launch — a status icon appears in your menu bar
#    Click → Edit .env → add your platform credentials
#    Click → Start Server
#    Click → Open Dashboard → http://localhost:8000

# Build it yourself:
bash scripts/make-dmg.sh
# → dist/Open-Dispatch-0.4.0.dmg`,
    note: "SwiftUI menubar app. Bundles the Python server — no separate Python install needed. macOS 13+.",
  },
};

const INSTALL_ORDER: InstallKey[] = ["brew", "curl", "docker", "pip", "dmg"];

export default function Page() {
  const [activeInstall, setActiveInstall] = useState<InstallKey>("brew");

  return (
    <>
      {/* ── NAV ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-bg)]/90 backdrop-blur">
        <div className="mx-auto max-w-6xl px-6 h-14 flex items-center justify-between">
          <span className="font-mono text-sm font-semibold text-[var(--color-fg)] tracking-tight">
            open<span className="text-[var(--color-accent)]">-dispatch</span>
          </span>
          <nav className="flex items-center gap-5 text-sm text-[var(--color-body)]">
            <a href="#install"   className="hover:text-[var(--color-fg)] transition-colors hidden sm:block">Install</a>
            <a href="#features"  className="hover:text-[var(--color-fg)] transition-colors hidden sm:block">Features</a>
            <a href="#api"       className="hover:text-[var(--color-fg)] transition-colors hidden sm:block">API</a>
            <Link
              href={GITHUB} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium text-[var(--color-fg)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors"
            >
              <GitHubIcon /> GitHub
            </Link>
          </nav>
        </div>
      </header>

      <main>
        {/* ── HERO ──────────────────────────────────────────────────────── */}
        <section className="relative overflow-hidden border-b border-[var(--color-border)]">
          <GridBg />
          <div className="relative mx-auto max-w-6xl px-6 py-20 md:py-32 grid md:grid-cols-2 gap-14 items-center">
            <div>
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1 text-xs font-mono text-[var(--color-body)]">
                <span className="size-1.5 rounded-full bg-green-400 animate-pulse" />
                v0.4.0 · MIT · 129 tests
              </div>
              <h1 className="font-sans text-5xl sm:text-6xl font-bold leading-[1.1] tracking-tight">
                One API to{" "}
                <span className="text-[var(--color-accent)]">dispatch</span>
                <br />your content
                <br />anywhere.
              </h1>
              <p className="mt-6 text-[var(--color-body)] leading-relaxed max-w-lg">
                Open-source infrastructure for content distribution.
                Like Stripe for payments — except for posting.
                One HTTP call, seven platforms, zero vendor lock-in.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                {PLATFORMS.map(p => (
                  <span key={p.name} className="flex items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1 text-xs text-[var(--color-body)]">
                    {p.icon} {p.name}
                  </span>
                ))}
              </div>
              <div className="mt-8 flex flex-wrap gap-3">
                <a href="#install"
                  className="inline-flex items-center gap-2 rounded bg-[var(--color-accent)] px-5 py-2.5 text-sm font-semibold text-white hover:opacity-90 transition-opacity">
                  Install now ↓
                </a>
                <Link href={GITHUB} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded border border-[var(--color-border)] px-5 py-2.5 text-sm font-semibold text-[var(--color-fg)] hover:border-[var(--color-accent)] transition-colors">
                  <GitHubIcon /> Star on GitHub
                </Link>
              </div>
            </div>

            {/* dispatch snippet */}
            <CodeCard filename="dispatch.sh">
              <span className="text-[#79d1ff]">curl</span>
              {` -X POST http://localhost:8000/dispatch \\
  -H "Content-Type: application/json" \\
  -d '`}
              <span className="text-[#e8c97d]">{`{`}</span>
              {`\n  `}
              <span className="text-[#e8c97d]">"targets"</span>
              {`: [`}
              <span className="text-[#9de29a]">"twitter"</span>
              {`, `}
              <span className="text-[#9de29a]">"bluesky"</span>
              {`, `}
              <span className="text-[#9de29a]">"telegram"</span>
              {`],\n  `}
              <span className="text-[#e8c97d]">"formats"</span>
              {`: {\n    `}
              <span className="text-[#e8c97d]">"twitter_thread"</span>
              {`: {`}
              <span className="text-[#e8c97d]">"tweets"</span>
              {`:[`}
              <span className="text-[#9de29a]">"shipped v0.4"</span>
              {`]},\n    `}
              <span className="text-[#e8c97d]">"bluesky_post"</span>
              {`:   {`}
              <span className="text-[#e8c97d]">"text"</span>
              {`:`}
              <span className="text-[#9de29a]">"shipped v0.4"</span>
              {`},\n    `}
              <span className="text-[#e8c97d]">"telegram_message"</span>
              {`:{`}
              <span className="text-[#e8c97d]">"text"</span>
              {`:`}
              <span className="text-[#9de29a]">"shipped v0.4"</span>
              {`}\n  }\n`}
              <span className="text-[#e8c97d]">{`}'`}</span>
            </CodeCard>
          </div>
        </section>

        {/* ── INSTALL ───────────────────────────────────────────────────── */}
        <section id="install" className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <h2 className="text-2xl font-bold tracking-tight mb-2">Get started in 60 seconds.</h2>
            <p className="text-[var(--color-body)] mb-8 max-w-2xl">
              Five ways to install — pick what fits your stack.
            </p>

            {/* tab strip */}
            <div className="flex flex-wrap gap-2 mb-6">
              {INSTALL_ORDER.map(key => {
                const m = INSTALL[key];
                const active = activeInstall === key;
                return (
                  <button
                    key={key}
                    onClick={() => setActiveInstall(key)}
                    className={`flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-all ${
                      active
                        ? "border-[var(--color-accent)] bg-[var(--color-accent-dim)] text-[var(--color-fg)]"
                        : "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-body)] hover:border-[var(--color-fg)]"
                    }`}
                  >
                    <span>{m.icon}</span> {m.label}
                  </button>
                );
              })}
            </div>

            {/* snippet pane */}
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--color-border)]">
                <span className="size-3 rounded-full bg-red-500/60" />
                <span className="size-3 rounded-full bg-yellow-500/60" />
                <span className="size-3 rounded-full bg-green-500/60" />
                <span className="ml-3 font-mono text-xs text-[var(--color-muted)]">
                  {INSTALL[activeInstall].icon} {INSTALL[activeInstall].label}
                </span>
              </div>
              <pre className="overflow-x-auto p-5 text-xs font-mono leading-relaxed text-[var(--color-body)] whitespace-pre">
                {INSTALL[activeInstall].snippet}
              </pre>
              {INSTALL[activeInstall].note && (
                <div className="border-t border-[var(--color-border)] px-5 py-3 text-xs text-[var(--color-muted)]">
                  ℹ️ {INSTALL[activeInstall].note}
                </div>
              )}
            </div>

            {/* comparison table */}
            <div className="mt-8 overflow-x-auto rounded-xl border border-[var(--color-border)]">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="bg-[var(--color-surface)] border-b border-[var(--color-border)]">
                    {["Method","Setup","Needs","Best for"].map(h => (
                      <th key={h} className="px-4 py-2.5 text-left text-[var(--color-muted)] font-semibold uppercase tracking-wider text-[10px]">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {[
                    ["🍺 Homebrew",  "~2 min",  "macOS + Homebrew",    "macOS devs, brew services auto-start"],
                    ["⬇️ install.sh", "~90s",    "bash + Python 3.11+", "Linux servers, scripts, CI"],
                    ["🐳 Docker",    "~60s",     "Docker",              "Self-hosters, Linux VMs, zero Python"],
                    ["🐍 pip",       "instant",  "Python 3.11+",        "Python devs, embedding in apps"],
                    ["🍎 macOS App", "10s",      "macOS 13+",           "Non-technical users, menubar control"],
                  ].map(([method, setup, needs, use]) => (
                    <tr key={method} className="hover:bg-[var(--color-surface)] transition-colors">
                      <td className="px-4 py-2.5 text-[var(--color-fg)]">{method}</td>
                      <td className="px-4 py-2.5 text-[var(--color-body)]">{setup}</td>
                      <td className="px-4 py-2.5 text-[var(--color-body)]">{needs}</td>
                      <td className="px-4 py-2.5 text-[var(--color-muted)]">{use}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* ── FEATURES ──────────────────────────────────────────────────── */}
        <section id="features" className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <h2 className="text-2xl font-bold tracking-tight mb-10 text-center">
              Everything you need. Nothing you don&apos;t.
            </h2>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {FEATURES.map(f => (
                <div key={f.title} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
                  <div className="text-2xl mb-3">{f.icon}</div>
                  <h3 className="font-semibold text-[var(--color-fg)] mb-2">{f.title}</h3>
                  <p className="text-sm text-[var(--color-body)] leading-relaxed">{f.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── API REFERENCE ─────────────────────────────────────────────── */}
        <section id="api" className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <h2 className="text-2xl font-bold tracking-tight mb-3">Simple, stable API.</h2>
            <p className="text-[var(--color-body)] mb-8 max-w-2xl text-sm">
              Every endpoint is reachable over plain HTTP.{" "}
              <code className="bg-[var(--color-surface)] border border-[var(--color-border)] px-1.5 py-0.5 rounded text-xs">/queue/&#123;id&#125;</code>
              {" "}content-negotiates — browsers get the HTML detail page, API clients get JSON.
            </p>
            <div className="overflow-x-auto rounded-xl border border-[var(--color-border)]">
              <table className="w-full text-sm font-mono">
                <thead>
                  <tr className="border-b border-[var(--color-border)] bg-[var(--color-surface)]">
                    {["Method","Path","Purpose"].map(h => (
                      <th key={h} className="px-5 py-3 text-left text-xs font-semibold text-[var(--color-muted)] uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {[
                    ["GET",  "/healthz",           "Liveness probe"],
                    ["POST", "/dispatch",          "Enqueue a ContentUnit for one or many platforms"],
                    ["GET",  "/queue?status=…",    "List rows (queued / publishing / published / failed / dead)"],
                    ["GET",  "/queue/{id}",        "One row — JSON or HTML (content-negotiated)"],
                    ["POST", "/queue/{id}/retry",  "Re-queue a failed or dead row"],
                    ["POST", "/ai/adapt",          "Rewrite a caption for each target platform"],
                    ["POST", "/media/transcode",   "Resize image to a platform spec"],
                    ["GET",  "/media/specs",       "List all 10 platform image specs"],
                  ].map(([method, path, purpose]) => (
                    <tr key={path} className="hover:bg-[var(--color-surface)]/50 transition-colors">
                      <td className="px-5 py-3 text-xs">
                        <span className={`font-semibold ${method === "GET" ? "text-[var(--color-accent)]" : "text-green-400"}`}>{method}</span>
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

        {/* ── ARCH + ADAPTER CONTRACT ───────────────────────────────────── */}
        <section className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20 grid md:grid-cols-2 gap-14 items-start">
            <div>
              <h2 className="text-2xl font-bold tracking-tight mb-4">Architecture at a glance.</h2>
              <CodeCard filename="flow.txt">
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
              </CodeCard>
            </div>
            <div>
              <h2 className="text-2xl font-bold tracking-tight mb-4">Add a platform in 80 LOC.</h2>
              <p className="text-[var(--color-body)] text-sm mb-4 leading-relaxed">
                One function, one file. The worker handles retry, backoff, and webhooks for you.
              </p>
              <CodeCard filename="adapters/myplatform.py">
                <span className="text-[#79d1ff]">def</span>
                <span className="text-[var(--color-fg)]"> publish</span>
                {"(\n  "}
                <span className="text-[var(--color-fg)]">unit</span>
                {": "}
                <span className="text-[#79d1ff]">ContentUnit</span>
                {",\n  "}
                <span className="text-[var(--color-fg)]">account</span>
                {": "}
                <span className="text-[#79d1ff]">str | None</span>
                {")\n  -> "}
                <span className="text-[#79d1ff]">tuple[bool, str, str]</span>
                {":\n  "}
                <span className="text-[#7a8fa6]">"""Returns (ok, post_id, error)."""</span>
                {"\n  ..."}
              </CodeCard>
              <ul className="mt-5 space-y-2 text-sm text-[var(--color-body)]">
                {[
                  "Write adapters/myplatform.py",
                  "Add it to ADAPTERS in adapters/__init__.py",
                  "Document the format key in README",
                ].map((s, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-[var(--color-accent)] font-mono shrink-0">{i + 1}.</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* ── N8N ───────────────────────────────────────────────────────── */}
        <section className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20 text-center">
            <div className="text-4xl mb-3">🔌</div>
            <h2 className="text-2xl font-bold tracking-tight mb-3">Native n8n integration.</h2>
            <p className="text-[var(--color-body)] max-w-md mx-auto mb-6 text-sm">
              Community node ships in the repo. Build it once, use all five operations from the visual editor — no JSON wiring.
            </p>
            <div className="inline-flex flex-wrap justify-center gap-2 mb-6">
              {["Dispatch","Adapt Caption","Get Row","Retry Row","List Queue"].map(op => (
                <span key={op} className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-1.5 text-sm text-[var(--color-body)]">{op}</span>
              ))}
            </div>
            <div className="font-mono text-xs text-[var(--color-muted)] bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-5 py-3 inline-block">
              cd n8n-node &amp;&amp; npm install &amp;&amp; npm run build
            </div>
          </div>
        </section>

        {/* ── FINAL CTA ─────────────────────────────────────────────────── */}
        <section>
          <div className="mx-auto max-w-6xl px-6 py-24 text-center">
            <h2 className="text-3xl font-bold tracking-tight mb-4">Ready to dispatch?</h2>
            <p className="text-[var(--color-body)] max-w-md mx-auto mb-8 text-sm">
              MIT licensed. Self-host forever free. Your platform credentials never leave your .env.
            </p>
            <div className="flex flex-wrap justify-center gap-4">
              <a href="#install"
                className="inline-flex items-center gap-2 rounded bg-[var(--color-accent)] px-6 py-3 text-sm font-semibold text-white hover:opacity-90 transition-opacity">
                Get started ↓
              </a>
              <Link href={GITHUB} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded border border-[var(--color-border)] px-6 py-3 text-sm font-semibold text-[var(--color-fg)] hover:border-[var(--color-accent)] transition-colors">
                <GitHubIcon /> View on GitHub
              </Link>
            </div>
            <p className="mt-8 text-xs text-[var(--color-muted)]">
              129 tests · 7 platforms · 3 queue backends · 5 install methods
            </p>
          </div>
        </section>
      </main>

      {/* ── FOOTER ────────────────────────────────────────────────────────── */}
      <footer className="border-t border-[var(--color-border)] py-8">
        <div className="mx-auto max-w-6xl px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[var(--color-muted)]">
          <span className="font-mono">open-dispatch — MIT License</span>
          <div className="flex gap-5">
            {[
              ["GitHub",       GITHUB],
              ["Releases",     GITHUB + "/releases"],
              ["Contributing", GITHUB + "/blob/main/CONTRIBUTING.md"],
              ["Security",     GITHUB + "/blob/main/SECURITY.md"],
              ["Install docs", GITHUB + "/blob/main/INSTALL_METHODS.md"],
            ].map(([label, href]) => (
              <Link key={label} href={href} target="_blank" rel="noopener noreferrer"
                className="hover:text-[var(--color-fg)] transition-colors">
                {label}
              </Link>
            ))}
          </div>
        </div>
      </footer>
    </>
  );
}

/* ── helpers ──────────────────────────────────────────────────────────────── */
function GridBg() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 opacity-[0.04]"
      style={{
        backgroundImage: "linear-gradient(var(--color-fg) 1px,transparent 1px),linear-gradient(90deg,var(--color-fg) 1px,transparent 1px)",
        backgroundSize: "40px 40px",
      }} />
  );
}

function CodeCard({ filename, children }: { filename: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden shadow-xl shadow-black/30">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--color-border)]">
        <span className="size-3 rounded-full bg-red-500/60" />
        <span className="size-3 rounded-full bg-yellow-500/60" />
        <span className="size-3 rounded-full bg-green-500/60" />
        <span className="ml-2 font-mono text-xs text-[var(--color-muted)]">{filename}</span>
      </div>
      <pre className="overflow-x-auto p-5 text-xs font-mono leading-relaxed text-[var(--color-body)] whitespace-pre">
        {children}
      </pre>
    </div>
  );
}

function GitHubIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" aria-hidden>
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}
