# Summary

<!-- What does this PR do and why? Link any related issues. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactor / chore

## Checklist

- [ ] One logical change per commit; clear commit messages
- [ ] `ruff check .` passes
- [ ] `ruff format --check .` passes
- [ ] `mypy src` passes
- [ ] `pytest --cov` passes with 100% coverage
- [ ] `python -m build` succeeds
- [ ] Documentation / CHANGELOG updated where needed
- [ ] Change preserves **deterministic, local-first** behaviour (no LLM APIs, embeddings,
      or required network calls; no output-affecting randomness)
- [ ] No AI-assistant attribution or `Co-authored-by` trailers in commits

## Notes for reviewers

<!-- Anything reviewers should focus on, screenshots, etc. -->
