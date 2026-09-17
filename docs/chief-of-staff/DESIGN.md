# AI Chief of Staff — MVP design

Proposed only. [PRD and acceptance IDs](PRD.md), [delivery plan](IMPLEMENTATION_PLAN.md), and [shared architecture](../SHARED_ARCHITECTURE.md) govern this design. Existing `/execute` is not reused as an authorization boundary. New app entry point stays separate from that prototype.

## Screens and navigation

Server-rendered Jinja, small local CSS, progressively enhanced forms; no SPA or chat-only interface. Navigation: Today, Goals & projects, Tasks, Notes, Briefings, Workflows, Activity, Preferences. Every page includes local timezone and explicit AI status. Default page size 50; bounded queries. Job polling every 3 seconds only while a visible job is active, backing off on errors. These are proposed settings, not measurements.

```text
TODAY — Thu 17 Sep 2026 · America/Chicago     AI unavailable
[Capture a task…] [Add manually]             [Briefing]
Overdue (2)       [ ] T-01 Draft outline       P-01  Sep 16
                 [ ] T-02 Check budget        P-01  Sep 15 [Blocked]
Due today (1)     [ ] T-03 Review notes        P-02  Today
Planned today    [ ] T-04 Gather references   No deadline
Next suggested   T-01 — overdue, high priority, unblocked
[Why this order?] [Unscheduled] [Show blocked]
```

```text
CAPTURE REVIEW                           No task saved yet
Text: Prepare launch notes next Friday for Atlas
Title: [Prepare launch notes]
Project: [? Choose Atlas P-01 / Atlas refresh P-02 / None]
Deadline: [? Sep 18 / Sep 25 / No deadline]  [Date / Time]
Priority: [Normal]   Notes: [Original wording…]
Evidence: “next Friday”, “Atlas”            [Save] [Discard]
```

```text
PROJECT Atlas → Goal G-01          [Edit] [Archive]
Status Active · Priority High · Due Oct 2 (date-only)
Tasks [Open / Done]   Dependencies   Notes [Add note]

BRIEFING · as of Sep 17 09:00 CDT   [Refresh facts]
FACTS 2 overdue: [T-01] [T-02]. 1 blocked: [T-02].
SUGGESTIONS Start [T-01]: overdue and unblocked. [Plan today]
Narrative unavailable — factual briefing is complete.

WORKFLOWS Briefing facts [Run] · Task extraction [Unavailable]
Organizer preview [Planned — integration not installed]
ACTIVITY J-12 Waiting for model · elapsed 5s [Cancel]
J-11 Failed: invalid project ID [Details] [Edit input]
```

Forms support keyboard navigation, inline validation, focus at errors and status text not conveyed only through color. Details show references and provenance. Notes are plain text in MVP. Preferences show explicit saved values and change history, not an inferred personality profile. Workflow detail displays scope and authorization before running. History distinguishes requested, validated, committed, rejected and externally uncertain outcomes.

## Schema and migrations

App-owned SQLite at the shared private state path. UUID primary keys, UTC `created_at`/`updated_at` timestamps, optimistic integer `version`, and nullable `deleted_at` on editable records. Titles bounded at 200 characters; note/body text at 16 KiB initially. Apply foreign keys and CHECK/unique constraints as well as domain validation. Use parameterized SQL. No cross-app joins.

| Table | Principal fields / constraints |
| --- | --- |
| goals | title, description, status (`active/paused/completed/archived`), priority (`low/normal/high/urgent`), deadline fields |
| projects | nullable goal_id FK, title, description, same status/priority/deadline fields; one goal per project |
| tasks | nullable project_id FK, title, description, status (`todo/in_progress/done/cancelled`), priority, deadline fields, planned_on DATE + planned_timezone, completed_at, manual_order; goal inherited through project |
| task_dependencies | task_id, prerequisite_id; composite unique key, distinct IDs; domain rejects cycles transactionally, including cross-project edges |
| notes | title, body; optional exactly one goal_id/project_id/task_id FK or no owner; note links cannot point at deleted records |
| preferences | unique allowlisted key, typed JSON value, approved_at, version; default values are distinguishable from saved preferences |
| action_history | event ID, actor (`user/system/workflow`), action, entity refs, request/job ID, before/after field diff, authorization ref, outcome, UTC time; private app history, not diagnostic logs |
| schema_migrations | ordered version, checksum, applied_at; unknown/newer schema blocks writes |
| jobs | shared lifecycle fields plus workflow version, progress stage, bounded units done/total, result ref, broker ticket, source versions, error code, retry_of |
| proposals | typed payload, evidence refs, source/input versions, unresolved fields, expiry, state, originating job; never authoritative task data |
| briefings | as_of UTC, timezone, query scope, immutable fact snapshot/counts, selected record versions, optional validated narrative/suggestions |
| authorization_grants | workflow/version, bounded project/root IDs, allowed read actions, schedule/timezone, daily cap, expiry, revoked_at; no arbitrary permission JSON |
| request_receipts | operation + idempotency key, input hash, result ref, committed_at; insert with domain write in same transaction |
| integration_requests | adapter/version, local job, stable remote key/ID, input hash, preview ID/version/expiry and last known remote state; no filesystem journal owned here |

