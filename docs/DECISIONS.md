# Decisions and evidence

Proposed architecture, inspected 2026-09-17. Requirements and future gates: [index](README.md). No benchmark, service launch, dependency install, model download or application change was performed.

## Inspection record

| Area | Verified observation | Implication |
| --- | --- | --- |
| Workspace | Root README is a minimal Python hello-world description; root and Organizer prototype have no Git repository. No applicable AGENTS.md was found in the workspace or checked ancestor locations. | Create requested planning files at root; future dedicated app repository placement remains reversible. |
| Organizer code | `app.py` scans the current directory and prints ten classifications. `core/scanner.py` eagerly recursively lists files; `rules.py` maps five extensions; `organizer.py` wraps shutil moves/copies; `tags.py` creates SQLite path/tag rows. | Useful examples, not a production architecture. Scanner lacks bounds/selection policy; mutations lack approval, collision and recovery protections. |
| Organizer dependencies/tests | `requirements.txt` lists unpinned watchdog, ollama and pyside6. No test files or project packaging manifest found there. Imports in inspected code use the standard library; no actual UI or model call found. | Listed dependencies do not prove integration or installation. Build a thin Python foundation; do not retain unnecessary dependencies by default. |
| Organizer reference docs | README claims duplicate detection and OneDrive/Google Drive/iCloud local-folder support; architecture is a UI/core/storage sketch; roadmap describes future AI tagging and natural-language commands. | Duplicate detection and cloud semantics are not implemented by inspected code. Preserve reference files as concept material. |
| Chief of Staff | No corresponding implementation or reference document found in workspace file inventory. | User's supplied concept is the requirements source; design this app fresh. |
| Sibling stack | Inspected Fitness pyproject, web entry and web tests: FastAPI/Jinja/Pydantic/SQLite via SQLAlchemy, pytest/httpx; Guardia also declares FastAPI/Pydantic. | Reuse familiar stack conventions, not unrelated domain code. Fitness origin middleware accepts missing Origin and is not sufficient for the new security requirement unchanged. Tests inspected, not executed. |
| Git status | Games clean. Fitness, Fitness_public, Retro-Games and Guardia/Guardia have pre-existing modified/untracked files. | Leave all sibling work intact; no staging, commits, pushes or issues. |
| Host | Local system reports MacBook Neo / Mac17,5, A18 Pro, 8 GB, macOS 27.0 build 26A428. Hardware identifiers containing private serial/UUID data are deliberately omitted. | Hardware matches target; OS/runtime/model execution still needs its own validation. |
| Ollama | Read-only CLI/API queries reached an already-running local service after sandbox access approval. Client/server 0.34.0; only llama3.2:latest listed. | Metadata is verified; no inference was run and no model residency/performance claim follows. [Inventory](MODEL_EVALUATION.md#verified-inventory). |

A first instruction-file search was too broad and traversed parent-directory names before the search was narrowed to workspace and explicit ancestor files. No personal file contents from that search were used in the design. Future inspection should stay within project scope.

## Decision register

| ID / requirements | Decision and rationale | Alternatives / revisit trigger |
| --- | --- | --- |
| D-01 / R-01 | One dedicated future repository, independent apps, small shared Python package. The user selected `practical_AI_Automation`; its dedicated local checkout avoids disturbing unrelated projects. | Separate repositories would duplicate contracts/releases; revisit only for independent distribution or access control. Do not merge the existing sibling repositories. |
| D-02 / R-01, R-02 | FastAPI/Jinja + SQLite, standard-library SQL migrations initially; one native Python environment for the future repository. Small server-rendered UI avoids Node build/SPA state duplication. | PySide6 adds packaging/resource cost; Flask is viable but FastAPI fits typed contracts and the nearby stack. SQLAlchemy only if real query/migration complexity warrants it. No Docker, Redis, vector DB or agent framework requirement exists. |
| D-03 / R-04, R-05 | One broker over a private Unix socket and one local runtime; global admission/recovery barrier. Both apps always use it. | Two process locks cannot enforce a common limit. A cross-process lock alone does not solve bounded admission or orphaned inference. Broker is a small single-host process, not distributed infrastructure. |
| D-04 / R-06, R-11 | Registered bounded workflows produce typed proposals; code owns authority and execution. | Autonomous agents, generated scripts and self-installing tools rejected. Confidence cannot authorize writes. |
| D-05 / R-02, R-03 | Rules/manual features ship before AI; every AI workflow independently qualifies. | A chat-first interface would make basic operation depend on model quality and availability. |
| D-06 / R-03, R-07 | Preview then explicit approval, per-operation journal and revalidation; same-volume local moves first. | Immediate bulk moves and cross-volume deletion introduce avoidable recovery risk. Deterministic scheduled execution can be considered later with an explicit preapproved policy. |
| D-07 / R-08, R-09 | Strict browser boundary, session and CSRF; private state outside Git, synthetic fixtures only. | Loopback alone and CORS alone do not authorize mutations. Local inference does not make logs or backups private. |
| D-08 / R-10 | No default candidate selected until A18-specific runtime and evaluation gates pass. Start evaluation with the installed Llama baseline, then separately authorized candidates. | Choosing by parameter count, advertised context or downloaded size cannot establish quality or memory fit. No M-series benchmark is an A18 result. |
| D-09 / R-12 | Exported-photo copies before native Photos/iCloud integration. | Direct library filesystem edits rejected. Native bridge is a separately gated extension; visual recognition/embeddings deferred. |

## Compatibility evidence

Apple lists A18 Pro and 8 GB unified memory for this machine, consistent with the local inventory. [Apple specifications](https://support.apple.com/en-nz/126322).

Ollama's macOS requirements currently specify macOS 14+ and Apple M-series CPU/GPU or x86 CPU. They do **not explicitly list A18 Pro**. The installed server responding to metadata proves it runs, not that every candidate executes with acceleration. Official support language therefore leaves this hardware/model combination unresolved. [Ollama macOS requirements](https://docs.ollama.com/macos).

An upstream llama.cpp issue records an A18-specific installer detection failure; it is not proof about installed Ollama 0.34.0, but reinforces separating installer support from engine/model execution. [llama.cpp issue 23928](https://github.com/ggml-org/llama.cpp/issues/23928). M3 must record actual backend, OS, exact runtime build, model digest, successful bounded generation and measured resources. Do not infer Neural Engine use from Apple hardware specifications. CPU execution, if observed, must be explicitly labeled and meet the same usability budgets.

## Reversible assumptions

- One user account, one Mac, no remote access or multi-user collaboration. Later multi-user support would change authentication and storage isolation.
- Manual app launch and scans first; scheduling runs while open, with no always-on service requirement. No email/calendar connector is required for a useful Chief of Staff.
- Local timezone initially America/Chicago from the environment; persist it as configuration and test daylight-saving boundaries. Paths and destination rules require explicit selection before personal-folder operations.
- A single default model profile serves both apps; smaller models may qualify for fewer workflows. No model is presumed equally capable.
- Default retention/budget values are proposals and can change after synthetic testing. No performance thresholds have been measured.

## Unresolved gates, not documentation blockers

| Gate | Needed evidence / decision | Timing |
| --- | --- | --- |
| Q-01 | Repository selected: `practical_AI_Automation`. Tested Python/dependency pins remain to be established. No repository-specific AGENTS.md existed before this addition. | M1 build start |
| Q-02 | Does Ollama 0.34.0 execute each intended model on this A18/macOS build, with what backend and resource use? | M3 evaluation before enabling AI |
| Q-03 | Can the selected provider prove running-request termination, or must recovery use the explicit runtime restart barrier? Confirm exclusive runtime ownership without disrupting other tools. | M3 coordination tests |
| Q-04 | Which models/workflows meet quality and memory budgets? Installed availability alone is insufficient. | M3 selection |
| Q-05 | Native PhotoKit bridge/API support, permissions, iCloud originals, pair handling and backup expectations on the then-current OS. | M5 feasibility |

None blocks these planning documents or deterministic M1/M2 design. No user question is necessary in this phase.

## Repository placement update

The user subsequently authorized a local checkout and push to [JeffGeissler/practical_AI_Automation](https://github.com/JeffGeissler/practical_AI_Automation). Inspected clean `main` at `b053172` before adding documentation. Existing files are `README.md`, `requirements.txt`, `api/main.py`, and `handlers/`. No tests, lockfile, packaging manifest or AGENTS.md were present in that checkout.

The existing code defines FastAPI POST `/execute`, dispatches `log_fitness`, and returns a success message from the supplied meal name. It does not persist meals or implement the proposed apps, authentication, CSRF protection, inference or filesystem automation. Requirements list unpinned FastAPI, Uvicorn, Requests and Pydantic. The existing README describes broader Shortcuts/local-or-cloud automation; that concept does not override the new apps’ local-only inference and browser security requirements. Reuse the existing FastAPI direction while keeping this prototype unchanged; decide any migration explicitly during M1.

Only planning Markdown and a navigation link are changed for publication. The original workspace copies are historical snapshots; this repository is the maintained planning source. Local clone/commit/push are authorized by the follow-up request, while application implementation remains documentation-only until explicitly requested.

## Chief of Staff concept refinement

The subsequent user request restricts this revision to **local documentation with no external mutations**; the earlier publication authorization does not authorize another push for this revision. Read the supplied March 27, 2026 v2.0 concept as vision, with the current MVP constraints taking precedence. Its checked-off dashboard, CRUD, AI briefings, HC Audit and Start Ollama claims have no supporting implementation in this checkout. Scoped workspace search found only the small Organizer tag/rule helpers, not the claimed integrated file tagger or HC Automation module. See the full [claim audit](chief-of-staff/PRD.md#concept-translation-and-claim-audit).

| ID / requirements | Refinement | Rationale / deferred alternative |
| --- | --- | --- |
| D-10 / CS-01–CS-05, R-02 | First usable release is manual CRUD, Today and factual briefings, including notes/preferences and explicit time semantics. | Preserve planning purpose without an inference dependency; concept's completed-foundation and week estimates remain unverified. |
| D-11 / CS-06–CS-09, R-07/R-11 | Compiled workflow registry plus durable jobs replaces dynamic spawning, instance tables and message bus. Routine user Save is sufficient approval; proposals and sensitive operations use scoped review. | Avoid continuous agents, repeated confirmation dialogs and model-derived authority. |
| D-12 / CS-12, R-03 | Chief can request Organizer previews only; execution approval/journal stays in Organizer. | Single owner of filesystem effects makes lost-response recovery tractable and avoids duplicated moves. |

New CS requirement IDs and C1–C4 milestones refine the existing R IDs/M milestones without renumbering them. No implementation, runtime evaluation or benchmark was performed for this revision. Remaining integration gates concern actual HC Audit/file-tagger source, Organizer readiness and A18 model qualification; they do not block the deterministic first release.

After the local documentation review, the user explicitly requested a GitHub push of this revision. That follow-up authorizes its commit and publication, without authorizing application implementation or runtime changes.
