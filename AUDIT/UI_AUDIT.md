# Web dashboard and UX audit — Phase 8

Browser verification used headless Brave through Playwright against a local server on `127.0.0.1:8765` with isolated `/tmp/od-ui-audit-data`; no worker ran and no external post was made. The preferred collaborative preview opened but two snapshots failed with `PreviewAutomationTimeoutError: Preview automation snapshot timed out after 15000ms.` Computer Use browser inventory was unavailable and its native Brave binding returned `cgWindowNotFound`, so the headless fallback was used. Viewports: desktop 1280×800 and mobile 390×844.

| Page / interaction | Result |
|---|---|
| Dashboard `/`, composer `/compose`, profiles `/profiles`, health `/healthz` | All returned 200, rendered expected headings and titles, no JavaScript page errors in either viewport. |
| Composer platform selection | Checkboxes for ten platforms rendered; switched from default Telegram to Discord. |
| Composer submission | Entered an audit-only draft; `/_compose` returned 200 with `Dispatched.` and a row was added to the isolated queue. No worker/social adapter ran. |
| Empty states | Profile page showed no-profile guidance; dashboard/composer rendered without preexisting user data. |
| Mobile layout | **FAIL**: each tested page had 166 px horizontal document overflow at 390 px viewport; navigation extends off screen. |
| Form labels | **FAIL**: eight composer controls (`profile_id`, text, YouTube fields, schedule, webhook, advanced JSON) had no associated `<label>` or ARIA name. Visual text nearby is not a programmatic label. |

## Findings

| ID | Priority | Evidence and fix |
|---|---|---|
| UI-1 | P2 | At 390 px viewport, `document.documentElement.scrollWidth - innerWidth` = 166 on all four pages. The screenshot shows the top navigation extending off screen. Make navigation wrap/collapse and prevent page-wide horizontal scroll; retest common mobile widths. |
| UI-2 | P2 | Eight composer inputs/selects/textareas have `labels.length == 0` and no `aria-label`/`aria-labelledby`. Add `id`/`for` associations or wrapping labels, including YouTube controls shown conditionally. |
| UI-3 | P2 | Selecting a platform with no credentials still allows a successful-looking `Dispatched.` response; the worker later dead-letters it. This is consistent with API behavior but confusing to new users. Show a warning or clearly state queue acceptance is separate from publication. |

Contrast and screen-reader speech were not measured with dedicated accessibility tools. Profile create/edit/delete, queue retry/purge, AI adaptation, scheduling and video composer paths remain to be exercised end to end. Token-protected browser UI requires a reverse proxy that supplies the bearer header, as README documents; this was not configured in this isolated check.
