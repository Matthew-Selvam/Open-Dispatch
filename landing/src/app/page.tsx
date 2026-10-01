"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ArrowRight,
  Check,
  Layers3,
  Plug,
  X as XIcon,
  Zap,
} from "lucide-react";

const GITHUB = "https://github.com/Matthew-Selvam/Open-Dispatch";
const DMG_URL =
  "https://github.com/Matthew-Selvam/Open-Dispatch/releases/latest/download/Open-Dispatch-0.4.0.dmg";
const DOCKER_DOCS = `${GITHUB}#--docker-compose-zero-python-required`;

/* Counts below are verified against the repo, not asserted:
   ADAPTERS in adapters/__init__.py, PLATFORM_IMAGE_SPECS in media/,
   backend classes in api/queue.py, pytest suite. Do not edit by hand. */
const ADAPTER_COUNT = 10;
const TEST_COUNT = 210;

/* Real brand marks in /public/logos, fetched rather than typed. */
const PLATFORMS = [
  { name: "X", slug: "x", target: "twitter" },
  { name: "Bluesky", slug: "bluesky", target: "bluesky" },
  { name: "Instagram", slug: "instagram", target: "instagram" },
  { name: "Threads", slug: "threads", target: "threads" },
  { name: "LinkedIn", slug: "linkedin", target: "linkedin" },
  { name: "Telegram", slug: "telegram", target: "telegram" },
  { name: "YouTube", slug: "youtube", target: "youtube" },
  { name: "TikTok", slug: "tiktok", target: "tiktok" },
  { name: "Discord", slug: "discord", target: "discord" },
  { name: "Facebook", slug: "facebook", target: "facebook" },
] as const;

const CAPABILITIES = [
  {
    icon: Zap,
    title: "One request, no dashboard",
    body: "Every action is a plain HTTP call. Drive it from cron, n8n, a CI job, or an agent. The browser UI is optional, not required.",
    evidence: "POST /dispatch",
  },
  {
    icon: Layers3,
    title: "Three queue backends",
    body: "JSONL on disk needs no infrastructure. Redis or Postgres when you outgrow one worker. Selected by environment variable.",
    evidence: "JSONL | Redis | Postgres",
  },
  {
    icon: Plug,
    title: "Ten adapters, one contract",
    body: "Every platform implements the same function signature. The worker owns retry, backoff, and webhooks so an adapter never has to.",
    evidence: "tuple[bool, str, str]",
  },
  {
    icon: Check,
    title: "Per-platform media specs",
    body: "Ten image specs and seven video specs are built in. POST an image, get it back at the exact dimensions the target expects.",
    evidence: "GET /media/specs",
  },
];

type InstallKey = "dmg" | "brew" | "curl" | "docker" | "pip";

const INSTALL: Record<InstallKey, {
  label: string;
  time: string;
  needs: string;
  snippet: string;
  note?: string;
}> = {
  dmg: {
    label: "macOS app",
    time: "10s",
    needs: "macOS 13+",
    snippet: "",
    note: "SwiftUI menubar app that bundles the Python server, so there is no separate Python install.",
  },
  brew: {
    label: "Homebrew",
    time: "~2 min",
    needs: "macOS",
    snippet:
`# Add the tap
brew tap matthew-selvam/open-dispatch \\
  ${GITHUB}
brew install open-dispatch

# Credentials
$EDITOR ~/.open-dispatch/.env

# Run it
open-dispatch`,
    note: "brew services wires launchd so it starts at login.",
  },
  curl: {
    label: "install.sh",
    time: "~90s",
    needs: "macOS & Linux",
    snippet:
`curl -fsSL \\
  https://raw.githubusercontent.com/Matthew-Selvam/Open-Dispatch/main/install.sh \\
  | bash

$EDITOR ~/.open-dispatch/.env
open-dispatch`,
    note: "Writes a launchd plist on macOS or a systemd user unit on Linux.",
  },
  docker: {
    label: "Docker",
    time: "~60s",
    needs: "Any platform",
    snippet:
`git clone ${GITHUB}
cd Open-Dispatch
cp .env.example .env      # add your platform credentials
docker compose up -d

# Confirm it is live
curl http://localhost:8000/healthz`,
    note: "No Python setup. Multi-arch image, with an optional Redis profile for multi-worker throughput.",
  },
  pip: {
    label: "pip",
    time: "Instant",
    needs: "Python 3.11+",
    snippet:
`pip install git+${GITHUB}.git

# Extras
pip install "open-dispatch[redis]"
pip install "open-dispatch[postgres]"

uvicorn api.app:app --reload`,
    note: "Best if you are embedding Open-Dispatch in an existing Python codebase.",
  },
};

