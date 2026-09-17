# Personal local applications — planning index

Status: proposed architecture; documentation-only phase, 2026-09-17. No application implementation or benchmark results are delivered by these documents.

| Document | Purpose |
| --- | --- |
| [Shared architecture](SHARED_ARCHITECTURE.md) | Boundaries, security, data, jobs, inference and app behavior |
| [Decisions](DECISIONS.md) | Evidence, choices, assumptions, unresolved gates |
| [Model evaluation](MODEL_EVALUATION.md) | Verified inventory and proposed evaluation protocol |
| [Agent instructions](../AGENTS.md) | Scope and future contributor rules |

## Source precedence and evidence

Current explicit user instructions govern scope. Existing applicable repository instructions follow; none were found in this workspace or checked ancestor instruction files. For implementation claims, inspected code and reproducible tests outrank README/concept claims. Official dated vendor sources inform compatibility but do not substitute for testing this machine. Proposed requirements describe future behavior, not existing functionality. Record conflicts in [Decisions](DECISIONS.md), rather than silently treating a concept as implemented.

These plans were originally prepared in a multi-project workspace whose root and Organizer prototype were not Git repositories. At the user’s request, they are now maintained in the dedicated `practical_AI_Automation` Git repository. Its existing FastAPI/Shortcuts prototype is preserved; the proposed two-app architecture is not implemented. Historical workspace observations remain in [Decisions](DECISIONS.md#inspection-record).

## Requirements and acceptance map

IDs are stable; retire rather than renumber them. The criteria below are future acceptance tests, currently **not run**.

| ID | Requirement and acceptance criterion | Milestone / detail |
| --- | --- | --- |
| R-01 | Independent Python apps and small shared package; each starts without the other and has no cross-app SQL writes. | M1; [boundaries](SHARED_ARCHITECTURE.md#boundaries-and-stack) |
| R-02 | Chief of Staff supports goals, projects, tasks, deterministic briefings and approved local actions with Ollama absent. | M1; [app scope](SHARED_ARCHITECTURE.md#application-scope) |
| R-03 | Organizer scans only selected roots; rules, preview, approval, journal and conflict-safe recovery work without AI. Synthetic filesystem tests prove no overwrite, escape or duplicate application. | M2; [Organizer safety](SHARED_ARCHITECTURE.md#organizer-safety) |
| R-04 | Only installed, pinned local models; missing runtime/model yields explicit unavailable status, no download or cloud request. | M3; [provider](SHARED_ARCHITECTURE.md#provider-contract) |
| R-05 | Both apps together admit at most one inference in flight; overload, cancellation, broker crash and orphaned runtime work cannot start overlapping inference. | M3; [coordination](SHARED_ARCHITECTURE.md#inference-coordination) |
| R-06 | Typed outputs also pass semantic, evidence and identifier checks; injected content cannot authorize actions or execute code. All adversarial fixtures cause zero unauthorized mutations. | M3; [contract](SHARED_ARCHITECTURE.md#provider-contract) |
| R-07 | Durable jobs have bounded retries, cancellation and restart recovery; fault injection at every side-effect boundary proves no blind replay. | M2–M3; [jobs](SHARED_ARCHITECTURE.md#persistent-jobs) |
| R-08 | Reject hostile Host/Origin, missing CSRF/session, cross-site form/fetch, DNS rebinding and mutating GET; test both apps independently. | M1; [browser security](SHARED_ARCHITECTURE.md#localhost-security) |
| R-09 | Private state remains outside Git; synthetic-only tests and exports, redacted bounded logs, backup/restore and staged-file review pass. | M1–M3; [storage](SHARED_ARCHITECTURE.md#storage-and-privacy) |
| R-10 | A18 Pro execution, output quality and resource targets pass the recorded evaluation before any AI workflow is enabled by default. | M3; [evaluation](MODEL_EVALUATION.md) |
| R-11 | Specialists are versioned registered workflows sharing inference; no resident agents, generated executable code or self-installing tools. Registry allowlist tests reject unknown workflows/actions. | M3; [boundaries](SHARED_ARCHITECTURE.md#boundaries-and-stack) |
| R-12 | Exported photo handling preserves originals/metadata and paired assets; native Photos access uses approved APIs, never library package edits. | M4–M5; [scope](SHARED_ARCHITECTURE.md#application-scope) |

## Milestones and review

1. **M0 — this phase:** review these five Markdown files and evidence; no build authorization implied.
2. **M1 — deterministic foundation:** after explicit build instruction, use this dedicated repository, pin a tested Python/dependency set, establish private state paths and browser security; deliver manual Chief of Staff CRUD and deterministic briefing.
3. **M2 — safe Organizer:** selected-root inventory, extension rules, duplicate candidates, preview and explicitly approved operations; fault recovery and job tests before personal-folder use.
4. **M3 — optional AI:** broker/provider, synthetic A18 evaluation, validated proposals, joint-app concurrency and recovery tests. Enable only passing workflows. M1/M2 remain useful if M3 fails.
5. **M4 — exported photos:** opt-in export-folder inventory, metadata and sidecar/pair preservation; no automatic deduplication deletion.
6. **M5 — Photos/iCloud feasibility:** separate permission/API prototype and review; native integration only after compatibility and original-availability tests.

At each milestone, review requirements against evidence, add actual commands and results with versions, update decisions and document status, and inspect diffs for private data and unrelated edits. Passing tests change only the verified claims they support. Revisit budgets with measurements; never rewrite proposed targets as measured performance. Later explicit build instructions authorize implementation; downloads, migrations and personal-folder effects must stay within that later instruction's scope.
