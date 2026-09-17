# AI Chief of Staff — implementation plan

Planning only; no task below authorizes code, installations, model downloads, services, personal-file changes, commits, pushes or external actions in the current phase. [PRD](PRD.md) owns requirements; [design](DESIGN.md) owns contracts. Likely paths below do not yet exist. The March 27 concept's checked-off milestones and week estimates are not the implementation baseline.

## Milestones

| Milestone | Deliverable / shared alignment | Dependencies and release boundary |
| --- | --- | --- |
| C1 — first usable planner | Deterministic manual CRUD, Today, notes/preferences, factual briefing, private history and restore; shared M1 | Explicit build instruction, then PRs 1–5. No Ollama, broker or Organizer required. |
| C2 — workflow operations | Fixed registry, durable jobs, progress/cancel/retry, scoped briefing grants and restart recovery | C1, PRs 6–7. Deterministic workflows only; does not claim AI qualification. |
| C3 — optional AI assistance | Plain-language proposals and grounded narrative/recommendations through shared broker; shared M3 | C2, PRs 8–10, A18/model evaluation and shared concurrency gate. Deterministic app stays releasable if AI fails. |
| C4 — Organizer preview | Read-only scoped integration and remote job reconciliation | C2, shared Organizer M2 service/contract available, PR 11. Can proceed independently of C3; file execution remains in Organizer. |

C1 is deliberately smaller than the full MVP. Full Chief MVP completes C2 and qualifying C3 workflows; C4 is conditional on Organizer readiness. Unknown HC Audit/file-tagger code cannot be placed on the critical path. No elapsed-week promise is made; each PR has one reviewable outcome and tests before the next dependent change.

## Ordered PR-sized work

### PR 1 — private app boundary and build baseline

- Covers CS-09/10/11 foundations, R-01/R-08/R-09. Inspect any new instructions, select native Python/dependency pins and establish exact build/test commands. Keep existing `api/main.py` and handler unchanged; do not mount `/execute` into Chief.
- Likely files: `pyproject.toml`, dependency lock, `.gitignore`, `apps/chief_of_staff/__main__.py`, `web.py`, `config.py`, `shared/web_security.py`, `tests/chief/test_security.py`, synthetic fixtures; update contributor commands once verified.
- Implement loopback-only binding, exact Host/Origin, pairing/session/CSRF, local assets, private config/state directories and empty navigation shell. No service launches automatically on import.
- Tests: hostile/missing/null Origin, incorrect Host/port, cross-site form/fetch, missing session/CSRF, mutating GET, safe template escaping; config rejects remote endpoints/private state in source.
- Demo: explicitly launch later, pair once, view empty Today; hostile mutation returns denial. Done when the shell is protected, commands documented and private files excluded without changing unrelated code.

### PR 2 — core persistence and linked manual CRUD

- Depends PR 1; CS-01/08/09/11. Add migration 001 and transactional repository/domain services with receipts, version checks and action history.
- Likely files: `apps/chief_of_staff/{domain.py,repository.py,schemas.py}`, `migrations/001_core.sql`, `templates/{goals,projects,tasks,notes,preferences}.html`, `tests/chief/{test_crud,test_migrations,test_history}.py`.
- Add goal/project/task/note/preferences forms, link selection, direct Save and soft-delete/Undo. Restrict referenced deletes, prevent cascading child loss; preferences typed and explicitly saved. No AI endpoint needed.
- Tests: all entity CRUD and restart persistence, invalid FK/extra fields, optimistic conflict, duplicate same-key save, changed-payload same-key rejection, delete/restore linkage and one audit event per committed change.
- Demo: create goal → project → task plus note, change preference, reload, soft-delete and restore a standalone note. Done when actions persist once with no redundant confirmation dialogs.

### PR 3 — time, dependencies and Today

- Depends PR 2; CS-02/05. Add deadline discriminated union, code-owned clock/date resolution, dependency validation and deterministic ranking. Schema fields may be reserved in PR 2; enforce them here before exposing scheduling.
- Likely files: `domain/scheduling.py`, `domain/dependencies.py` (split the initial domain module if helpful), `services/today.py`, `templates/today.html`, `tests/chief/{test_time,test_dependencies,test_today}.py`.
- Tests: date-only versus timestamp deadlines, DST gap/fold, timezone-change stability, priority tie ordering, membership/count deduplication, cancelled prerequisites, self/cyclic dependencies, completed dependent reopening behavior.
- Demo: synthetic Sep 17 clock shows two overdue tasks, one blocked, next actionable T-01 and visible reasons. Complete/reschedule without another modal. Done when manual Today is usable without AI and computed counts match fixtures.

