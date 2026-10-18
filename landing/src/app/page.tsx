"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, Check, X as XIcon } from "lucide-react";

const GITHUB = "https://github.com/Matthew-Selvam/Open-Dispatch";
const DMG_URL =
  "https://github.com/Matthew-Selvam/Open-Dispatch/releases/latest/download/Open-Dispatch-0.4.0.dmg";

/* Counts verified against the repo: ADAPTERS in adapters/__init__.py, pytest suite. */
const ADAPTER_COUNT = 10;
const TEST_COUNT = 318;

/* Real brand mark path data from /public/logos, inlined so the hero fan
   renders without extra requests. Source: landing/public/logos/<slug>.svg */
const PLATFORMS = [
  "x", "bluesky", "instagram", "threads", "linkedin",
  "telegram", "youtube", "tiktok", "discord", "facebook",
] as const;

const PLATFORM_NAMES: Record<(typeof PLATFORMS)[number], string> = {
  x: "X", bluesky: "Bluesky", instagram: "Instagram", threads: "Threads",
  linkedin: "LinkedIn", telegram: "Telegram", youtube: "YouTube",
  tiktok: "TikTok", discord: "Discord", facebook: "Facebook",
};

const LOGO_PATHS: Record<(typeof PLATFORMS)[number], string> = {
  x: "M14.234 10.162L22.977 0h-2.072l-7.591 8.824L7.251 0H.258l9.168 13.343L.258 24H2.33l8.016-9.318L16.749 24h6.993zm-2.837 3.299l-.929-1.329L3.076 1.56h3.182l5.965 8.532l.929 1.329l7.754 11.09h-3.182z",
  bluesky: "M5.202 2.857C7.954 4.922 10.913 9.11 12 11.358c1.087-2.247 4.046-6.436 6.798-8.501C20.783 1.366 24 .213 24 3.883c0 .732-.42 6.156-.667 7.037c-.856 3.061-3.978 3.842-6.755 3.37c4.854.826 6.089 3.562 3.422 6.299c-5.065 5.196-7.28-1.304-7.847-2.97c-.104-.305-.152-.448-.153-.327c0-.121-.05.022-.153.327c-.568 1.666-2.782 8.166-7.847 2.97c-2.667-2.737-1.432-5.473 3.422-6.3c-2.777.473-5.899-.308-6.755-3.369C.42 10.04 0 4.615 0 3.883c0-3.67 3.217-2.517 5.202-1.026",
  instagram: "M7.03.084c-1.277.06-2.149.264-2.91.563a5.9 5.9 0 0 0-2.124 1.388a5.9 5.9 0 0 0-1.38 2.127C.321 4.926.12 5.8.064 7.076s-.069 1.688-.063 4.947s.021 3.667.083 4.947c.061 1.277.264 2.149.563 2.911c.308.789.72 1.457 1.388 2.123a5.9 5.9 0 0 0 2.129 1.38c.763.295 1.636.496 2.913.552c1.278.056 1.689.069 4.947.063s3.668-.021 4.947-.082c1.28-.06 2.147-.265 2.91-.563a5.9 5.9 0 0 0 2.123-1.388a5.9 5.9 0 0 0 1.38-2.129c.295-.763.496-1.636.551-2.912c.056-1.28.07-1.69.063-4.948c-.006-3.258-.02-3.667-.081-4.947c-.06-1.28-.264-2.148-.564-2.911a5.9 5.9 0 0 0-1.387-2.123a5.9 5.9 0 0 0-2.128-1.38C16.997.32 16.124.119 14.847.063C13.569.007 13.158-.006 9.9 0S7.308.022 7.03.084m.262 21.821c-1.17-.052-1.805-.246-2.228-.41c-.56-.217-.96-.477-1.382-.896a3.7 3.7 0 0 1-.895-1.381c-.164-.422-.36-1.057-.413-2.227c-.058-1.265-.07-1.645-.078-4.848s.006-3.583.06-4.848c.052-1.17.246-1.806.41-2.228c.217-.56.477-.96.896-1.382a3.7 3.7 0 0 1 1.38-.895c.423-.165 1.058-.36 2.228-.413c1.265-.058 1.645-.07 4.848-.078s3.583.006 4.849.06c1.17.052 1.805.246 2.228.41c.56.217.96.477 1.381.896c.421.42.68.819.896 1.381c.164.422.36 1.056.413 2.227c.058 1.265.07 1.645.078 4.848s-.006 3.583-.06 4.849c-.052 1.17-.246 1.805-.41 2.228c-.217.56-.477.96-.896 1.381a3.7 3.7 0 0 1-1.38.895c-.423.165-1.058.36-2.228.413c-1.265.058-1.645.07-4.848.078s-3.583-.006-4.849-.06m9.788-15.114a1.44 1.44 0 1 0 1.44-1.44a1.44 1.44 0 0 0-1.44 1.44m-10.526 5.21a5.451 5.451 0 1 0 10.902 0a5.451 5.451 0 0 0-10.902 0m1.902 0a3.55 3.55 0 1 1 7.1 0a3.55 3.55 0 0 1-7.1 0",
  threads: "M18.263 11.097c-.03-3.486-1.92-5.586-5.111-5.586c-2.13 0-3.922.963-4.863 2.499l2.062 1.438c.535-.843 1.272-1.543 2.628-1.543c1.528 0 2.318.85 2.544 2.431a15 15 0 0 0-2.236-.173c-4.125 0-6.068 1.867-6.068 4.336s1.943 3.99 4.804 3.99c3.139 0 5.013-2.115 5.781-4.735c.798.361 1.348 1.204 1.348 2.47c0 3.387-3.907 5.232-7.22 5.232c-4.885 0-8.077-3.207-8.077-8.424c0-6.392 4.223-10.487 9.9-10.487c3.808 0 5.69 1.671 6.97 3.914l2.108-1.475C21.44 2.078 18.331 0 13.663 0C6.227 0 1.168 5.277 1.168 12.934c0 7 4.953 11.066 10.856 11.066c4.878 0 9.809-2.846 9.809-7.716c0-2.545-1.46-4.231-3.569-5.187m-6.09 4.545c-1.51 0-2.428-.704-2.428-1.603c0-1.062 1.204-1.509 2.897-1.509c.693 0 1.337.071 1.918.204c-.49 1.838-1.443 2.908-2.387 2.908",
  linkedin: "M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037c-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85c3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.06 2.06 0 0 1-2.063-2.065a2.064 2.064 0 1 1 2.063 2.065m1.782 13.019H3.555V9h3.564zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0z",
  telegram: "M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12a12 12 0 0 0 12-12A12 12 0 0 0 12 0zm4.962 7.224c.1-.002.321.023.465.14a.5.5 0 0 1 .171.325c.016.093.036.306.02.472c-.18 1.898-.962 6.502-1.36 8.627c-.168.9-.499 1.201-.82 1.23c-.696.065-1.225-.46-1.9-.902c-1.056-.693-1.653-1.124-2.678-1.8c-1.185-.78-.417-1.21.258-1.91c.177-.184 3.247-2.977 3.307-3.23c.007-.032.014-.15-.056-.212s-.174-.041-.249-.024q-.159.037-5.061 3.345q-.72.495-1.302.48c-.428-.008-1.252-.241-1.865-.44c-.752-.245-1.349-.374-1.297-.789q.04-.324.893-.663q5.247-2.286 6.998-3.014c3.332-1.386 4.025-1.627 4.476-1.635",
  youtube: "M23.498 6.186a3.02 3.02 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.02 3.02 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.02 3.02 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.02 3.02 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814M9.545 15.568V8.432L15.818 12z",
  tiktok: "M12.525.02c1.31-.02 2.61-.01 3.91-.02c.08 1.53.63 3.09 1.75 4.17c1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97c-.57-.26-1.1-.59-1.62-.93c-.01 2.92.01 5.84-.02 8.75c-.08 1.4-.54 2.79-1.35 3.94c-1.31 1.92-3.58 3.17-5.91 3.21c-1.43.08-2.86-.31-4.08-1.03c-2.02-1.19-3.44-3.37-3.65-5.71c-.02-.5-.03-1-.01-1.49c.18-1.9 1.12-3.72 2.58-4.96c1.66-1.44 3.98-2.13 6.15-1.72c.02 1.48-.04 2.96-.04 4.44c-.99-.32-2.15-.23-3.02.37c-.63.41-1.11 1.04-1.36 1.75c-.21.51-.15 1.07-.14 1.61c.24 1.64 1.82 3.02 3.5 2.87c1.12-.01 2.19-.66 2.77-1.61c.19-.33.4-.67.41-1.06c.1-1.79.06-3.57.07-5.36c.01-4.03-.01-8.06.01-12.08z",
  discord: "M20.317 4.37a19.8 19.8 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.3 18.3 0 0 0-5.487 0a13 13 0 0 0-.617-1.25a.08.08 0 0 0-.079-.037A19.7 19.7 0 0 0 3.677 4.37a.1.1 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.08.08 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.08.08 0 0 0 .084-.028a14 14 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13 13 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10 10 0 0 0 .372-.292a.07.07 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.07.07 0 0 1 .078.01q.181.149.373.292a.077.077 0 0 1-.006.127a12.3 12.3 0 0 1-1.873.892a.077.077 0 0 0-.041.107q.36.698.772 1.352a.076.076 0 0 0 .084.028a19.8 19.8 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.06.06 0 0 0-.031-.03M8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.956-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.956 2.418-2.157 2.418m7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418",
  facebook: "M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978c.401 0 .955.042 1.468.103a9 9 0 0 1 1.141.195v3.325a9 9 0 0 0-.653-.036a27 27 0 0 0-.733-.009c-.707 0-1.259.096-1.675.309a1.7 1.7 0 0 0-.679.622c-.258.42-.374.995-.374 1.752v1.297h3.919l-.386 2.103l-.287 1.564h-3.246v8.245C19.396 23.238 24 18.179 24 12.044c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 6.627 5.373 12 12 12a12 12 0 0 0 2.153-.195",
};

