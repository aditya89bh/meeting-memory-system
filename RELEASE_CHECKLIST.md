# Release checklist

This checklist makes releases of the Meeting Memory System repeatable and auditable.
The project follows [Semantic Versioning](https://semver.org/) and the
[Keep a Changelog](https://keepachangelog.com/) format.

## Version checklist

Pick the version bump from the nature of the changes since the last release:

- **MAJOR** (`X.0.0`) — incompatible public API changes (CLI flags, REST routes, SDK
  signatures, or database schema migrations that are not backward compatible).
- **MINOR** (`x.Y.0`) — backward-compatible functionality (new commands, endpoints,
  insight providers, additive schema migrations).
- **PATCH** (`x.y.Z`) — backward-compatible bug fixes and documentation only.

Keep the version in sync in **both** places:

- [ ] `pyproject.toml` → `project.version`
- [ ] `src/meeting_memory/__init__.py` → `__version__`

## Pre-release

- [ ] `git switch main && git pull --ff-only`
- [ ] Working tree is clean (`git status`)
- [ ] `CHANGELOG.md` has a dated section for the new version and an empty `[Unreleased]`
- [ ] `ROADMAP.md` reflects what shipped vs. what is still planned
- [ ] Migration notes added to [`MIGRATION.md`](MIGRATION.md) if behaviour changed

## Quality gates

Run from a clean checkout with `pip install -e ".[dev]"`:

- [ ] `ruff check .`
- [ ] `ruff format --check .`
- [ ] `mypy src`
- [ ] `pytest --cov` (coverage stays at 100%)
- [ ] `python -m build` (sdist + wheel)
- [ ] `meeting-memory demo`
- [ ] API smoke test (`uvicorn meeting_memory.api.app:app` then `GET /health`)
- [ ] SDK smoke test (`examples/api/sdk_quickstart.py`)
- [ ] Dashboard loads (`GET /` returns the dashboard HTML)
- [ ] `docker build -t meeting-memory .` (if Docker is available)
- [ ] `mkdocs build --strict`

## Cut the release

- [ ] Commit the version bump: `chore: prepare vX.Y.Z release`
- [ ] Verify no `Co-authored-by:` trailers and no tool attribution in commits
- [ ] `git push origin main`
- [ ] Tag the release: `git tag -a vX.Y.Z -m "vX.Y.Z"`
- [ ] `git push origin vX.Y.Z`
- [ ] Confirm the **Release** workflow builds, checks, and publishes the artifacts
- [ ] Confirm the **Docs** workflow deploys the documentation site

## Post-release

- [ ] Verify the GitHub release notes and attached `dist/*` artifacts
- [ ] Announce highlights and known limitations
- [ ] Open the next `[Unreleased]` section in `CHANGELOG.md`
