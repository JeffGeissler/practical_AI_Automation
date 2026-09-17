# practical_AI_Automation

Practical iOS automation framework for building powerful workflows without publishing to the App Store. This project enables iOS users to create sophisticated automation by combining Apple Shortcuts with a Python backend service.

## Overview

**practical_AI_auto** is a distributed automation system that leverages Apple's Shortcuts app to trigger custom logic running on a Python service. Instead of being limited to App Store distribution, this approach provides flexibility to run custom automation workflows locally or in the cloud.

## Architecture

The system follows a modular, layered architecture:

```
Apple Shortcut
    ↓ (HTTP request)
curl / HTTP Client
    ↓
Python Service (Local or Cloud)
    ↓
Handler (Modular Logic)
    ↓
Output Options
    ├── GitHub (repo updates, issues, PRs)
    ├── JSON (structured data)
    └── Notifications (alerts, messages)
```

### Components

- **Apple Shortcut**: Entry point triggering the automation workflow
- **HTTP Client (curl)**: Sends requests from the Shortcut to the backend service
- **Python Service**: Backend processing layer (can run locally or on cloud infrastructure)
- **Handler**: Modular business logic processing requests and orchestrating workflows
- **Output**: Flexible output destinations including GitHub integration, JSON exports, and system notifications

## Requirements

- iOS device with Shortcuts app
- Python 3.8+
- HTTP connectivity between iOS device and Python service

## Getting Started

*(Project setup instructions coming soon)*

## Usage

*(Usage examples and documentation coming soon)*

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

To be determined

## Local AI application planning

See [the planning index](docs/README.md) for the proposed AI Chief of Staff and Organizer applications, shared architecture, decisions, and model evaluation plan. This work is documentation only; the existing Shortcuts prototype is preserved. The new applications require local-only inference and the security boundaries described in those plans.