Manual task goal linkage goes through a project; a task can be unassigned but cannot silently acquire a second conflicting goal. Blocked is computed, not a stored task status: an unfinished prerequisite blocks; a cancelled prerequisite stays unsatisfied until the user removes the dependency. Reject starting/completing a blocked task with an inline explanation and dependency-edit option; never auto-complete prerequisites. Reopening a prerequisite leaves previously completed dependents completed with a warning, but blocks future unfinished dependents.

Archive excludes goals/projects from default active views but does not silently archive children; show remaining work and preserve task deadlines in Today with an archived-parent badge. Delete is soft-delete, does not cascade, and requires explicit detach/reassign for live references (including notes and dependencies). Restore revalidates references. Deletes/edits are atomic with action history. Undo is a new validated versioned operation, never a rollback over later edits. Permanent purge is out of scope.

Preferences allow timezone, week start, due-soon horizon (default 7 days), preferred project order, briefing local time and display density. Suggestions to change preferences are drafts only. Runtime paths/model pins/security settings live in validated local config, not free-form preference keys. Authorization grants are separate from preferences.

Migration sequence proposed: 001 core entities/dependencies/preferences/history/receipts; 002 briefing snapshots; 003 jobs/registry grants; 004 proposals/inference references; 005 optional integration requests. Each migration has a checksum, backup and old-fixture upgrade test, runs transactionally where supported, and checks integrity/foreign keys before admitting writes. Do not promise destructive down-migrations; rollback restores a verified pre-migration snapshot using the matching app version. No migration runs in this phase.

## Time and Today semantics

Deadline discriminated union on goals/projects/tasks: `none`, `date` with `due_date` + IANA `due_timezone`, or `instant` with `due_at_utc` + original IANA timezone + entered local datetime/offset. CHECKs forbid mixed variants. Reject naive timestamps. Date-only means due through that local date, overdue when the next local date begins; never synthesize 23:59:59 UTC. Instant becomes overdue when now ≥ stored instant. DST gaps require choosing a valid time; DST folds require selecting an offset. Code converts/validates, never the model.

Changing display timezone changes presentation, not stored deadline semantics. Date-only deadlines retain their original zone and date unless explicitly edited; when different from display zone show a badge. Today compares date deadlines in their deadline zone; timestamp deadlines fall within today's display-zone day. Planned day is a separate date/zone, never a promised deadline. Use injected `now` and timezone data in tests; no device-clock calls scattered through templates.

Today has separate membership facets: overdue, due today, planned today, blocked and unscheduled. Display each task once in primary groups (overdue before due today before planned); badges preserve other facets. Completed/cancelled/deleted tasks excluded. Counts explicitly identify task counts; goal/project deadlines appear separately. Actionable ranking: manually pinned order first, then overdue, due today, due-soon, remaining; within bucket priority, earliest effective deadline, creation time, stable ID. Filter blocked work out of actionable next steps; still show it in overdue facts. Reasons are generated from the actual sorting keys, not invented productivity scores. User choices take precedence over suggestions.

## API examples

