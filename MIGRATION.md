# Migration notes

This document records upgrade notes between releases. The project keeps the public
surface (CLI, REST API, Python SDK) backward compatible and applies database schema
changes as additive, forward-only migrations.

## Upgrading to 1.0.0 (from 0.9.0)

**No action required.** v1.0.0 is a productization and documentation release. There are
no public API changes, no CLI flag removals, and no database schema changes relative to
0.9.0. Existing databases, scripts, and deployments continue to work unchanged.

What changed:

- New `meeting-memory demo` command (additive).
- New example organizations, tutorials, notebooks, case studies, and a documentation
  site (documentation only).
- Benchmark visualization assets and a `--charts` option on `meeting-memory benchmark`
  (additive).
- GitHub Actions workflows for CI, docs, and releases (repository tooling only).

To upgrade:

```bash
git pull
pip install -e ".[api,sdk]"   # or: pip install --upgrade meeting-memory
```

## General upgrade guidance

- Back up the database before upgrading across a MAJOR version:

  ```bash
  meeting-memory backup ./meeting-memory.db --output ./backup
  ```

- Schema migrations run automatically when the store opens an existing database; they
  are additive and idempotent.
- Pin the version in production deployments and review [`CHANGELOG.md`](CHANGELOG.md)
  before upgrading.
