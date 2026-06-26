"use client";

import Link from "next/link";

const GITHUB = "https://github.com/Matthew-Selvam/Open-Dispatch";

function GitHubIcon() {
  return (
    <svg viewBox="0 0 16 16" className="w-3.5 h-3.5 fill-current" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
    </svg>
  );
}

const ENDPOINTS = [
  {
    method: "GET",
    path: "/healthz",
    purpose: "Liveness probe",
    description: "Returns JSON for API clients, the HTML dashboard for browsers.",
    example: `curl http://localhost:8000/healthz`,
    response: `{"status": "ok"}`,
  },
  {
    method: "POST",
    path: "/dispatch",
    purpose: "Post content to one or many platforms",
    description: "Enqueues a ContentUnit. Returns a queue row ID you can poll.",
    example: `curl -X POST http://localhost:8000/dispatch \\
  -H "Content-Type: application/json" \\
  -d '{
    "targets": ["twitter", "bluesky"],
    "formats": {
      "twitter_thread": {
        "tweets": ["your tweet here"]
      },
      "bluesky_post": {
        "text": "your post here"
      }
    }
  }'`,
    response: `{"id": "abc123", "status": "queued", "targets": ["twitter", "bluesky"]}`,
  },
  {
    method: "GET",
    path: "/queue",
    purpose: "List queue rows",
    description: "Filter by status: queued, publishing, published, failed, dead.",
    example: `curl "http://localhost:8000/queue?status=published"`,
    response: `[{"id": "abc123", "status": "published", "platform": "twitter", ...}]`,
  },
  {
    method: "GET",
    path: "/queue/{id}",
    purpose: "Get one queue row",
    description: "Content-negotiated — JSON for API clients (Accept: application/json), HTML detail page for browsers.",
    example: `curl -H "Accept: application/json" http://localhost:8000/queue/abc123`,
    response: `{"id": "abc123", "status": "published", "post_id": "1234567890", ...}`,
  },
  {
    method: "POST",
    path: "/queue/{id}/retry",
    purpose: "Retry a failed or dead row",
    description: "Resets the row to queued so the worker picks it up again.",
    example: `curl -X POST http://localhost:8000/queue/abc123/retry`,
    response: `{"id": "abc123", "status": "queued"}`,
  },
  {
    method: "DELETE",
    path: "/queue/{id}",
    purpose: "Delete a queue row",
    description: "Permanently removes the row. Cannot be undone.",
    example: `curl -X DELETE http://localhost:8000/queue/abc123`,
    response: `{"deleted": true}`,
  },
  {
    method: "POST",
    path: "/ai/adapt",
    purpose: "Rewrite a caption per platform",
    description: "Takes a source caption and returns platform-optimised versions. Uses Ollama → OpenRouter → heuristic fallback.",
    example: `curl -X POST http://localhost:8000/ai/adapt \\
  -H "Content-Type: application/json" \\
  -d '{
    "text": "We just shipped v0.4 — self-host free, MIT.",
    "platforms": ["twitter", "linkedin", "instagram"]
  }'`,
    response: `{"twitter": "v0.4 is live. self-host free, MIT ↓", "linkedin": "...", "instagram": "..."}`,
  },
  {
    method: "POST",
    path: "/media/transcode",
    purpose: "Resize an image to a platform spec",
    description: "Sends back the resized image as binary. Accepts image/* body.",
    example: `curl -X POST "http://localhost:8000/media/transcode?platform=twitter" \\
  -H "Content-Type: image/jpeg" \\
  --data-binary @photo.jpg \\
  --output photo.twitter.jpg`,
    response: `(binary JPEG)`,
  },
  {
    method: "GET",
    path: "/media/specs",
    purpose: "List all platform image specs",
    description: "Returns dimensions, aspect ratio, and format for all 10 built-in specs.",
    example: `curl http://localhost:8000/media/specs`,
    response: `{"twitter": {"width": 1600, "height": 900, "format": "JPEG"}, ...}`,
  },
];

const METHOD_COLOR: Record<string, string> = {
  GET:    "text-[var(--color-accent)]",
  POST:   "text-green-400",
  DELETE: "text-red-400",
};

function CodeBlock({ code }: { code: string }) {
  return (
    <pre className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg p-4 text-xs font-mono text-[var(--color-body)] overflow-x-auto whitespace-pre leading-relaxed">
      {code}
    </pre>
  );
}