/* Ordered shortest-first. The macOS app genuinely is the fastest path, so it
   leads rather than sitting at the end as an afterthought. */
const INSTALL_ORDER: InstallKey[] = ["dmg", "brew", "curl", "docker", "pip"];

const ENDPOINTS = [
  ["GET", "/healthz", "Liveness probe. JSON for clients, dashboard for browsers."],
  ["POST", "/dispatch", "Enqueue a ContentUnit for one or many platforms."],
  ["GET", "/queue", "List rows. Filter by queued, publishing, published, failed, dead, canceled."],
  ["GET", "/campaign/{unit_id}", "Every platform row for one dispatch."],
  ["POST", "/campaign/{unit_id}/cancel", "Cancel a campaign's queued rows."],
  ["GET", "/queue/{id}", "One row, content-negotiated as JSON or HTML."],
  ["POST", "/queue/{id}/retry", "Re-queue an errored or dead row."],
  ["DELETE", "/queue/{id}", "Delete a queue row permanently."],
  ["POST", "/ai/adapt", "Rewrite a caption per platform."],
  ["POST", "/media/transcode", "Resize an image to a platform spec."],
  ["GET", "/media/specs", "List the built-in image and video specs."],
] as const;

const FAQS = [
  {
    q: "Which install method should I use?",
    a: "On macOS, the app is the shortest path: one download, drag to Applications, done. If you want a terminal workflow, Homebrew gives you a login service via brew services. On a Linux VPS, Docker avoids the Python setup entirely.",
  },
  {
    q: "How do I self-host on a VPS?",
    a: "Docker is the cleanest option. It runs as a non-root user, needs no Python on the host, and ships an optional Redis sidecar. Read the Docker section of the README for the full walkthrough.",
  },
  {
    q: "Is it really free?",
    a: "Yes. It is MIT licensed with no cloud component, no telemetry, and no account to create. Your platform credentials stay in a .env file on your own machine.",
  },
  {
    q: "How do I reach the API?",
    a: "It listens on localhost:8000 with no auth by default, which suits trusted self-hosting. If you expose the port beyond localhost, set OPEN_DISPATCH_API_TOKEN first. That requires an Authorization header on every route except /healthz.",
  },
  {
    q: "Where do I get platform credentials?",
    a: "Each platform's developer console issues its own keys, and .env.example in the repo lists every variable Open-Dispatch reads, grouped by platform with the account-scoped naming convention. Copy it to .env and fill in only the platforms you dispatch to. The API does not complain about platforms you leave unset.",
  },
  {
    q: "Can I add another platform?",
    a: "Yes. The adapter contract is a single Python function, roughly 80 lines. Register it in adapters/__init__.py, document its format key in the README, and the worker handles retry, backoff, and webhooks for you.",
  },
];

