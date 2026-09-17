# AI Chief of Staff — MVP requirements

Status: proposed, documentation only. Read with [shared requirements](../README.md#requirements-and-acceptance-map), [design](DESIGN.md) and [implementation plan](IMPLEMENTATION_PLAN.md). CS IDs remain stable; all acceptance criteria below are unimplemented and untested.

## Purpose, users and evidence

One owner on an 8 GB A18 Pro MacBook Neo needs to understand their goals/projects, track commitments, decide what to do today, and coordinate approved specialist workflows. Success means a reliable personal planning tool that remains useful with no model running. The owner is also its sole maintainer; no team roles or hosted service are needed.

Concept source reviewed: user-supplied **“AI Chief of Staff — Agent Architecture & Vision,” March 27, 2026, version 2.0 — Multi-Agent System**, supplied as conversation text during this revision. Current user constraints take precedence over that vision. Its JavaScript classes, SQL tables, endpoints and week-based roadmap are design sketches, not inspected implementation. The supplied text is summarized here; no separate concept file existed in the checkout.

Inspected repository code: `api/main.py` dispatches `log_fitness`; `handlers/fitness.py` returns a message, without persistence. It is not Chief of Staff functionality. The sibling `mac-organizer-prototype/core/tags.py` inserts filepath/tag rows and `rules.py` maps extensions; neither is an implemented AI specialist or a safe file-operation service. Preserve existing code. Reuse those small ideas only through a tested future adapter; HC Audit and AI file tagging stay unavailable until actual code and tests are inspected.

## Concept translation and claim audit

| Concept feature or claim | Evidence / MVP treatment |
| --- | --- |
| Central coordinator understands goals, projects, tasks and priorities | Preserve as explicit relationships, Today, database-backed context selection and visible reasons (CS-01/02/04/05); no promise of comprehensive latent understanding. |
| Checked-off dashboard, goal/project/task management, AI prioritization/briefings | No corresponding code in this checkout; plan as new work, not completed foundation. |
| Checked-off HC Audit Assistant; fully integrated Mission/Master/Consolidated/Mapping parsing and wizard | No HC Automation module located in scoped search; unavailable until source, tests and data-access permissions are supplied. Do not route audit work to the sample fitness handler. |
| File tagger already exists; Research is a proven use case | Only sibling extension rules and SQLite tag insertion verified. Document discovery/parsers, OneDrive, research specialist and safe integration are unverified/deferred. |
| Checked-off Start Ollama button, also listed as unfinished next step | Neither implementation found; internal concept inconsistency recorded. MVP shows runtime availability/manual recovery; no automatic service launch feature. |
| Dynamic agent spawning, simultaneous models, message bus and agent-instance tables | Replace with compiled workflow registry, durable jobs and typed results through one inference broker. No general message bus, agent spawner or runtime registry POST endpoint. |
| Suggest best specialist / accept, reject or defer | Preserve for available registry entries only: show capability, required scope and reason, then Run or Not now. Missing capability becomes a manual backlog note, never self-installed code. |
| Learn preferences and work patterns | Only user-approved typed preferences with provenance (CS-08). No automatic behavioral learning in MVP. |
| Encrypted sensitive data, logged agent communications | Encryption not verified/implemented. Use private state paths/OS protection and deliberate backup policy; retain bounded action history, not blanket prompt/message logging. |
| Week 1–4+ roadmap and success metrics | Replace with gated PR-sized milestones; no inherited delivery-date promise. Measure task correctness, usability and resource limits; active-agent count is not a success metric. |

The concept's communication, research, data-analysis, code and learning specialists are future capability candidates, not MVP services. Preserve extensibility through reviewed implementations and stable contracts, not arbitrary new executable agents.

## Primary workflows

1. Create a goal, link projects, create tasks, attach notes, and set explicit preferences. Read, edit, archive/delete and restore through ordinary forms.
2. Open Today: see overdue, due today, planned today, blocked and unscheduled work; choose a next task with visible ordering reasons. Complete or reschedule it without an extra approval dialog.
3. Type a task in plain language. Optionally request AI structuring, resolve ambiguous project/date fields, and press Save in an editable form. The application validates and commits it once. Manual entry is always available.
4. Generate a factual briefing from current records. Follow supporting task/project links, inspect its as-of time, and optionally request a short narrative or next-step suggestions. Suggestions do not become commitments until accepted.
5. Run an available registered workflow within its declared permissions. View progress/results, cancel, inspect a failure or request a bounded retry. Organizer is a planned integration, disabled until its capability contract passes.
6. Review history and approved preferences. Change/revoke preferences or recurring read-only authorization without claiming the system autonomously learned them.

## MVP requirements and acceptance

| ID / shared parent | Requirement | Acceptance criterion | Delivery |
| --- | --- | --- | --- |
| CS-01 / R-01, R-02 | CRUD for goals, projects, tasks, notes, preferences; goal → projects → tasks, including unassigned tasks. | Create/read/edit/archive/delete/restore all record types; invalid references rejected, no cascading loss of linked work, persisted records survive restart. | C1 |
| CS-02 / R-02 | Status, explicit priority, deadlines, planned day, dependencies and Today. | Date-only and instant deadlines behave as specified across midnight/DST/timezone changes; cycles/self-dependency rejected; blocked work excluded from actionable recommendations. | C1 |
| CS-03 / R-02, R-06 | Plain-language capture proposes fields; ambiguous dates/project matches surfaced. | Ambiguous fixture in [design examples](DESIGN.md#worked-examples) cannot silently assign date/project; Save uses ordinary domain validation and idempotency. Manual fallback succeeds without AI. | C3 |
| CS-04 / R-02, R-06 | Briefing facts retrieved from DB, arithmetic in code, supporting links and as-of time. | Fixture with two overdue tasks renders count two and correct links; completed work excluded. Every factual statement uses supplied facts; stale snapshot visibly labeled. Suggestions displayed separately. | C1 facts; C3 narrative |
| CS-05 / R-02, R-06 | Explain next-step/prioritization suggestions. | Deterministic ordering shows reasons; AI suggestions cite current eligible task IDs or are labeled proposed new tasks. No invented deadline, commitment or silent reprioritization. | C1 rules; C3 AI |
| CS-06 / R-11 | Registry contains only implemented, tested workflow versions with input/output schemas, permissions and timeouts. | Unknown/unimplemented workflow rejected before a job is created. No model-selected import/path/code. HC Audit/file tagger are unavailable unless inspected and qualified. | C2 registry; C3 AI |
| CS-07 / R-05, R-07 | Durable progress, cancellation, bounded retry, failure details and action history. | Crash/restart and duplicate-request fixtures show no duplicate task save or Organizer mutation; uncertain inference blocks new dispatch. UI distinguishes cancel requested from cancelled. | C2; C3 broker |
| CS-08 / R-06, R-09 | Explicit user-approved preferences; no autonomous learning. | Preference change requires direct Save; provenance, old/new values and revocation visible. Model-inferred preferences never enter authoritative settings automatically. | C1 |
| CS-09 / R-06, R-08 | Action authorization follows impact, not model confidence. | Routine direct edits have no approval modal; model proposals need review/Save; scoped authorization cannot grant filesystem execution. Forged approvals and stale previews rejected. | C1–C4 |
| CS-10 / R-04, R-05, R-10 | Optional local AI through shared broker, one global inference at a time. | Missing Ollama leaves CRUD/Today/factual briefing functional; no download/cloud fallback. Exact A18/model qualification and shared resource gates pass before enabling AI. | C3 |
| CS-11 / R-09 | Recoverable private local storage and backup/restore. | Synthetic backup restores records/references/history; restored pending jobs never replay automatically; private state stays outside source. | C1 basics; C2 job recovery |
| CS-12 / R-03, R-07, R-11 | Organizer preview integration with stable request IDs and separate execution authority. | Repeated preview request returns the same job; Chief cannot execute moves. Repeated approved execution in Organizer returns the recorded result or recovery state, never a second move. | C4, conditional |

Delivery labels C1–C4 are defined in [the plan](IMPLEMENTATION_PLAN.md#milestones). They refine, rather than renumber, shared M1/M2/M3.

## Scope and authorization

Immediate user gestures authorize routine local CRUD, completion, planning/reordering, note edits, preference saves, factual briefing generation and job cancellation. Save is the approval for the visible fields; do not add a second confirmation to every Save. Soft deletion offers Undo; referenced records require detach/reassign choices. Permanent erasure is deferred.

Preconfigured authorization is opt-in and revocable: a specific read-only briefing workflow on a chosen schedule while the app is open, with selected project scope, optional eligible AI narrative, daily run cap and expiry. It never authorizes task mutation or file changes. Missed runs coalesce, not replay as a backlog. Manual launch works without configuring this.

Preview required: AI-proposed task creation/edits, batch changes, future Organizer operations, restore replacing current state. Preview names target records, old/new fields, evidence, and expiry/version constraints. New filesystem access requires explicit roots and read scope, even for an Organizer preview. Actual file moves require separate approval inside Organizer. No authorization grant may include arbitrary future tools or external destinations.

## Non-goals and deferred features

No email sending, calendar integration, autonomous web research, marketplace, dynamic code generation, unrestricted agent spawning, cloud inference or autonomous learning. No browser exposure to LAN/iOS Shortcuts, automatic import of the old `/execute` route, multimodal/photo analysis, embeddings/vector database, continuous watchers or resident specialist models in this MVP.

Defer native Photos/iCloud and exported-photo handling to shared M4/M5; defer HC Audit integration until code is supplied and permissions reviewed. Also defer attachments/document ingestion, recurring tasks, dependency graphs across users, task-duration prediction, auto-rescheduling, persistent always-on scheduling, native notifications, encrypted DB implementation, and irreversible purge. A deterministic briefing and editable recommendations are enough for first use.

## Release standard and open decisions

First usable release is **C1: a manual Today planner with linked goals/projects/tasks, notes/preferences and factual briefing**, using no inference service. Release after persistence, scheduling, browser-boundary and synthetic restore tests; it must not depend on C3 model qualification.

Remaining decisions: exact Python/dependency pins at build start; A18/model workflow qualification and cancellation capability; Organizer availability and future HC Audit/file-tagger source. The supplied concept has been reviewed. Defaults in the design settle reversible UX choices. None blocks this documentation or deterministic C1 design. Performance numbers inherited from [evaluation](../MODEL_EVALUATION.md) are proposed targets, not results.
