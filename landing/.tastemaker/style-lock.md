# Open-Dispatch — style lock

Project: `Matthew-Selvam/Open-Dispatch`, surface: `landing/` (public marketing page, Next.js 16 + Tailwind 4)
Established: 2026-10-01

## Design read

- **Surface type:** public marketing landing page for a self-hosted developer tool.
- **Audience:** developers and technical operators evaluating self-host vs. Buffer/Hootsuite. They arrive skeptical and comparison-ready.
- **Visitor mode:** evaluate then install. High intent, short attention, wants proof over adjectives.
- **Visual lane:** technical dark. Infrastructure-tool register, not lifestyle-app register. Closer to a status console than to a SaaS brochure.
- **Dials:** low-to-medium density; motion restrained and functional; variance from the template via structure, not decoration; art direction anchored on real code and real numbers.

## Direction contract

- **Thesis:** this is plumbing, not a product to be admired. The page should read like the tool's own logs: real endpoints, real counts, real numbers, nothing decorative that isn't load-bearing.
- **First viewport:** one promise (one HTTP call, ten platforms), one real request/response panel, one primary action (install), and the honest count.
- **System:** dark technical tokens from `generate_palette.py --mood technical --mode dark`; Inter for UI, JetBrains Mono for all code/endpoint/numeric content.
- **Risk:** a developer tool with a beautiful marketing page looks like a hosted SaaS trying to be something it isn't. Mitigation: every visual is a real artifact (a live snippet, a real endpoint table, a verified stat), and no invented metrics.

## Color contract

Generated, not hand-picked. Source: `python3 scripts/generate_palette.py --mood technical --mode dark` (base hue 253.4, accent hue 13.4, triadic).

| Role | Value |
| --- | --- |
| text | `#eaf3fe` |
| bg | `#0f1318` |
| surface | `#1b1f24` |
| primary | `#4277b4` |
| on-primary | `#ffffff` |
| secondary | `#202f41` |
| accent | `#da818a` |
| border | `#262b30` |

**Text-safe (>= 4.5:1) — legal for body text, links, labels on a fill:**
`bg/on-primary`, `text/bg`, `surface/on-primary`, `text/surface`, `border/on-primary`, `text/border`, `bg/accent`, `surface/accent`, `accent/border`, `primary/on-primary`

**UI-safe (>= 3.0:1) — legal for large text, icons, state-carrying borders:**
`text/primary`, `bg/primary`, `surface/primary`, `primary/border`

**Decorative (< 3.0) — must never be the only thing conveying state:**
`accent/on-primary`, `text/accent`, `primary/accent`, `bg/border`, `surface/border`, `bg/surface`, `text/on-primary`

**Dark mode:** locked dark, not a toggle. This is a developer infrastructure tool; a light mode would dilute the register and there is no product requirement for one. If a toggle is ever required, generate the light pair from the same seed in `--mode light` and re-run `check_contrast.py --matrix` before shipping.

## Typography

- **UI / display:** Inter (already loaded via `next/font/google` in `layout.tsx`).
- **Code, endpoints, numbers, metadata:** JetBrains Mono. The existing page already leans on mono for structure; that instinct is correct for this product and stays.
- Two families only. No third accent face.

## Density & spacing

- Section padding: pivotal sections (hero, install) `py-24` to `py-32`; connective sections `py-20`. Never one uniform value across all sections.
- Card internal padding: `p-6` (24px) minimum for content cards. Compact stat tiles may use `p-4`.
- Rule: internal padding <= external gap between neighbors.
- Content width: `max-w-6xl` for the page frame, `max-w-3xl` for prose, `max-w-2xl` for subheads.
- Radius scale: `rounded-lg` (tabs, small controls), `rounded-xl` (panels, code cards), `rounded-2xl` reserved for feature tiles. No pill buttons except the small inline status chip.

## Structure

**Macrostructure: Product Demo / Workbench (#7)**

Rotation: this is the project's first build under this skill, so there is no prior `log.json` entry to rotate against. Recorded anyway for the next pass.

Rationale: Open-Dispatch's strongest argument is "see it work." The product is a CLI and an HTTP API. The generic Feature Stack (#1) is the default reach for technical SaaS and is exactly what the current page does. Workbench inverts the priority: the hero *is* a real request and its real response, the architecture is a real pipeline, and features become evidence attached to those artifacts rather than a 3-up card grid.

**Narrative arc (six beats):**
1. **Hook** — one HTTP call, ten platforms. Real curl against the real endpoint.
2. **Problem** — hosted schedulers hold your OAuth tokens and meter every account.
3. **Solution** — the queue is yours: three backends, on your disk.
4. **How it works** — the real pipeline, dispatch to adapter to webhook.
5. **Proof** — verified numbers only: 210 tests, 10 adapters, 10 image + 7 video specs, MIT.
6. **Close** — five install paths, the shortest one first.

**Component archetypes:** Workbench hero (real request/response), comparator table (them vs. us, retained — it is genuine differentiator proof), pipeline diagram, endpoint ledger, install matrix, FAQ ledger, minimal footer.

## Assets

- **Photography:** none. This is a CLI/API product; stock photography of people at laptops would be a lie about what the product is. The honest visual language is code, endpoints, and diagrams.
- **Illustrations:** none. Same reason. `~/.ideagram/undraw/` is unpopulated and a primitive-composition fallback would be a visible quality drop for no gain.
- **Icons:** `lucide-react` (already a dependency) for all UI iconography. **Emoji are removed** — the platform row, comparison table, install tabs, n8n section, and macOS download pane all use emoji as icons today, which is a MEDIUM anti-slop finding and the single most common "AI built this" tell in the current markup.
- **Brand logos:** fetched SVG marks for the platform row, replacing emoji chips with real logos.

## Copy constraints

- **No em dashes in shipped copy.** Hard ban. The current page has 30+ violations.
- **Every number must be verifiable against the repo.** Verified this pass: 210 tests (pytest), 10 adapters (`adapters/__init__.py` ADAPTERS), 10 image + 7 video specs (`media`), 3 queue backends (`api/queue.py`), 5 install methods.
- **Corrected claim:** the current page says "seven platforms" in the hero, metadata, and body. The repo registers **ten** adapters. The copy is wrong and understates the product.
- No invented customers, metrics, testimonials, or ratings.

## Build stamp

Recorded in the CSS header comment per `references/diversification.md`.