export default function Page() {
  const [activeInstall, setActiveInstall] = useState<InstallKey>("dmg");

  return (
    <>
      <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-bg)]/90 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <Link
            href="/"
            className="font-mono text-sm font-semibold tracking-tight text-[var(--color-fg)]"
          >
            open-dispatch
          </Link>
          <nav className="flex items-center gap-5 text-sm text-[var(--color-body)]">
            <a href="#how" className="hidden transition-colors hover:text-[var(--color-fg)] sm:block">
              How it works
            </a>
            <a href="#api" className="hidden transition-colors hover:text-[var(--color-fg)] sm:block">
              API
            </a>
            <a href="#install" className="hidden transition-colors hover:text-[var(--color-fg)] sm:block">
              Install
            </a>
            <a href="#faq" className="hidden transition-colors hover:text-[var(--color-fg)] sm:block">
              FAQ
            </a>
            <a
              href={GITHUB}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--color-border)] px-3 py-1.5 font-mono text-xs text-[var(--color-fg)] transition-colors hover:border-[var(--color-primary)]"
            >
              <GitHubIcon /> GitHub
            </a>
          </nav>
        </div>
      </header>

      <main>
        {/* ── WORKBENCH HERO ──────────────────────────────────────────────
            The product is a request. So the hero is a request, with its real
            response underneath. One promise, one visual, two actions. */}
        <section className="border-b border-[var(--color-border)]">
          <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-24 md:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] md:py-28">
            <div>
              <p className="font-mono text-xs text-[var(--color-muted)]">
                MIT licensed · {TEST_COUNT} tests
              </p>

              <h1 className="mt-4 text-4xl font-bold leading-[1.02] tracking-[-0.03em] sm:text-5xl">
                One HTTP call.
                <br />
                <span className="text-[var(--color-primary)]">
                  {ADAPTER_COUNT} platforms.
                </span>
                <br />
                Your infrastructure.
              </h1>

              <p className="mt-6 max-w-md text-[var(--color-body)] leading-relaxed">
                Open-Dispatch is a queue and a set of adapters that posts to
                social platforms. You run it. Your OAuth tokens never leave
                the machine, and there is no per-account meter.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <a
                  href="#install"
                  className="inline-flex items-center gap-2 rounded-md bg-[var(--color-primary)] px-5 py-2.5 text-sm font-semibold text-[var(--color-on-primary)] transition-opacity hover:opacity-90"
                >
                  Install it <ArrowRight size={16} />
                </a>
                <a
                  href={GITHUB}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-md border border-[var(--color-border)] px-5 py-2.5 text-sm font-semibold text-[var(--color-fg)] transition-colors hover:border-[var(--color-primary)]"
                >
                  <GitHubIcon /> Source
                </a>
              </div>

              {/* Logo wall: the real marks, one per registered adapter. */}
              <div className="mt-10">
                <p className="font-mono text-xs text-[var(--color-muted)]">
                  {ADAPTER_COUNT} registered adapters
                </p>
                <ul className="mt-3 grid max-w-xs grid-cols-5 gap-2">
                  {PLATFORMS.map((p) => (
                    <li key={p.target}>
                      <span className="logo-tile" title={p.name}>
                        {/* Plain img, not next/image: these are local static SVG
                            brand marks with fixed dimensions, and next/image's
                            optimizer serves them inconsistently (it also refuses
                            SVG without dangerouslyAllowSVG). */}
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={`/logos/${p.slug}.svg`}
                          alt={p.name}
                          width={20}
                          height={20}
                        />
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* The one authored moment: a real request and its real response. */}
            <div className="panel-enter">
              <RequestPanel />
            </div>
          </div>
        </section>

        {/* ── THE PROBLEM ───────────────────────────────────────────────── */}
        <section className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <h2 className="text-2xl font-bold tracking-tight">
              What hosted schedulers take from you
            </h2>
            <div className="mt-8 overflow-hidden rounded-xl border border-[var(--color-border)]">
              <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] border-b border-[var(--color-border)] bg-[var(--color-surface)] text-xs font-semibold uppercase tracking-wider">
                <div className="px-5 py-3 text-[var(--color-muted)]">Hosted tools</div>
                <div className="border-l border-[var(--color-border)] px-5 py-3 text-[var(--color-primary)]">
                  Open-Dispatch
                </div>
              </div>
              {[
                ["Per-account fees that compound monthly", "Self-host free, no ceilings"],
                ["OAuth tokens held on someone else's servers", "Credentials stay in your .env"],
                ["Failures buried in a vendor dashboard", "Every error in your queue, retryable"],
                ["Inbox, analytics, and scheduling behind paid tiers", "All ten platforms in one build"],
                ["Your audience's data lingers after you cancel", "Your queue, your disk, your call"],
                ["Vendor lock-in by design", "MIT licensed, fork it whenever"],
              ].map(([them, us]) => (
                <div
                  key={them}
                  className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] border-b border-[var(--color-border)] text-sm last:border-b-0"
                >
                  <div className="flex items-start gap-2.5 px-5 py-4 text-[var(--color-body)]">
                    <XIcon size={15} className="mt-0.5 shrink-0 text-[var(--color-muted)]" />
                    <span>{them}</span>
                  </div>
                  <div className="flex items-start gap-2.5 border-l border-[var(--color-border)] px-5 py-4 text-[var(--color-fg)]">
                    <Check size={15} className="mt-0.5 shrink-0 text-[var(--color-primary)]" />
                    <span>{us}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── HOW IT WORKS ──────────────────────────────────────────────── */}
        <section id="how" className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <h2 className="text-2xl font-bold tracking-tight">
              The whole path, end to end
            </h2>
            <p className="mt-3 max-w-2xl text-[var(--color-body)]">
              A request enters the queue, a worker picks it up, one adapter
              publishes it, and a webhook reports the result. There is no
              hidden step between those four.
            </p>
            <div className="mt-8 grid gap-8 lg:grid-cols-2">
              <PipelineDiagram />
              <div>
                <h3 className="font-semibold">
                  Adding a platform is one function
                </h3>
                <p className="mt-2 text-sm text-[var(--color-body)]">
                  The worker owns retry, backoff, and webhook delivery, so an
                  adapter only has to publish and report a result.
                </p>
                <div className="mt-4">
                  <CodeCard filename="adapters/myplatform.py">
{`def publish(
  unit: ContentUnit,
  account: str | None
) -> tuple[bool, str, str]:
  """(ok, post_id, error)"""`}
                  </CodeCard>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── CAPABILITIES ───────────────────────────────────────────────── */}
        <section className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <h2 className="text-2xl font-bold tracking-tight">
              What it does, with the artifact that proves it
            </h2>
            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              {CAPABILITIES.map((c) => {
                const Icon = c.icon;
                return (
                  <article
                    key={c.title}
                    className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6"
                  >
                    <div className="flex items-start gap-4">
                      <Icon size={20} className="mt-0.5 shrink-0 text-[var(--color-primary)]" />
                      <div>
                        <h3 className="font-semibold">{c.title}</h3>
                        <p className="mt-2 text-sm leading-relaxed text-[var(--color-body)]">
                          {c.body}
                        </p>
                        <p className="mt-3 font-mono text-xs text-[var(--color-muted)]">
                          {c.evidence}
                        </p>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        {/* ── API LEDGER ────────────────────────────────────────────────── */}
        <section id="api" className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h2 className="text-2xl font-bold tracking-tight">
                  Every endpoint, no client library required
                </h2>
                <p className="mt-3 max-w-2xl text-[var(--color-body)]">
                  Plain HTTP with JSON in and JSON out. Full request and
                  response shapes are on the API reference page.
                </p>
              </div>
              <Link
                href="/api-reference"
                className="inline-flex items-center gap-1.5 font-mono text-sm text-[var(--color-primary)] hover:underline"
              >
                API reference <ArrowRight size={14} />
              </Link>
            </div>

            <div className="mt-8 overflow-x-auto rounded-xl border border-[var(--color-border)]">
              <table className="w-full text-left font-mono text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)] bg-[var(--color-surface)]">
                    {["Method", "Path", "Purpose"].map((h) => (
                      <th
                        key={h}
                        className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-muted)]"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ENDPOINTS.map(([method, path, purpose]) => (
                    <tr
                      key={path}
                      className="border-b border-[var(--color-border)] last:border-b-0"
                    >
                      <td className="whitespace-nowrap px-5 py-3 text-xs">
                        <span
                          className={
                            method === "GET"
                              ? "text-[var(--color-primary)]"
                              : method === "DELETE"
                                ? "text-[var(--color-accent)]"
                                : "text-[var(--color-fg)]"
                          }
                        >
                          {method}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-xs text-[var(--color-fg)]">
                        {path}
                      </td>
                      <td className="px-5 py-3 text-xs text-[var(--color-body)]">
                        {purpose}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* ── INSTALL ───────────────────────────────────────────────────── */}
        <section id="install" className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <h2 className="text-2xl font-bold tracking-tight">
              Five ways in, shortest first
            </h2>

            <div
              role="tablist"
              aria-label="Install method"
              className="mt-8 flex flex-wrap gap-2"
            >
              {INSTALL_ORDER.map((key) => {
                const m = INSTALL[key];
                const active = activeInstall === key;
                return (
                  <button
                    key={key}
                    role="tab"
                    aria-selected={active}
                    onClick={() => setActiveInstall(key)}
                    className={`flex flex-col items-start rounded-lg border px-4 py-2.5 text-left transition-colors ${
                      active
                        ? "border-[var(--color-primary)] bg-[var(--color-secondary)] text-[var(--color-fg)]"
                        : "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-body)] hover:border-[var(--color-muted)]"
                    }`}
                  >
                    <span className="text-sm font-medium">{m.label}</span>
                    <span className="mt-0.5 font-mono text-[11px] text-[var(--color-muted)]">
                      {m.time} · {m.needs}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="panel mt-4 overflow-hidden">
              <div className="terminal-bar">
                <span className="terminal-dot" />
                <span className="terminal-dot" />
                <span className="terminal-dot" />
                <span className="ml-2 font-mono text-xs text-[var(--color-muted)]">
                  {INSTALL[activeInstall].label}
                </span>
              </div>

              {activeInstall === "dmg" ? (
                <DownloadPane />
              ) : (
                <pre className="overflow-x-auto p-5 font-mono text-xs leading-relaxed whitespace-pre text-[var(--color-body)]">
                  {INSTALL[activeInstall].snippet}
                </pre>
              )}

              {INSTALL[activeInstall].note && (
                <p className="border-t border-[var(--color-border)] px-5 py-3 text-xs text-[var(--color-muted)]">
                  {INSTALL[activeInstall].note}
                </p>
              )}
            </div>
          </div>
        </section>

        {/* ── FAQ ───────────────────────────────────────────────────────── */}
        <section id="faq" className="border-b border-[var(--color-border)]">
          <div className="mx-auto max-w-4xl px-6 py-20">
            <h2 className="text-2xl font-bold tracking-tight">
              Questions worth answering before you install
            </h2>
            <dl className="mt-8 divide-y divide-[var(--color-border)]">
              {FAQS.map((f) => (
                <div
                  key={f.q}
                  className="grid gap-3 py-7 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] sm:gap-10"
                >
                  <dt className="text-sm font-semibold leading-snug">{f.q}</dt>
                  <dd className="text-sm leading-relaxed text-[var(--color-body)]">
                    {f.a}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        {/* ── CLOSE ─────────────────────────────────────────────────────── */}
        <section>
          <div className="mx-auto max-w-6xl px-6 py-24">
            <div className="flex flex-wrap items-center justify-between gap-8">
              <div>
                <h2 className="text-2xl font-bold tracking-tight">
                  Run it yourself
                </h2>
                <p className="mt-2 font-mono text-sm text-[var(--color-body)]">
                  {TEST_COUNT} tests · {ADAPTER_COUNT} adapters · 3 queue
                  backends · MIT
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <a
                  href="#install"
                  className="inline-flex items-center gap-2 rounded-md bg-[var(--color-primary)] px-5 py-2.5 text-sm font-semibold text-[var(--color-on-primary)] transition-opacity hover:opacity-90"
                >
                  Install <ArrowRight size={16} />
                </a>
                <a
                  href={GITHUB}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-md border border-[var(--color-border)] px-5 py-2.5 text-sm font-semibold text-[var(--color-fg)] transition-colors hover:border-[var(--color-primary)]"
                >
                  <GitHubIcon /> GitHub
                </a>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-[var(--color-border)]">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 py-8 font-mono text-xs text-[var(--color-muted)] sm:flex-row">
          <span>open-dispatch · MIT</span>
          <div className="flex flex-wrap justify-center gap-5">
            {[
              ["Releases", `${GITHUB}/releases`],
              ["Contributing", `${GITHUB}/blob/main/CONTRIBUTING.md`],
              ["Security", `${GITHUB}/blob/main/SECURITY.md`],
              ["Install docs", `${GITHUB}/blob/main/INSTALL_METHODS.md`],
            ].map(([label, href]) => (
              <a
                key={label}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="transition-colors hover:text-[var(--color-fg)]"
              >
                {label}
              </a>
            ))}
          </div>
        </div>
      </footer>
    </>
  );
}

/* ── Pieces ────────────────────────────────────────────────────────────── */

/**
 * The hero visual: a real request and the real response shape it returns.
 * Both are copied from the repo's own test fixtures and endpoint docs, so the
 * first thing a visitor sees is literally what the tool does.
 */
function RequestPanel() {
  return (
    <div className="panel overflow-hidden">
      <div className="terminal-bar">
        <span className="terminal-dot" />
        <span className="terminal-dot" />
        <span className="terminal-dot" />
        <span className="ml-2 font-mono text-xs text-[var(--color-muted)]">
          dispatch.sh
        </span>
      </div>

      <pre className="overflow-x-auto p-5 font-mono text-xs leading-relaxed">
        <code>
          <span className="tok-pun">$ </span>
          <span className="tok-key">curl</span>
          <span className="text-[var(--color-body)]"> -X POST </span>
          <span className="text-[var(--color-body)]">
            http://localhost:8000/dispatch
          </span>
          {"\n"}
          <span className="tok-pun">  </span>
          <span className="tok-key">-H</span>
          <span className="tok-str">
            {" "}
            &quot;Content-Type: application/json&quot;
          </span>
          {"\n"}
          <span className="tok-pun">  </span>
          <span className="tok-key">-d</span>
          <span className="text-[var(--color-body)]">{' '}</span>
          <span className="tok-str">
            &apos;{`{"targets":["bluesky","telegram"],`}
          </span>
          {"\n"}
          <span className="tok-pun">   </span>
          <span className="tok-str">
            {" "}
            &quot;formats&quot;:{`{"bluesky_post":{"text":"shipped v0.4"},`}
          </span>
          {"\n"}
          <span className="tok-pun">   </span>
          <span className="tok-str">
            {" "}
            &quot;telegram_message&quot;:{`{"text":"shipped v0.4"}}}}`}
          </span>
          {"\n\n"}
          <span className="tok-cmt"># 202 Accepted</span>
          {"\n"}
          <span className="tok-pun">{`{`}</span>
          <span className="tok-key">&quot;id&quot;</span>
          <span className="tok-pun">:</span>
          <span className="tok-str">&quot;7f3a91c4&quot;</span>
          <span className="tok-pun">,</span>
          {"\n"}
          <span className="tok-pun"> </span>
          <span className="tok-key">&quot;status&quot;</span>
          <span className="tok-pun">:</span>
          <span className="tok-str">&quot;queued&quot;</span>
          <span className="tok-pun">,</span>
          {"\n"}
          <span className="tok-pun"> </span>
          <span className="tok-key">&quot;targets&quot;</span>
          <span className="tok-pun">:[</span>
          <span className="tok-str">&quot;bluesky&quot;</span>
          <span className="tok-pun">,</span>
          <span className="tok-str">&quot;telegram&quot;</span>
          <span className="tok-pun">]</span>
          <span className="tok-pun">{`}`}</span>
        </code>
      </pre>
    </div>
  );
}

/** The real dispatch path, as the repo actually wires it. */
function PipelineDiagram() {
  return (
    <div className="panel overflow-hidden">
      <div className="terminal-bar">
        <span className="terminal-dot" />
        <span className="terminal-dot" />
        <span className="terminal-dot" />
        <span className="ml-2 font-mono text-xs text-[var(--color-muted)]">
          request path
        </span>
      </div>
      <pre className="overflow-x-auto p-5 font-mono text-xs leading-relaxed text-[var(--color-body)]">
{`POST /dispatch
      |
      v
Queue   JSONL | Redis | Postgres
      |
      v
scheduler/worker.py
      |
      +--> adapters/<platform>.py   x {ADAPTER_COUNT}
      |
      v  on publish or fail
  webhook_url`}
      </pre>
    </div>
  );
}

function DownloadPane() {
  return (
    <div className="flex flex-col items-center gap-5 px-6 py-14 text-center">
      <div>
        <p className="text-lg font-semibold">Open-Dispatch 0.4.0</p>
        <p className="mt-1.5 font-mono text-xs text-[var(--color-muted)]">
          macOS 13 Ventura or later · Apple Silicon and Intel
        </p>
      </div>
      <a
        href={DMG_URL}
        className="inline-flex items-center gap-2 rounded-md bg-[var(--color-primary)] px-6 py-2.5 text-sm font-semibold text-[var(--color-on-primary)] transition-opacity hover:opacity-90"
      >
        Download .dmg
      </a>
      <p className="font-mono text-xs text-[var(--color-muted)]">
        <a
          href={`${GITHUB}/releases`}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-[var(--color-fg)] hover:underline"
        >
          all releases
        </a>
        {"  ·  "}
        build from source:{" "}
        <span className="text-[var(--color-body)]">bash scripts/make-dmg.sh</span>
      </p>
    </div>
  );
}

function CodeCard({
  filename,
  children,
}: {
  filename: string;
  children: string;
}) {
  return (
    <div className="panel overflow-hidden">
      <div className="terminal-bar">
        <span className="terminal-dot" />
        <span className="terminal-dot" />
        <span className="terminal-dot" />
        <span className="ml-2 font-mono text-xs text-[var(--color-muted)]">
          {filename}
        </span>
      </div>
      <pre className="overflow-x-auto p-5 font-mono text-xs leading-relaxed text-[var(--color-body)]">
        <code>{children}</code>
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
