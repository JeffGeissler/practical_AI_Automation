# practical_AI_Automation

Personal automation and AI assistant projects that run on your own Mac.

## What's here

| Part | Status | Where |
| --- | --- | --- |
| **Productivity Assistant** | Design proposal, not yet built | [Design](docs/ARCHITECTURE.md) |
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

The Productivity Assistant and the planned local AI apps are documentation only.
Nothing in this repository stores personal data; keep databases, documents, logs
and secrets outside it.

## License

To be determined.