export default function ApiReferencePage() {
  return (
    <>
      <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-bg)]/90 backdrop-blur">
        <div className="mx-auto max-w-6xl px-6 h-14 flex items-center justify-between">
          <Link href="/" className="font-mono text-sm font-semibold text-[var(--color-fg)] tracking-tight hover:opacity-80 transition-opacity">
            open<span className="text-[var(--color-accent)]">-dispatch</span>
          </Link>
          <nav className="flex items-center gap-5 text-sm text-[var(--color-body)]">
            <Link href="/#install"   className="hover:text-[var(--color-fg)] transition-colors hidden sm:block">Install</Link>
            <Link href="/#features"  className="hover:text-[var(--color-fg)] transition-colors hidden sm:block">Features</Link>
            <Link href="/#faq"       className="hover:text-[var(--color-fg)] transition-colors hidden sm:block">FAQ</Link>
            <Link href="/api-reference" className="text-[var(--color-accent)] hidden sm:block">API</Link>
            <Link
              href={GITHUB} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium text-[var(--color-fg)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors"
            >
              <GitHubIcon /> GitHub
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-16">
        {/* Header */}
        <div className="mb-12">
          <p className="text-xs font-mono text-[var(--color-accent)] mb-2 uppercase tracking-widest">Reference</p>
          <h1 className="text-3xl font-bold tracking-tight mb-3">API Reference</h1>
          <p className="text-[var(--color-body)] text-sm max-w-2xl">
            Once Open-Dispatch is running, the API is available at{" "}
            <code className="bg-[var(--color-surface)] border border-[var(--color-border)] px-1.5 py-0.5 rounded text-xs">
              http://localhost:8000
            </code>
            . No auth is required by default — it's designed for trusted self-hosting. Front it with{" "}
            Cloudflare Access, Tailscale, or basic auth if you expose it to the internet.
          </p>
        </div>

        {/* Quick test */}
        <div className="mb-14 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
          <h2 className="text-sm font-semibold text-[var(--color-fg)] mb-1">Confirm it&apos;s running</h2>
          <p className="text-xs text-[var(--color-body)] mb-3">Run this first. You should see <code className="text-[var(--color-accent)]">{`{"status":"ok"}`}</code>.</p>
          <CodeBlock code={`curl http://localhost:8000/healthz`} />
        </div>

        {/* Endpoints */}
        <div className="space-y-10">
          {ENDPOINTS.map((ep) => (
            <div key={ep.path} className="border border-[var(--color-border)] rounded-xl overflow-hidden">
              <div className="flex items-center gap-3 px-5 py-4 bg-[var(--color-surface)] border-b border-[var(--color-border)]">
                <span className={`font-mono text-xs font-bold w-14 shrink-0 ${METHOD_COLOR[ep.method] ?? "text-[var(--color-fg)]"}`}>
                  {ep.method}
                </span>
                <code className="font-mono text-sm text-[var(--color-fg)]">{ep.path}</code>
                <span className="text-xs text-[var(--color-muted)] ml-auto hidden sm:block">{ep.purpose}</span>
              </div>
              <div className="px-5 py-5 space-y-4">
                <p className="text-sm text-[var(--color-body)]">{ep.description}</p>
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-widest text-[var(--color-muted)] mb-2">Request</p>
                  <CodeBlock code={ep.example} />
                </div>
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-widest text-[var(--color-muted)] mb-2">Response</p>
                  <CodeBlock code={ep.response} />
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* ContentUnit shape */}
        <div className="mt-14 border border-[var(--color-border)] rounded-xl overflow-hidden">
          <div className="px-5 py-4 bg-[var(--color-surface)] border-b border-[var(--color-border)]">
            <h2 className="text-sm font-semibold text-[var(--color-fg)]">ContentUnit — full shape</h2>
          </div>
          <div className="px-5 py-5">
            <CodeBlock code={`{
  "category":      "general",          // optional label
  "targets":       ["twitter:work", "bluesky", "threads"],
  "scheduled_for": "2026-06-26T18:00:00+00:00",  // omit to post immediately
  "formats": {
    "twitter_thread":   { "tweets": ["t1", "t2"], "media_paths": [] },
    "bluesky_post":     { "text": "…", "images": [{"path": "…", "alt": "…"}] },
    "telegram_message": { "text": "…", "photo_path": "…", "parse_mode": "HTML" },
    "instagram_post":   { "caption": "…", "image_url": "https://…" },
    "linkedin_post":    { "text": "…", "asset_urn": "urn:li:digitalmediaAsset:…" },
    "threads_post":     { "text": "…", "image_url": "https://…", "video_url": "https://…" }
  },
  "webhook_url": "https://example.com/callback"  // optional, fires on publish/fail
}`} />
            <p className="text-xs text-[var(--color-body)] mt-3">
              <strong className="text-[var(--color-fg)]">Target syntax:</strong>{" "}
              <code className="text-[10px] bg-[var(--color-bg)] px-1 rounded">platform[:account]</code>.
              Per-account env vars are{" "}
              <code className="text-[10px] bg-[var(--color-bg)] px-1 rounded">{"<PLATFORM>_<FIELD>_<ACCOUNT>"}</code>{" "}
              (uppercase). <code className="text-[10px] bg-[var(--color-bg)] px-1 rounded">twitter:work</code> resolves to{" "}
              <code className="text-[10px] bg-[var(--color-bg)] px-1 rounded">TWITTER_ACCESS_TOKEN_WORK</code>.
            </p>
          </div>
        </div>

        {/* Footer CTA */}
        <div className="mt-14 text-center">
          <p className="text-sm text-[var(--color-body)] mb-4">Something missing or broken?</p>
          <Link
            href={`${GITHUB}/issues`}
            target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded border border-[var(--color-border)] px-4 py-2 text-sm font-medium text-[var(--color-fg)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors"
          >
            <GitHubIcon /> Open an issue
          </Link>
        </div>
      </main>
    </>
  );
}
