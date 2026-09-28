# Productivity Assistant: implementation plan and token budget

Status: proposal, 2026-09-28. Implements the [design](ARCHITECTURE.md). Nothing is
built yet. **All token and turn figures are estimates (targets), not measurements.**

## How this plan is meant to be used

- **One milestone per coding session.** Start a fresh AI-assistant session for each
  milestone, give it this plan and the design, and end the session when the
  milestone's checks pass. Long sessions re-read their whole history on every turn,
  which is where most tokens go.
- **Each milestone ships something usable** and ends with passing tests and a commit.
- **Record actual usage** (turns, input and output tokens) in the
  [tracking table](#tracking-actual-usage) after each milestone, and adjust the
  remaining estimates.

## Milestones

Phase numbers match the design's roadmap.

| # | Phase | Milestone | Delivers | Done when |
| --- | --- | --- | --- | --- |
| M0 | 1 | Foundation | Package layout, `pyproject.toml`, FastAPI app on `127.0.0.1`, settings file outside the repo, SQLite with versioned migrations, session + CSRF + Host/Origin checks, test harness, CI (lint + tests) | App starts; a test proves a cross-site POST is rejected; CI green |
| M1 | 1 | Tasks & projects | Task/project CRUD, dependencies, full change history, Alpine.js pages, JSON/CSV export, daily SQLite backup with rotation | Create, edit, complete and delete through the UI; history records each change; export and backup restore verified |
| M2 | 1 | Prioritization | Transparent score (due date, importance, blocking, effort, age), overrides and pins, Today page showing the score breakdown | Ranking matches documented examples; overrides persist; every rank shows its reasons |
| M3 | 1 | Briefings & scheduler | Factual morning briefing and evening review, in-app scheduler, catch-up on first open | Briefing generated on schedule and after a missed run; no AI involved. **Phase 1 complete: usable daily.** |
| M4 | 2 | AI gateway + capture | Gateway (local-only policy, schema validation, timeouts, audit table), Ollama adapter, capture drafts in an editable form | Invalid, slow or missing model falls back to the manual form; audit rows written; nothing saved without confirmation |
| M5 | 2 | AI summaries & suggestions | Briefing summary, priority suggestions with reasons, proposed weight changes from overrides; local model comparison on synthetic examples | Suggestions accepted or dismissed, never auto-applied; model choice recorded with measured speed and quality |
| M6 | 3 | Documents | Upload (PDF, DOCX, TXT, CSV, XLSX) with size limits, text extraction, SQLite full-text search, candidate tasks for review | Search finds content; candidates become tasks only when accepted |
| M7 | 4 | Jira (read-only) | Token in macOS Keychain, pull assigned issues, show with source and last-synced time, disconnect-and-delete | Imported issues appear on Today; outage shows last copy; disconnect removes data |
| M8 | 4 | Confluence & MS Project (read-only) | Confluence page search/action items; MS Project via file export import (XML/CSV) first | Items imported with source; no writes to either tool |
| M9 | 5 | Optional cloud | Provider-neutral cloud adapter for the chosen provider, per-request consent screen showing exactly what is sent, background jobs blocked | Cloud never used without consent; every send in the audit trail. **Only after the provider decision.** |
| M10 | — | Hardening & release | launchd login item (optional), encrypted export/backup option, log rotation, setup and run docs with verified commands | Fresh-machine setup from the README works end to end |

## Token budget (estimates)

Method: **input tokens ≈ turns × average context**, **output tokens ≈ turns ×
~2,500**. Fresh sessions keep average context around 60,000–90,000 tokens. Most
input tokens are prompt-cache reads, which cost less than fresh input.

| # | Milestone | Turns | Avg. context | Input tokens | Output tokens |
| --- | --- | --- | --- | --- | --- |
| M0 | Foundation | 40 | 60k | 2.4M | 0.10M |
| M1 | Tasks & projects | 50 | 80k | 4.0M | 0.13M |
| M2 | Prioritization | 30 | 80k | 2.4M | 0.08M |
| M3 | Briefings & scheduler | 35 | 80k | 2.8M | 0.09M |
| | **Phase 1 subtotal** | **155** | | **11.6M** | **0.40M** |
| M4 | AI gateway + capture | 50 | 90k | 4.5M | 0.13M |
| M5 | AI summaries & suggestions | 40 | 90k | 3.6M | 0.10M |
| M6 | Documents | 50 | 90k | 4.5M | 0.13M |
| M7 | Jira | 45 | 90k | 4.1M | 0.11M |
| M8 | Confluence & MS Project | 60 | 90k | 5.4M | 0.15M |
| M9 | Optional cloud | 30 | 90k | 2.7M | 0.08M |
| M10 | Hardening & release | 30 | 80k | 2.4M | 0.08M |
| | **Total** | **460** | | **38.8M** | **1.18M** |
| | **With 30% contingency** | | | **~50M** | **~1.5M** |

Expected range: roughly **0.6× to 1.5×** these figures. The largest risks to the
budget are debugging external APIs (M7, M8), document parsing edge cases (M6), and
local-model behavior on an 8 GB Mac (M4, M5).

### Keeping within budget

1. **Fresh session per milestone.** The single biggest lever: a session at 300k
   context spends about four times the tokens per turn of one at 75k.
2. **Hand off through documents.** Update this plan's tracking table and the
   milestone's notes at the end of each session; the next session reads those,
   not the old conversation.
3. **Right-size the model.** Use a faster, cheaper model (for example Sonnet) for
   routine CRUD, templates and tests; reserve the most capable model (for example
   Opus) for design decisions, security (M0, M9) and hard debugging.
4. **Keep outputs small.** Run tests with concise output; read only the files and
   line ranges needed; avoid dumping large logs or documents into the session.
5. **Stop at the gate.** If a milestone exceeds 1.5× its estimate, pause and
   re-plan instead of continuing to iterate.

### Tracking actual usage

| # | Session date | Turns | Input tokens | Output tokens | vs. estimate | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| M0 | | | | | | |
| M1 | | | | | | |

## Runtime token budget (the app's own AI use)

The app enforces these limits in the AI gateway. Values are starting targets, to be
tuned during M5.

| Feature | Max input | Max output | Frequency |
| --- | --- | --- | --- |
| Capture draft | 1,000 | 256 | Per capture |
| Briefing / review summary | 3,000 | 400 | Twice a day |
| Priority suggestions | 4,000 | 400 | Once a day, or on request |
| Document task extraction | 4,000 per chunk, up to 20 chunks | 400 per chunk | Per upload |

- **Local model:** no cost per token, but time and memory matter on an 8 GB Mac.
  Cap background local work at about 200,000 tokens a day and run one request at a
  time.
- **Cloud (M9, if enabled):** a monthly cap set in Settings (starting target
  500,000 tokens), a per-request cap, and a running total shown next to the audit
  trail. When the cap is reached, requests stay local.

## Decisions needed before or during the build

| Needed by | Decision |
| --- | --- |
| M0 | Python version (the Mac's system Python is 3.9; the design says 3.11+) and where private data lives |
| M5 | Local model, chosen from measured results on this Mac |
| M7 | Which integration first, and whether your employer allows importing its data |
| M9 | Whether the cloud is allowed at all, and which provider |