/* Fan geometry: one origin square on the left, five nodes per row. */
const FAN_OX = 114;
const FAN_OY = 148;
const FAN_ROWS = [76, 220];
const FAN_COLS = [258, 322, 386, 450, 514];
const FAN_CYCLE = 4.5;
const FAN_TRAVEL_END = 37;
const FAN_STAGGER = 0.27;

type FanNode = { slug: (typeof PLATFORMS)[number]; cx: number; cy: number };

const FAN_NODES: FanNode[] = PLATFORMS.map((slug, i) => ({
  slug,
  cx: FAN_COLS[i % 5],
  cy: FAN_ROWS[Math.floor(i / 5)],
}));

const CAPABILITIES = [
  {
    title: "One request, no dashboard",
    body: "Every action is a plain HTTP call. Drive it from cron, n8n, a CI job, or an AI agent. The browser UI is optional, never required.",
    evidence: "POST /dispatch",
  },
  {
    title: "Three queue backends",
    body: "JSONL on disk needs no infrastructure. Redis or Postgres when you outgrow one worker. Selected by an environment variable, not a rewrite.",
    evidence: "JSONL | Redis | Postgres",
  },
  {
    title: "Ten adapters, one contract",
    body: "Every platform implements the same function signature. The worker owns retry, backoff, and webhooks so an adapter never has to.",
    evidence: "tuple[bool, str, str]",
  },
  {
    title: "Per-platform media specs",
    body: "Ten image specs and seven video specs are built in. Send an image, get it back at the exact dimensions the target expects.",
    evidence: "GET /media/specs",
  },
];