### PR 4 — deterministic briefings and capture form

- Depends PR 3; CS-03 manual path, CS-04/05. Build SQL fact selector and deterministic briefing renderer with as-of time, links, counts, omissions and clear suggestions section. Start with synchronous bounded generation; PR 6 wraps the same service in jobs.
- Likely files: `services/{briefings,capture}.py`, `templates/{briefing,capture}.html`, `tests/chief/{test_briefings,test_capture}.py`, migration 002 for briefing snapshots.
- Tests: completed/cancelled/deleted exclusions, blocked overdue counts, timezone fixtures, valid supporting links, stale snapshot badges; manual capture has editable fields and preserves typed source text without assigning ambiguous dates.
- Demo: open factual overdue briefing, follow T-01 to P-01/G-01, save a manually resolved ambiguous capture. Done when no model call is needed and facts/suggestions are visibly separate.

### PR 5 — local backup/restore and C1 release checks

- Depends PRs 1–4; CS-11 and complete C1 coverage. Add private snapshot/restore UI or trusted local command, integrity checks, pre-replacement preview, rollback and schema compatibility checks.
- Likely files: `services/backup.py`, `tests/chief/test_backup.py`, local operator documentation and updated `AGENTS.md` commands.
- Tests: online SQLite snapshot, complete synthetic restore, checksum/corruption/newer-schema failures, interrupted replacement/rollback, no secret/model inclusion; restore disables future scheduled actions by design.
- Demo: create sample work, back up, edit it, restore with explicit scope and verify facts/history. Then use app with no Ollama/broker available. C1 done after this small end-to-end scenario passes, docs match behavior and non-AI UI/resource targets are measured and labeled honestly.

### PR 6 — registry and durable deterministic jobs

- Depends C1; CS-06/07. Code-defined versioned workflow registry; only `briefing.facts` invokable initially. Job table, one worker, bounded queue, status/results/history and cancellation checkpoints. Workflow runs may save their own results but do not edit task commitments.
- Likely files: `shared/{workflow_contracts,jobs}.py`, `apps/chief_of_staff/{workflows,jobs}.py`, migration 003, `templates/{workflows,jobs,activity}.html`, `tests/chief/test_jobs.py`.
- Tests: unknown/unimplemented workflow and invalid schema rejection before admission; queue limits, duplicate requests, actual progress stages, cancellation semantics, bounded retry, fault injection after DB commit before HTTP response. No fake percentage for unknown work.
- Demo: submit factual briefing, inspect stage/result, cancel queued job and trigger synthetic transient failure. Done when state transitions are durable and API errors expose only safe details.

### PR 7 — restart reconciliation and optional scheduled authorization

- Depends PR 6; CS-07/08/09/11. Add revoked/expired scope checks, one daily briefing grant while app is open, sleep coalescing and restart recovery. Extend restore to quarantine active jobs/proposals and disable grants.
- Likely files: `services/{authorization,scheduler,recovery}.py`, `templates/preferences.html`, `tests/chief/{test_recovery,test_authorization,test_scheduler}.py`.
- Tests: interrupted read restart, receipt deduplication, expiry/revocation between admission and execution, scope changes, DST schedule transitions, missed-run coalescing, backup restore causes zero automatic dispatch.
- Demo: opt into one project-scoped briefing schedule, restart/simulate sleep, show one current run, revoke and prove no new run. C2 done when all permissions and failure paths have explicit UI and deterministic tests.

### PR 8 — shared inference broker and A18 qualification harness

- Depends C2; CS-10, R-04/R-05/R-10; coordinate with shared M3 rather than create a second broker implementation.
- Likely files: `shared/inference/{contracts,broker,ollama_provider}.py`, broker migration/config, `tests/shared/test_inference_coordination.py`, synthetic benchmark fixtures/report and documented evaluation commands.
- Implement private socket singleton, bounded global queue, pinned local profiles, runtime-uncertainty barrier, deadlines and cancellation capability handling. No tool installation/cloud fallback; no runtime auto-start button.
- Tests with fake provider first: two independent app clients never overlap inference; queue overflow/fairness, dispatch crash, uncertain cancellation, late result, missing model/digest drift, redirect/proxy rejection. Then separately authorized real-runtime evaluation following [model plan](../MODEL_EVALUATION.md) on this A18; record exact versions/quantization/context and memory/cold/warm results.
- Demo: both synthetic clients share the broker; stop provider and keep Today usable. Done only when the shared limit is proven under fault injection. Model workflow enablement additionally requires measured acceptance gates; if none pass, ship deterministic behavior and label AI unavailable.

