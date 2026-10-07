# practical_AI_Automation

Personal automation and AI assistant projects that run on your own Mac.

## What's here

| Part | Status | Where |
| --- | --- | --- |
| **Productivity Assistant** | Phase 1 built (tasks, priorities, briefings, backups) plus AI-assisted capture | [Design](docs/ARCHITECTURE.md), [plan](docs/PRODUCTIVITY_IMPLEMENTATION_PLAN.md) |
| **Planning for local AI apps** (Chief of Staff, Organizer) | Planning documents | [Planning index](docs/README.md) |
| **Shortcuts automation prototype** | Small working prototype | `api/`, `handlers/` |

### Productivity Assistant

A task and planning assistant: plain-language capture, a transparent prioritized
list, morning briefings and evening reviews, document search, and read-only
imports from Jira, Confluence and MS Project. It is local by default. AI only
proposes and you confirm, and every feature works without AI. A cloud model is an
optional, per-request opt-in, with the provider still to be chosen. See the
[design](docs/ARCHITECTURE.md) for architecture, principles, data, security,
roadmap and open decisions.

**Built so far (Phase 1, no AI):** tasks and projects with dependencies and full
change history; a transparent priority score with pins, up/down and snooze (see
[how scoring works](docs/PRIORITIZATION.md)); a factual morning briefing and
evening review, made on schedule or when you next open the app; JSON/CSV export;
and a daily backup keeping the newest 14.

**AI-assisted capture (M4):** type a note such as "Send Q3 report to Dana by
Friday, about 2 hours" on Today and confirm an editable draft. Rules in the app
read the due date, importance, effort and project; a small local model
(qwen3:0.6b in Ollama) suggests a clean title. Nothing is saved until you
confirm, and capture works the same with the model off or Ollama not running.

Run it (Python 3.9 or later; verified on this Mac with Python 3.9.6):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/productivity-assistant            # then open http://127.0.0.1:8000/
```

Your data lives in `~/Library/Application Support/ProductivityAssistant`, outside
this repository. Set `PA_DATA_DIR` to use another folder, or `PA_PORT` for another
port. The app listens only on `127.0.0.1`. AI uses `qwen3:0.6b` from an
already-running Ollama on this Mac if it is installed; set `PA_AI_MODEL=off` to
turn AI off. The app never starts Ollama or downloads models.

| Command | Does |
| --- | --- |
| `.venv/bin/productivity-assistant backup` | Write a backup now |
| `.venv/bin/productivity-assistant restore <file>` | Replace the database with a verified backup (stop the app first); the current state is backed up first |
| `.venv/bin/ruff check . && .venv/bin/pytest -q` | Lint and tests (synthetic data in temporary folders) |

### Shortcuts automation prototype

An Apple Shortcut sends an HTTP request to a small Python service, which runs a
handler and returns JSON:

```
Apple Shortcut → HTTP request → FastAPI service → handler → JSON response
```

The service (`api/main.py`) exposes `POST /execute`, taking an `action` and a
`payload`. The one handler today is `log_fitness` (`handlers/fitness.py`), which
returns a confirmation for a meal. Dependencies are listed in `requirements.txt`.
Setup and run instructions will be added once they have been verified.

## Status

Productivity Assistant Phase 1 (M0–M3) and AI capture (M4) are implemented and
tested; AI summaries, documents, integrations and cloud use are not built yet. The Chief of Staff and
Organizer apps remain planning documents. Nothing in this repository stores
personal data; keep databases, documents, logs and secrets outside it.

## License

To be determined.