Proposed endpoints, not executable commands. Session/Host/Origin/CSRF protection from [shared security](../SHARED_ARCHITECTURE.md#localhost-security) applies to HTML forms and JSON routes. Examples omit secrets; browser mutations require valid session, exact Origin, `X-CSRF-Token` (or equivalent form token), and `Idempotency-Key`. Input rejects extra fields. Version conflicts return 409; validation 422; unavailable workflow 503; queue full 429. GET never creates a job or changes data.

```http
POST /api/v1/tasks
Idempotency-Key: capture-42
Content-Type: application/json

{"title":"Draft outline","project_id":"P-01","priority":"high",
 "deadline":{"kind":"date","date":"2026-09-18","timezone":"America/Chicago"}}

201 {"id":"T-01","version":1,"status":"todo"}
```

IDs in examples are readable aliases; real schemas use UUIDs. Repeating the same key and payload returns the existing result; same key with different payload returns 409. PATCH `/api/v1/tasks/T-01` includes expected_version and validated field changes; DELETE soft-deletes with expected_version. Parallel CRUD routes for goals/projects/notes/preferences use the same rules. GET `/api/v1/today?date=2026-09-17` computes facts in code. Authenticated user action `POST /api/v1/briefings` creates a snapshot/job; GET by ID reads it.

```http
POST /api/v1/workflow-runs
Idempotency-Key: extract-42

{"workflow_id":"task.capture.propose","version":1,
 "input":{"text":"Prepare launch notes next Friday for Atlas",
          "reference_time":"2026-09-17T09:00:00-05:00"}}

202 {"job_id":"J-42","state":"queued","status_url":"/api/v1/jobs/J-42"}
```

Server validates reference_time as the capture-session time, rather than trusting model output. Proposal result: `title`, supplied project candidate IDs, raw deadline phrase, evidence spans, `unresolved_fields`, and typed abstention. Numeric candidate dates come from the application date resolver. POST `/api/v1/proposals/PR-42/apply` carries proposal version, edited final task fields and resolved choices; domain code revalidates references/approval/source freshness and atomically saves task/history/receipt. Default proposal expiry 24 hours; refreshing invalidates old approval.

GET `/api/v1/jobs/J-42` returns state, stage, units if known, elapsed time, safe error code and permitted next actions; do not fabricate percent completion for inference. POST `.../cancel` records cancellation. POST `.../retry` creates a linked attempt only when the policy permits; invalid-output failures offer edit/new proposal, not blind replay. No generic `/execute` endpoint accepts arbitrary tool names.

## Registry, routing and context

Registry entries are code-defined, versioned and tested: ID, implementation reference (fixed import, never model supplied), input/result schema versions, permission set, maximum duration, input bounds, retry class, cancellation behavior, AI requirement and availability reason. Discoverable plans are shown separately from invokable entries. No such Chief workflows are implemented in the repository today.

| Planned implemented entry | Input → result | Permission / proposed timeout |
| --- | --- | --- |
| briefing.facts v1 | selected scope + as_of → immutable facts/links | app read + own briefing record write; 5 s |
| task.capture.propose v1 | text + reference time + candidate IDs → TaskProposal | selected-input inference, proposal store only; queue 120 s + generation 60 s |
| briefing.narrative v1 | validated bounded fact snapshot → separate narrative/suggestions | selected-fact inference, briefing draft only; same AI bounds |
| organizer.preview v1 (conditional) | approved root IDs + rule profile version → remote preview reference | selected-root metadata read; 3 s dispatch, 120 s preview job then resumable cursor |

CRUD goes directly through domain services, not an AI workflow. HC Audit and file tagger have no registry entry until actual implementations are reviewed, adapted and tested. Organizer appears as planned/unavailable until versioned capability negotiation succeeds. Its preview budget can yield an explicitly incomplete result; approval must never imply the rest of an unscanned tree.

GET `/api/v1/workflows` lists invokable entries with their schemas, permissions and availability; planned capabilities are a separate display list. Match tasks to workflows initially with deterministic declared capability labels; show the matching reason and exact scope. Run follows the authorization table; Not now dismisses the suggestion, and Defer stores a private non-executable suggestion note. Neither accepting a suggestion nor a model response can register a new workflow, install code or create an agent instance. An unavailable capability remains a manual task. There is no registry mutation or inter-agent messaging API in MVP.

SQL selection is deterministic and parameterized: task capture receives at most 5 project candidates matching user-selected scope/title terms; ties remain ambiguous, not guessed. Briefings compute full-scope counts in one read transaction, then select at most 12 supporting tasks by Today order and up to 5 projects. Mark omitted records/counts. Include only relevant approved preferences (up to 8 keys) and up to 2 explicitly selected note excerpts; no automatic whole-notebook or folder reading. Always retain source IDs, versions, provenance and as_of. The stricter shared 1,200-source-token/2,048-total-context budget wins over record caps: reduce selection transparently or use deterministic output; never imply truncated detail is exhaustive. Source text cannot override instructions or permissions.

Facts pane always comes from code. Model narrative is optional, bounded and validated for allowed IDs/evidence; use structured fact references with application-rendered numbers/date labels rather than accepting model arithmetic. Unsupported assertions cause rejection and deterministic fallback. Suggestions cite reasons/evidence separately, never claim new commitments exist. A user must save any suggested new task or change. Saving changes rechecks live versions, even if the briefing was valid when generated.

Model routing: deterministic workflow → no model; eligible AI workflow → one configured, digest-pinned profile through the shared broker; ineligible/unavailable → manual/factual path. No automatic larger-model escalation. Existing Llama and candidate Granite/Qwen profiles retain [evaluation](../MODEL_EVALUATION.md) status; none is qualified yet. Keep one loaded model, short context/output, bounded queues/timeouts, no per-specialist models. No A18 performance claim follows from catalog or M-series support.

## Action authorization

| Action | Authority and UX |
| --- | --- |
| Read/search; direct add/edit/complete/plan; explicit preference Save | Immediate authenticated user gesture, domain validation, CSRF for writes; inline feedback/Undo, no extra modal |
| Soft-delete unreferenced record; cancel queued job | Immediate explicit gesture; Undo for record, cancellation feedback for job |
| Read-only scheduled briefing | Saved revocable grant bound to workflow/version/project scope, expiry and max one daily run by default; no writes except its own briefing/job history |
| AI proposal or batch update; referenced-record detach/reassign | Editable preview and one Save/Apply; exact targets, expected versions, diff and unresolved fields required |
| Organizer metadata preview | One scoped request after selecting/authorizing root IDs; no file mutations; no blanket filesystem grant |
| File moves/copies | Unavailable from Chief MVP; open exact Organizer preview, authorize there; Organizer owns validation and execution |
| Restore | Preview backup identity/schema/record counts and replacement scope, explicit Replace; pause workers and invalidate grants/jobs as below |
| Email/calendar/web/tool install/generated code/unknown workflow | Denied/out of scope; no “approve anyway” override |

Scope-changing edits revoke grants and invalidate previews. Cancellation/expiry/revocation wins before dispatch and before each effect. Grant authorization never relies on model confidence. Permission checks run server-side at admission and again before commitment; models never set actor/approval fields. Audit records use request IDs and committed changes, not chain-of-thought.

## Jobs and restart recovery

Follow [shared lifecycle](../SHARED_ARCHITECTURE.md#persistent-jobs): `queued → running → succeeded`, with `waiting_inference`, `awaiting_approval`, `retry_wait`, `cancel_requested`, `cancelled`, `failed`, `needs_review`. Proposal-producing workflows may wait for review; only Apply marks the domain action committed. Declining a proposal cancels it without a task write. Expiry produces needs_review and requires a fresh proposal/version. A facts-only job can finish without approval.

Progress stores durable stages (selecting facts, queued for model, generating, validating, ready for review), optional actual counts and heartbeat. UI safe error details distinguish unavailable, invalid output, version conflict, denied scope, expired preview and uncertain completion; offer the appropriate recovery. Request/job IDs enable diagnosis without logging personal text. Action history in private SQLite retains meaningful diffs/provenance; operational logs remain redacted and bounded as shared policy requires.

Read-only transient failures: at most 3 total attempts, delays 5/30 s within the absolute job deadline. No retry of invalid outputs or uncertain mutations. One app worker, at most 100 pending domain jobs; AI admission also observes global broker limits (8 queued, max 4 per app), never hides overflow in another waiting queue. A visible retry button does not bypass those caps. Terminal-job retry is a new linked job after safety checks; same-operation request keys prevent duplicate effects.

On restart, transactionally reconcile receipts, proposals and remote IDs before processing queued work. If a task save committed before the browser lost its response, receipt returns the existing task. Safe interrupted reads may restart; inference jobs query the old broker ticket, never start a new generation to “resume.” Uncertain runtime execution activates the shared global barrier; show “waiting for runtime recovery,” not a false failure followed by automatic retry. Cancel requests persist. No job resumes with expired/revoked permission. After sleep, scheduled briefings coalesce into one current run.

## Backup and restore

Use SQLite online backup into a user-selected private directory; bundle schema/app version, checksum and snapshot time, not source code, model weights, session secrets or absolute personal-path inventories. Include domain data/history/preferences and job references consistently; never raw-copy a live WAL database. A backup is sensitive and is not made private by being local. Initial backup is manual; no cloud/sync upload.

Restore validates checksum, schema compatibility, integrity and foreign keys in a temporary private DB; display record counts/time and replacement scope. Pause admission/workers, preserve a rollback snapshot, switch the Chief DB only after validation, then reopen with a new data-generation ID and fresh sessions. Do not roll back Organizer DB or filesystem based on a Chief backup. All restored active jobs/proposals become needs_review, all grants disabled pending user renewal; old idempotency/integration references are retained for reconciliation, never dispatched automatically. Show old briefings as snapshots. Test malformed backup, newer schema, interrupted restore and rollback using synthetic data. Physical erasure from SSD/backups is not promised.

## Organizer integration contract

Conditional C4 integration over a versioned typed local Unix-socket interface, not direct DB access or HTTP calls from the browser. Chief requests metadata preview only. Organizer owns approved roots, rules, inventory, canonical preview/approval/execution state and filesystem journal. Socket permissions follow shared private-path rules. Unsupported version/missing service reports unavailable and leaves task management working.

`capabilities` returns adapter version, supported `preview/status/cancel`, root/profile IDs available to this user, and whether previews can be incomplete. No filesystem paths are accepted from a model. `request_preview` takes request UUID, Chief data-generation ID, root IDs, rule-profile version, scope hash and `mode: preview`; returns stable job ID. Same key/hash returns same job; mismatched hash is a conflict. Status returns preview ID/version, manifest hash, expiry, scanned/remaining counts, warnings, read scope and a validated local review link. UI derives the allowed local link from configured origin/ID, not arbitrary returned URLs. Proposed preview expiry 24 hours; any file/rule/root change invalidates execution readiness.

Chief persists the outbound key before dispatch, then records the remote receipt. If acknowledgement is lost, query by the same key; do not invent a new request. Organizer transactionally deduplicates admission. Chief cancellation requests stop scanning at safe checkpoints and never assert rollback. A second click on Request preview reuses the active matching request; an explicit Refresh creates a new preview and supersedes the old one.

Chief has **no execute permission** in MVP. The Organizer review page alone takes explicit approval bound to preview ID/version, manifest hash, user scope and operation ID. Repeated approval/delivery must return the same operation/status. A crash after file movement but before DB completion is reconciled from the Organizer journal and file identities, never replayed from the Chief job. An expired/missing historical receipt causes needs_review, not assumed permission to redo a move. Chief action history records the remote operation outcome when available without claiming an atomic transaction across apps.

## Worked examples

1. **Ambiguous capture (CS-03):** at 2026-09-17 09:00 America/Chicago, “Prepare launch notes next Friday for Atlas.” Two Atlas projects match; “next Friday” may mean Sep 18 or Sep 25. Proposal shows both project candidates and unresolved date. User picks P-01 and Sep 25 (date-only), or explicitly chooses no project/deadline. Save validates and creates one task; original phrase remains provenance, no time-of-day invented.
2. **Overdue briefing (CS-04/05):** at the same time, T-01 due Sep 16 is high/unblocked; T-02 due Sep 15 depends on unfinished T-03; T-04 due Sep 14 is done. Code reports two overdue, one blocked, links T-01/T-02/P-01. Facts do not include completed T-04. Suggestion: “Start T-01: overdue, high priority, unblocked.” No claim of a scheduled meeting or user commitment. AI wording cannot change counts.
3. **Restart (CS-07):** J-42 has broker ticket B-42 when Chief exits. Startup queries B-42. A finished result becomes a reviewable proposal once; uncertain generation waits behind the broker barrier. If task creation had committed before response loss, `capture-42` returns its existing receipt instead of inserting a second task. Nothing is re-approved implicitly.
4. **Invalid model action (CS-06/09):** output includes `action: shell.execute`, an unknown P-999 or `approved: true`. Extra/unknown fields, IDs or actions fail validation; record safe error `invalid_proposal`, perform zero domain/file mutations, offer manual edit/new request. High confidence does not change the result.
5. **Ollama unavailable (CS-10):** request returns unavailable within health deadline; retain capture text, show editable manual fields and factual briefing. No repeated background loads, silent model switch, pull or cloud fallback; other jobs/CRUD remain usable.
6. **Organizer retry (CS-12):** preview key O-42 dispatch succeeds but acknowledgement is lost. Restart repeats O-42 and retrieves the same preview, with no moves performed. User opens Organizer and approves operation OP-42 there. After lost execution response, querying/repeating OP-42 returns its journal-backed result or needs_review; Chief cannot execute it or generate a replacement operation automatically.