### PR 9 — task proposal and validated Apply

- Depends PR 8 qualification for extraction; CS-03/06/09/10. Add migration 004, bounded project-context retrieval, typed extraction/abstention, ambiguous date resolution UI, single Save into ordinary domain service.
- Likely files: `workflows/task_capture.py`, `services/{context,proposals}.py`, `templates/capture.html`, `tests/chief/test_task_proposals.py`.
- Tests: both Atlas projects and “next Friday” surfaced, invented ID/approval/action/evidence rejected, expired/stale proposal, double Apply inserts once, unavailable runtime preserves text/manual form, input/output token/byte limits.
- Demo: resolve P-01/Sep 25 explicitly, save once, simulate response loss and retry, inspect the same task. Done when plain-language capture has no privilege beyond the manually validated form.

### PR 10 — grounded narrative and workflow suggestions

- Depends PRs 8–9 and narrative qualification; CS-04/05/06. Render code-owned fact references, optional bounded narrative and separate suggestions. Registry matching suggests only installed/qualified capabilities with scope/reason; unsupported requests remain manual tasks.
- Likely files: `workflows/briefing_narrative.py`, `services/workflow_suggestions.py`, `templates/{briefing,workflows}.html`, `tests/chief/{test_grounding,test_workflow_suggestions}.py`.
- Tests: every referenced ID/evidence valid; unsupported claims rejected, blocked task not recommended as actionable, no silent deadline/preference updates; unavailable narrative leaves factual briefing intact; no generic agent spawn route.
- Demo: factual briefing with optional grounded next step, invalid model action rejection, unavailable Ollama fallback. C3 done after relevant synthetic holdout gates and combined-app resource targets pass; do not present unmeasured numbers as results.

### PR 11 — conditional Organizer preview adapter

- Depends C2 and separately implemented Organizer M2 capability/recovery contract; CS-12. No dependency on AI and no HC Audit assumption.
- Likely files: `shared/organizer_contracts.py`, `apps/chief_of_staff/integrations/organizer.py`, migration 005, `templates/organizer_preview.html`, `tests/integration/test_organizer_preview.py`.
- Implement capability negotiation, root/profile selection, bounded read-scope authorization, persistent outbound key, preview/status/cancel and validated local review link. Chief receives no move/copy execution permission.
- Tests: unavailable/version mismatch, root escape or model-supplied path, identical key returns same preview, lost acknowledgement/restart, incomplete/stale preview, cancellation, restore does not resend. Separate Organizer contract test proves repeated approved OP-42 never moves twice, including crash after disk effect before DB commit.
- Demo: request O-42, lose response, reconnect to same preview, open Organizer review; explicitly approve once there using synthetic roots, repeat delivery and verify exactly one filesystem effect. Done when both apps' recovery evidence supports the contract; otherwise leave the UI marked planned/unavailable.

## Definition of done

- Every delivered CS requirement has the relevant acceptance test and demonstrated user flow; update [PRD](PRD.md) status only with evidence. Keep unimplemented registry entries unavailable.
- Test changed behavior with synthetic fixtures, temporary roots and injected clock/provider. No personal documents, health/audit data, Downloads or Photos libraries in tests or benchmark output.
- Verify security/domain validation and state-recovery boundaries, not merely mock happy paths. Run targeted tests and required repository checks; record actual commands/results once they exist.
- Keep migrations, backup/restore, data ownership and private exclusions aligned. Read-only database facts remain functional with broker/Ollama absent. UI does not require a model or background agent to save a task.
- Record prompt/schema/workflow/runtime/digest changes and rerun affected qualification. Keep proposed targets distinct from measurements; accept no unverified A18 compatibility claim.
- Review Markdown links, requirement mapping, user-facing wording and diff scope; update shared decisions when architecture changes. No unrelated code changes or external publication without task authorization.

## First release and decisions remaining

Deliver **C1 after PRs 1–5**, a small but usable local planner: linked goals/projects/tasks, notes and explicit preferences, accurate Today, deterministic next-step reasons and factual briefings, plus private persistence and tested backup/restore. No specialist coordination UI should imply integrations already exist. This is a realistic first vertical slice, not the concept's claimed completed foundation.

Build-time decisions: exact Python/dependency pins, backup destination chosen by the user, and confirmation of timezone defaults (America/Chicago unless changed). AI gates: measured model suitability on A18, runtime termination evidence and exclusive runtime ownership. Integration gates: Organizer implementation readiness and actual source/tests for HC Audit or a fuller file tagger. These gates do not block C1; HC Audit, document research and native Photos are not prerequisites.
