# Contributing to fulcrum-trust

Thank you for your interest in contributing. This document covers dev setup, running tests, and the PR process.

## Development Setup

```bash
# Clone and install in editable mode with dev dependencies
git clone https://github.com/Fulcrum-Governance/fulcrum-trust.git
cd fulcrum-trust
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest                  # all 240 tests with coverage (must be >=95%)
pytest --tb=short       # shorter tracebacks
pytest tests/test_manager.py -v  # single module
```

## Type Checking

```bash
mypy fulcrum_trust/     # must report: Success: no issues found
```

## Linting and Formatting

```bash
ruff check .            # lint (must be zero errors)
ruff format .           # auto-format
ruff format --check .   # verify format without writing (used in CI)
```

## Pull Request Guidelines

- Keep PRs focused on a single concern
- All tests must pass: `pytest`
- Zero mypy errors: `mypy fulcrum_trust/`
- Zero ruff errors: `ruff check .`
- Add tests for any new behavior
- Update docstrings for any changed public API

## Code Conventions

- **Type hints everywhere** — mypy strict, no `Any` without justification
- **Docstrings** — Google style on all public classes/methods
- **Imports** — absolute imports only (`from fulcrum_trust.types import TrustState`)
- **Python 3.9+** — use `from __future__ import annotations` in all modules

## Reporting Issues

Open an issue at https://github.com/Fulcrum-Governance/fulcrum-trust/issues. Include:
- Python version and OS
- Minimal reproducible example
- Expected vs. actual behavior
