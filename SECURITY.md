# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | ✅ |
| < 1.0 | ❌ |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report privately using GitHub's
[private vulnerability reporting](https://github.com/aditya89bh/meeting-memory-system/security/advisories/new)
("Report a vulnerability" under the repository's **Security** tab).

When reporting, please include:

- A description of the vulnerability and its impact
- Steps to reproduce (a minimal proof of concept if possible)
- Affected version(s) and environment details

You can expect an initial acknowledgement within a few days. We will work with you to
understand and resolve the issue promptly and will credit you in the release notes unless
you prefer to remain anonymous.

## Security posture

The Meeting Memory System is **local-first and deterministic** by design:

- It performs no outbound network calls during its core pipeline (parsing, extraction,
  retrieval, graph building, analysis).
- It has no required third-party runtime dependencies for the core; the REST API and SDK
  extras add FastAPI/uvicorn and httpx respectively.
- All data is stored locally in a single SQLite database you control.

When deploying the REST API, follow standard practices: run behind a trusted reverse
proxy, restrict network exposure, and protect the database file and backups as you would
any sensitive data store. See [docs/deployment.md](docs/deployment.md).