const COMPARISON: [string, string][] = [
  ["Per-account fees that compound monthly", "Self-host free, no ceilings"],
  ["OAuth tokens held on someone else's servers", "Credentials stay in your .env"],
  ["Failures buried in a vendor dashboard", "Every error visible in your queue, retryable"],
  ["Inbox, analytics, and scheduling behind paid tiers", "All ten platforms in one build"],
  ["Your audience's data lingers after you cancel", "Your queue, your disk, your call"],
  ["Vendor lock-in by design", "MIT licensed, fork it whenever"],
];

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

type InstallKey = "dmg" | "brew" | "curl" | "docker" | "pip";

const INSTALL: Record<InstallKey, { label: string; time: string; needs: string; code?: string; note: string }> = {
  dmg: {
    label: "macOS app",
    time: "10s",
    needs: "macOS 13+",
    note: "SwiftUI menubar app that bundles the Python server, so there is no separate Python install. First launch: right-click, then Open, to bypass Gatekeeper once.",
  },
  brew: {
    label: "Homebrew",
    time: "~2 min",
    needs: "macOS",
    code: `# Add the tap
brew tap matthew-selvam/open-dispatch \\
  ${GITHUB}
brew install open-dispatch

# Credentials
$EDITOR ~/.open-dispatch/.env

# Run it
open-dispatch`,
    note: "brew services wires a launchd plist so the server starts at login.",
  },
  curl: {
    label: "install.sh",
    time: "~90s",
    needs: "macOS & Linux",
    code: `curl -fsSL \\
  https://raw.githubusercontent.com/Matthew-Selvam/Open-Dispatch/main/install.sh \\
  | bash

$EDITOR ~/.open-dispatch/.env
open-dispatch`,
    note: "Writes a launchd plist on macOS or a systemd user unit on Linux. No sudo required.",
  },
  docker: {
    label: "Docker",
    time: "~60s",
    needs: "Any platform",
    code: `git clone ${GITHUB}
cd Open-Dispatch
cp .env.example .env      # add your platform credentials
docker compose up -d

# Confirm it is live
curl http://localhost:8000/healthz`,
    note: "No Python setup. Multi-arch image (amd64 + arm64), non-root user, optional Redis profile for multi-worker throughput.",
  },
  pip: {
    label: "pip",
    time: "Instant",
    needs: "Python 3.11+",
    code: `pip install git+${GITHUB}.git

# Optional extras
pip install "open-dispatch[redis]"
pip install "open-dispatch[postgres]"

uvicorn api.app:app --reload`,
    note: "Best if you are embedding Open-Dispatch in an existing Python codebase.",
  },
};

