# Contributing

Thanks for your interest in improving the Meeting Memory System! This project values
**determinism, correctness, and clarity**. Contributions of all sizes are welcome.

## Ground rules

This project has one non-negotiable principle: **it must stay deterministic and
local-first**. Contributions must not introduce:

- LLM APIs, embeddings, or vector databases as runtime dependencies
- Network calls during parsing, extraction, retrieval, graph building, or analysis
- Randomness that affects outputs (seed any necessary randomness)

The same inputs must always produce the same outputs.

## Development setup

```bash
git clone https://github.com/aditya89bh/meeting-memory-system.git
cd meeting-memory-system

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quality gates

All of these must pass before a change can be merged. Run them locally:

```bash
ruff check .                 # lint
ruff format --check .        # formatting
mypy src                     # static types
pytest --cov                 # tests + coverage (target: 100%)
python -m build              # packaging
meeting-memory demo          # end-to-end smoke test
```

New code must keep test coverage at 100% (branch coverage is enabled).

## Pull request guidelines

- **One commit = one logical change.** Keep PRs focused.
- Use clear, conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `ci:`,
  `chore:`).
- Update documentation and the [CHANGELOG](CHANGELOG.md) when behaviour changes.
- Every subsystem you touch should be exercised by a tutorial, demo, case study, or
  notebook where practical.
- Do **not** include AI-assistant attribution or `Co-authored-by` trailers in commits.

## Coding conventions

- Python 3.10+ with full type annotations (`mypy` strict-friendly).
- Prefer small, pure, well-named functions; document non-obvious intent only.
- Schema changes are **append-only** migrations — never edit an existing migration.
- Public APIs (service layer, REST routes, SDK methods) are stable; avoid breaking them
  outside of a major version.

## Reporting bugs and requesting features

Use the [issue templates](.github/ISSUE_TEMPLATE/). For security issues, follow
[SECURITY.md](SECURITY.md) instead of opening a public issue.

By contributing, you agree that your contributions are licensed under the project's
[MIT License](LICENSE) and that you abide by the [Code of Conduct](CODE_OF_CONDUCT.md).
