# Contributing to NIO

NIO is MIT licensed and accepts contributions.

## Getting started

```bash
git clone https://github.com/shawnla90/nio
cd nio
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/
```

## Code style

- Python 3.11+ required
- Linted with `ruff` (config in `pyproject.toml`)
- No em dashes in code comments or docstrings
- Run `ruff check nio/ tests/` before submitting

## Tests

All changes need tests. Run:

```bash
pytest tests/ -q
```

Test files go in `tests/`. Fixtures that need a temp database should use the `tmp_db` pattern (see existing tests).

## Souls and voices

Souls live in `registry/souls/`. Voices live in `registry/voice-profiles/`. Both are markdown with YAML frontmatter. Edit them like any other file.

To add a new soul:
1. Create `registry/souls/your-soul.md` with the standard frontmatter schema
2. Add tests in `tests/test_soul_inheritance.py`
3. PR with a description of what the soul is for

## Anti-slop rules

Rules live in `registry/anti-slop.json`. After editing, run `nio antislop sync` to regenerate the Python and TypeScript validators.

## Issues

Use GitHub issues. Label bugs as `bug`, features as `enhancement`. If you are unsure whether something is a bug, open an issue anyway.