const INSTALL_ORDER: InstallKey[] = ["dmg", "brew", "curl", "docker", "pip"];

const FAQS = [
  {
    q: "Which install method should I use?",
    a: "On macOS, the app is the shortest path: one download, drag to Applications, done. If you want a terminal workflow, Homebrew gives you a login service via brew services. On a Linux VPS, Docker avoids the Python setup entirely.",
  },
  {
    q: "How do I self-host on a VPS?",
    a: "Docker is the cleanest option. It runs as a non-root user, needs no Python on the host, and ships an optional Redis sidecar. The Docker section of the README walks through it step by step.",
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
    a: "Each platform's developer console issues its own keys, and .env.example in the repo lists every variable Open-Dispatch reads, grouped by platform. Copy it to .env and fill in only the platforms you dispatch to. The API skips platforms you leave unset.",
  },
  {
    q: "Can I add another platform?",
    a: "Yes. The adapter contract is a single Python function, roughly 80 lines. Register it in adapters/__init__.py, document its format key in the README, and the worker handles retry, backoff, and webhooks for you.",
  },
];

export default function Page() {
  const [activeInstall, setActiveInstall] = useState<InstallKey>("dmg");
  const [copied, setCopied] = useState(false);

  const install = INSTALL[activeInstall];

  function copySnippet() {
    if (!install.code) return;
    navigator.clipboard.writeText(install.code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    });
  }

  return (
    <>
      <a className="skip" href="#main">Skip to content</a>

      <header>
        <div className="wrap nav">
          <Link className="brand" href="/" aria-label="Open-Dispatch home">
            <BrandMark size={22} />
            open-dispatch
          </Link>
          <nav aria-label="Sections">
            <a href="#how">How it works</a>
            <a href="#api">API</a>
            <a href="#install">Install</a>
            <a href="#faq">FAQ</a>
            <a className="gh-btn" href={GITHUB} target="_blank" rel="noopener noreferrer">
              <GitHubIcon />
              GitHub
            </a>
          </nav>
        </div>
      </header>

      <main id="main">
        {/* ── hero ─────────────────────────────────────────────────── */}
        <section className="hero" style={{ borderTop: "none" }}>
          <div className="wrap hero-grid">
            <div>
              <p className="eyebrow">MIT licensed · {TEST_COUNT} tests</p>
              <h1>
                One request in.
                <br />
                <span className="out">Ten platforms out.</span>
              </h1>
              <p className="sub">
                Open-Dispatch is a self-hosted dispatch queue for social
                platforms. Your credentials never leave your machine, and
                nothing meters you per account.
              </p>
              <div className="hero-ctas">
                <a className="btn btn-primary" href="#install">
                  Install <ArrowRight size={15} aria-hidden />
                </a>
                <a className="btn btn-ghost" href={GITHUB} target="_blank" rel="noopener noreferrer">
                  GitHub
                </a>
              </div>
            </div>

            <div className="panel">
              <div className="bar">
                <span className="dot" /><span className="dot" /><span className="dot" />
                <span className="name">dispatch.sh</span>
                <span className="verb">POST /dispatch</span>
              </div>
              <div className="request" aria-hidden>
                <span className="k">curl</span>
                {` -X POST localhost:8000/dispatch -d '{"targets":["x","bluesky","instagram","threads","linkedin","telegram","youtube","tiktok","discord","facebook"], ...}'`}
              </div>
              <DispatchFan />
              <div className="fan-response">
                <span className="ok">202 accepted</span>
                <span>queued as 7f3a91c4</span>
              </div>
            </div>
          </div>
        </section>

        {/* ── stat band ────────────────────────────────────────────── */}
        <div className="stats">
          <div className="wrap row">
            <div className="stat"><b>10</b><span>platform adapters</span></div>
            <div className="stat"><b>{TEST_COUNT}</b><span>tests, no network</span></div>
            <div className="stat"><b>3</b><span>queue backends</span></div>
            <div className="stat"><b>5</b><span>ways to install</span></div>
          </div>
        </div>

        {/* ── comparison ───────────────────────────────────────────── */}
        <section aria-labelledby="compare-h">
          <div className="wrap">
            <h2 id="compare-h">What hosted schedulers take from you</h2>
            <div className="ledger">
              <div className="ledger-head">
                <div>Hosted tools</div>
                <div className="us">Open-Dispatch</div>
              </div>
              {COMPARISON.map(([them, us]) => (
                <div className="ledger-row" key={them}>
                  <div className="them">
                    <XIcon className="mark" size={14} aria-hidden />
                    {them}
                  </div>
                  <div className="us">
                    <Check className="mark" size={14} aria-hidden color="var(--color-primary)" />
                    {us}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── how it works ─────────────────────────────────────────── */}
        <section id="how" aria-labelledby="how-h">
          <div className="wrap">
            <h2 id="how-h">The whole path, end to end</h2>
            <p className="lede">
              A request enters the queue, a worker picks it up, an adapter
              publishes it, and a webhook reports the result. There is no
              hidden step between those four.
            </p>

            <div className="flow" role="img" aria-label="Request path: dispatch endpoint, queue, worker, platform adapters, webhook">
              <FlowNode chip="POST /dispatch" what="one HTTP call" />
              <FlowNode chip="Queue" what="JSONL | Redis | Postgres" />
              <FlowNode chip="Worker" what="retry + backoff" />
              <FlowNode chip={`adapters/ ×${ADAPTER_COUNT}`} what="one per platform" />
              <FlowNode chip="webhook_url" what="on publish or fail" />
            </div>

            <div className="flow-split">
              <div>
                <h3 style={{ fontSize: 17, fontWeight: 650 }}>Adding a platform is one function</h3>
                <p style={{ marginTop: 10, fontSize: 14.5, color: "var(--color-body)" }}>
                  The worker owns retry, backoff, and webhook delivery, so an
                  adapter only has to publish and report a result. Register it
                  in one dict and document its format key. That is the whole
                  integration surface.
                </p>
              </div>
              <div className="panel">
                <div className="bar">
                  <span className="dot" /><span className="dot" /><span className="dot" />
                  <span className="name">adapters/myplatform.py</span>
                </div>
                <pre className="code"><code>{`def publish(unit: ContentUnit, account: str | None) -> tuple[bool, str, str]:
    """Return (ok, post_id, error_message)."""
    # the worker handles retry, backoff, webhooks`}</code></pre>
              </div>
            </div>
          </div>
        </section>

        {/* ── capabilities ─────────────────────────────────────────── */}
        <section aria-labelledby="caps-h">
          <div className="wrap">
            <h2 id="caps-h">What it does, with the artifact that proves it</h2>
            <div className="caps">
              {CAPABILITIES.map((c) => (
                <div className="cap" key={c.title}>
                  <h3>{c.title}</h3>
                  <p>{c.body}</p>
                  <p className="ev">{c.evidence}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── api ──────────────────────────────────────────────────── */}
        <section id="api" aria-labelledby="api-h">
          <div className="wrap">
            <div className="api-head">
              <div>
                <h2 id="api-h">Every endpoint, no client library required</h2>
                <p className="lede">
                  Plain HTTP with JSON in and JSON out. Full request and
                  response shapes live on the API reference page.
                </p>
              </div>
              <Link className="api-link" href="/api-reference">API reference →</Link>
            </div>
            <div className="api-table-wrap">
              <table className="api">
                <thead>
                  <tr>
                    <th scope="col">Method</th>
                    <th scope="col">Path</th>
                    <th scope="col">Purpose</th>
                  </tr>
                </thead>
                <tbody>
                  {ENDPOINTS.map(([method, path, purpose]) => (
                    <tr key={path}>
                      <td className={`m-${method.toLowerCase()}`}>{method}</td>
                      <td className="path">{path}</td>
                      <td>{purpose}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* ── install ──────────────────────────────────────────────── */}
        <section id="install" aria-labelledby="install-h">
          <div className="wrap">
            <h2 id="install-h">Five ways in, shortest first</h2>
            <div className="tabs" role="tablist" aria-label="Install method">
              {INSTALL_ORDER.map((key) => (
                <button
                  key={key}
                  className="tab"
                  role="tab"
                  aria-selected={activeInstall === key}
                  onClick={() => setActiveInstall(key)}
                >
                  <span className="t">{INSTALL[key].label}</span>
                  <span className="m">{INSTALL[key].time} · {INSTALL[key].needs}</span>
                </button>
              ))}
            </div>

            <div className="tabpane panel">
              <div className="bar">
                <span className="dot" /><span className="dot" /><span className="dot" />
                <span className="name">{install.label}</span>
                {install.code && (
                  <button className="copy-btn" type="button" onClick={copySnippet}>
                    {copied ? "copied" : "copy"}
                  </button>
                )}
              </div>

              {activeInstall === "dmg" ? (
                <div className="dmg-pane">
                  <p className="v">Open-Dispatch 0.4.0</p>
                  <p className="req">macOS 13 Ventura or later · Apple Silicon and Intel</p>
                  <a className="btn btn-primary" href={DMG_URL}>Download .dmg</a>
                  <p className="alt">
                    <a href={`${GITHUB}/releases`} target="_blank" rel="noopener noreferrer">all releases</a>
                    {" · build from source: bash scripts/make-dmg.sh"}
                  </p>
                </div>
              ) : (
                <pre className="code"><code>{install.code}</code></pre>
              )}

              <p className="note">{install.note}</p>
            </div>
          </div>
        </section>

        {/* ── faq ──────────────────────────────────────────────────── */}
        <section id="faq" aria-labelledby="faq-h">
          <div className="wrap">
            <h2 id="faq-h">Questions worth answering before you install</h2>
            <dl className="faq-list">
              {FAQS.map((f) => (
                <div className="faq-row" key={f.q}>
                  <dt>{f.q}</dt>
                  <dd>{f.a}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        {/* ── close ────────────────────────────────────────────────── */}
        <section aria-labelledby="close-h" style={{ borderTop: "1px solid var(--border-soft)" }}>
          <div className="wrap close-cta">
            <div>
              <h2 id="close-h">Run it yourself</h2>
              <p className="facts">
                {TEST_COUNT} tests · {ADAPTER_COUNT} adapters · 3 queue backends · MIT
              </p>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
              <a className="btn btn-primary" href="#install">
                Install <ArrowRight size={15} aria-hidden />
              </a>
              <a className="btn btn-ghost" href={GITHUB} target="_blank" rel="noopener noreferrer">
                GitHub
              </a>
            </div>
          </div>
        </section>
      </main>

      <footer>
        <div className="wrap foot">
          <span>open-dispatch · MIT © Matthew Selvam</span>
          <div className="links">
            <a href={`${GITHUB}/releases`} target="_blank" rel="noopener noreferrer">Releases</a>
            <a href={`${GITHUB}/blob/main/CONTRIBUTING.md`} target="_blank" rel="noopener noreferrer">Contributing</a>
            <a href={`${GITHUB}/blob/main/SECURITY.md`} target="_blank" rel="noopener noreferrer">Security</a>
            <a href={`${GITHUB}/blob/main/INSTALL_METHODS.md`} target="_blank" rel="noopener noreferrer">Install docs</a>
          </div>
        </div>
      </footer>
    </>
  );
}

/* ── pieces ─────────────────────────────────────────────────────────── */

/** The repo's favicon mark, reused as the nav brand glyph. */
function BrandMark({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden>
      <rect x="4" y="4" width="92" height="92" rx="22" fill="#0f1418" stroke="#243240" strokeWidth="4" />
      <g stroke="#3b9eff" strokeWidth="9" strokeLinecap="round">
        <line x1="31" y1="50" x2="71" y2="27" />
        <line x1="31" y1="50" x2="77" y2="50" />
        <line x1="31" y1="50" x2="71" y2="73" />
      </g>
      <g fill="#3b9eff">
        <circle cx="71" cy="27" r="9" />
        <circle cx="77" cy="50" r="9" />
        <circle cx="71" cy="73" r="9" />
      </g>
      <circle cx="31" cy="50" r="13" fill="#7dc3ff" />
      <circle cx="31" cy="50" r="6" fill="#0f1418" />
    </svg>
  );
}

/**
 * Hero visual: the dispatch mark, enlarged into a live diagram. Comets
 * travel from the origin square to each of the ten real platform marks,
 * staggered so the fan reads as one request being distributed.
 */
function DispatchFan() {
  return (
    <svg
      className="fan"
      viewBox="0 0 560 300"
      role="img"
      aria-label={`One dispatch request fanning out to ${PLATFORMS.map((p) => PLATFORM_NAMES[p]).join(", ")}`}
    >
      <g fill="none" strokeLinecap="round">
        {FAN_NODES.map((n) => (
          <line key={`b-${n.slug}`} className="fl-base" x1={FAN_OX} y1={FAN_OY} x2={n.cx} y2={n.cy} />
        ))}
        {FAN_NODES.map((n, i) => (
          <line
            key={`c-${n.slug}`}
            className="comet"
            x1={FAN_OX}
            y1={FAN_OY}
            x2={n.cx}
            y2={n.cy}
            pathLength={100}
            style={{ animationDelay: `${(i * FAN_STAGGER).toFixed(2)}s` }}
          />
        ))}
      </g>
      <circle className="opulse" cx="86" cy="148" r="34" fill="none" stroke="#3b9eff" strokeWidth="2" />
      <g>
        {FAN_NODES.map((n) => (
          <circle key={`t-${n.slug}`} cx={n.cx} cy={n.cy} r="22" fill="#10161d" stroke="#243240" strokeWidth="1.5" />
        ))}
        {FAN_NODES.map((n) => (
          <path
            key={`p-${n.slug}`}
            d={LOGO_PATHS[n.slug]}
            fill="#eaf3fe"
            transform={`translate(${n.cx - 11}, ${n.cy - 11}) scale(${22 / 24})`}
          />
        ))}
      </g>
      <g>
        <rect x="52" y="114" width="68" height="68" rx="17" fill="#0f1418" stroke="#2c4358" strokeWidth="1.5" />
        <g stroke="#3b9eff" strokeWidth="7" strokeLinecap="round">
          <line x1="72" y1="148" x2="94" y2="135" />
          <line x1="72" y1="148" x2="97" y2="148" />
          <line x1="72" y1="148" x2="94" y2="161" />
        </g>
        <g fill="#3b9eff">
          <circle cx="94" cy="135" r="6" />
          <circle cx="97" cy="148" r="6" />
          <circle cx="94" cy="161" r="6" />
        </g>
        <circle cx="72" cy="148" r="9" fill="#7dc3ff" />
        <circle cx="72" cy="148" r="4" fill="#0f1418" />
      </g>
      {FAN_NODES.map((n, i) => (
        <circle
          key={`h-${n.slug}`}
          className="hit"
          cx={n.cx}
          cy={n.cy}
          r="22"
          style={{ animationDelay: `${(i * FAN_STAGGER + (FAN_CYCLE * FAN_TRAVEL_END) / 100).toFixed(2)}s` }}
        />
      ))}
    </svg>
  );
}

function FlowNode({ chip, what }: { chip: string; what: string }) {
  return (
    <div className="node">
      <span className="chip">{chip}</span>
      <span className="what">{what}</span>
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
