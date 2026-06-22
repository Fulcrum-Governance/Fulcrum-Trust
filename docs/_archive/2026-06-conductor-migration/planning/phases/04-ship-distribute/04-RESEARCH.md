# Phase 4: Ship + Distribute — Research

**Researched:** 2026-02-18
**Domain:** Python packaging, PyPI publishing, GitHub releases, community distribution
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DIST-01 | `pip install fulcrum-trust` works from a clean virtualenv | PyPI publish flow (build → twine check → TestPyPI → PyPI); pyproject.toml already correct |
| DIST-02 | README has quickstart (install → 5 lines → working trust evaluation) | README.md quickstart already exists and is correct |
| DIST-03 | API reference documentation covers all public classes/methods | mkdocstrings-python with Google-style docstrings; or inline REFERENCE.md — see Architecture Patterns |
| DIST-04 | Blog post published (already drafted at docs/blog-trust-circuit-breaker.md) | Blog is 1831 words, draft status; needs status change and publication destination |
| DIST-05 | Distribution posts live on HN, Reddit, Discord | Show HN, r/MachineLearning [P], r/Python — human actions; plan produces draft copy |
</phase_requirements>

---

## Summary

Phase 4 ships a Python package that is already functionally complete (97 tests, 96.83% coverage, mypy clean) and focuses on the publish pipeline, documentation polish, and community distribution. The dominant technical task is setting up a `publish.yml` GitHub Actions workflow using PyPI Trusted Publishing (OIDC) — the modern approach that eliminates API tokens entirely. The workflow triggers on `v*` tag pushes, runs `python -m build`, and publishes via `pypa/gh-action-pypi-publish@release/v1`.

For API documentation (DIST-03), the project already has Google-style docstrings and a small public surface (`TrustManager`, `TrustOutcome`, `TrustState`, `TrustConfig`, `MemoryStore`, `FileStore`). The right approach for a small package at v0.1.0 is a single `docs/api-reference.md` file using mkdocstrings syntax — no Sphinx, no full MkDocs site required. This satisfies DIST-03 without adding CI complexity.

Community distribution (DIST-04, DIST-05) is entirely human-driven. The plan should produce ready-to-use post copy for HN, Reddit, and Discord. The blog post at `docs/blog-trust-circuit-breaker.md` is the anchor content; the HN post links directly to the GitHub repo, not the blog. Reddit r/MachineLearning uses a `[P]` tag for personal projects. Optimal HN timing is Tuesday–Thursday, 7–9 AM US Eastern.

**Primary recommendation:** Use PyPI Trusted Publishing (OIDC) via pending publisher for the first publish — no API tokens stored anywhere, converts to normal publisher on first use.

---

## Standard Stack

### Core

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `python -m build` | build 1.x | Produces sdist + wheel in `dist/` | PEP 517/518 compliant; hatchling already configured |
| `twine` | 5.x | Metadata validation + manual upload fallback | `twine check dist/*` catches README rendering issues before upload |
| `pypa/gh-action-pypi-publish` | `release/v1` | GitHub Actions PyPI upload via OIDC | Official pypa action; tokenless; PEP 740 attestations auto-generated |
| `gh` CLI | 2.x | Create GitHub release, attach notes | Official GitHub CLI; `--notes-file` accepts CHANGELOG excerpt |

### Supporting

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `mkdocstrings[python]` | `>=0.18` | API reference from Google-style docstrings | DIST-03: generates `docs/api-reference.md` from `:::` syntax |
| `mkdocs-material` | 9.x | Optional: serve full MkDocs site | Only if a hosted docs site is wanted; not required for v0.1.0 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Trusted Publishing (OIDC) | PyPI API token in GitHub Secrets | Token approach works but is less secure; tokens can leak; OIDC is now the recommended standard |
| `pypa/gh-action-pypi-publish` | `twine upload` in CI with token | Same as above — token required, harder to rotate |
| mkdocstrings inline ref | Sphinx autodoc | Sphinx requires reStructuredText config, heavier setup; overkill for 6 public classes |
| mkdocstrings inline ref | pdoc | pdoc is simpler but outputs standalone HTML, harder to embed in README context |

**Installation (dev docs tools):**
```bash
pip install "mkdocstrings[python]>=0.18" mkdocs-material
```

---

## Architecture Patterns

### Pattern 1: PyPI Trusted Publishing (OIDC) — Pending Publisher Flow

**What:** Configure PyPI to trust GitHub Actions OIDC tokens from a specific repo+workflow before the project even exists. On first publish, the pending publisher converts to a normal publisher and the project is created automatically.

**When to use:** Every new PyPI project. No API tokens, no secrets to rotate.

**Setup steps (human, done once):**
1. Go to `https://pypi.org/manage/account/publishing/` (account sidebar, not project sidebar)
2. Fill in: Project name = `fulcrum-trust`, Owner = `Fulcrum-Governance`, Repo = `fulcrum-trust`, Workflow = `publish.yml`, Environment = `pypi`
3. Repeat for TestPyPI: `https://test.pypi.org/manage/account/publishing/`
4. Create GitHub environment named `pypi` in repository Settings → Environments (optional but recommended for manual approval gate)

**Critical caveat:** A pending publisher does NOT reserve the name. If another user registers `fulcrum-trust` before the first publish, the pending publisher is invalidated.

### Pattern 2: publish.yml Workflow

**What:** GitHub Actions workflow triggered on `v*` tag push. Separates build (restricted permissions) from publish (OIDC permissions) into two jobs.

**Example:**
```yaml
# Source: https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/
name: Publish

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    name: Build distribution
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install build
        run: pip install build

      - name: Build distributions
        run: python -m build

      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish-testpypi:
    name: Publish to TestPyPI
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: testpypi
      url: https://test.pypi.org/p/fulcrum-trust
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://test.pypi.org/legacy/

  publish-pypi:
    name: Publish to PyPI
    needs: publish-testpypi
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/fulcrum-trust
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
```

**Key rules:**
- `id-token: write` is mandatory at the job level (not workflow level) for security
- `needs: publish-testpypi` serializes TestPyPI → PyPI; remove if you want them parallel
- No `username`, `password`, or `token` needed — OIDC handles it
- Action version: `release/v1` (not `master` — that branch is sunset)

### Pattern 3: Manual Publish Flow (pre-CI dry run)

**What:** Run the build + upload locally to TestPyPI first, before the automated workflow exists.

```bash
# Build
python -m build
# Outputs: dist/fulcrum_trust-0.1.0-py3-none-any.whl
#          dist/fulcrum_trust-0.1.0.tar.gz

# Validate metadata (catches README render issues)
twine check dist/*

# Upload to TestPyPI
twine upload --repository testpypi dist/*
# Prompts for TestPyPI username (__token__) and password (API token)

# Verify install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ fulcrum-trust

# Upload to real PyPI (only if TestPyPI looks good)
twine upload dist/*
```

### Pattern 4: GitHub Release Creation

**What:** Create a GitHub release from the tag, attach changelog notes, mark as latest.

```bash
# Create annotated tag first
git tag -a v0.1.0 -m "v0.1.0 - initial release"
git push origin v0.1.0

# Create release with notes from file
gh release create v0.1.0 \
  --title "v0.1.0 - Initial Release" \
  --notes-file RELEASE_NOTES.md \
  --latest \
  dist/*.whl dist/*.tar.gz
```

**Alternatively**, `--generate-notes` uses GitHub's auto-generated release notes from PR titles and commits since the last tag — useful if commits are well-labeled.

### Pattern 5: CHANGELOG.md Format (Keep a Changelog 1.1.0)

**What:** Standard changelog format. Latest version first, ISO 8601 dates.

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-02-19

### Added

- Beta distribution trust model (`TrustEvaluator`) with configurable priors
- `TrustManager` orchestrating evaluation, storage, and time-decay
- Exponential decay toward uninformative prior (configurable half-life)
- `MemoryStore` (default, in-process) and `FileStore` (JSON-backed, cross-session)
- Abstract `TrustStore` Protocol for custom store implementations
- LangGraph adapter (`TrustAwareGraph`) wrapping existing `StateGraph` graphs
- `TrustOutcome.PARTIAL` for fractional trust signals
- Circuit breaker: `should_terminate()` returns `True` below configurable threshold
- Configurable `TrustConfig` (threshold, half-life, outcome weights)
- 97 tests, 96.83% coverage, mypy strict clean

[Unreleased]: https://github.com/Fulcrum-Governance/fulcrum-trust/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Fulcrum-Governance/fulcrum-trust/releases/tag/v0.1.0
```

### Pattern 6: API Reference (mkdocstrings inline)

**What:** Single Markdown file auto-generating API docs from Google-style docstrings using `:::` syntax. No full MkDocs site required — can be a `docs/api-reference.md` file linked from README.

**mkdocs.yml (minimal):**
```yaml
site_name: fulcrum-trust
theme:
  name: material

plugins:
  - search
  - mkdocstrings:
      default_handler: python
      handlers:
        python:
          options:
            docstring_style: google
            show_root_heading: true
            show_symbol_type_heading: true
            show_source: false
```

**docs/api-reference.md:**
```markdown
# API Reference

## TrustManager

::: fulcrum_trust.manager.TrustManager
    options:
      docstring_style: google

## Types

::: fulcrum_trust.types.TrustState
::: fulcrum_trust.types.TrustConfig
::: fulcrum_trust.types.TrustOutcome

## Stores

::: fulcrum_trust.stores.memory.MemoryStore
::: fulcrum_trust.stores.file.FileStore

## Adapters

::: fulcrum_trust.adapters.langgraph.TrustAwareGraph
```

**Note on DIST-03 scope:** For v0.1.0, a `docs/api-reference.md` committed to the repo and linked from README satisfies DIST-03 without requiring a hosted docs site. Hosted docs (Read the Docs, GitHub Pages) can be deferred.

### Pattern 7: mypy Strict Pass Checklist

**What:** Verify these before tagging v0.1.0. The `pyproject.toml` already enables `strict = true`.

```bash
mypy src/fulcrum_trust/
```

**Strict mode enables these flags (verified from mypy docs):**
- `--disallow-untyped-defs` — all functions must have complete annotations
- `--disallow-any-generics` — no bare `List`, `Dict` — must be `List[str]`, etc.
- `--warn-return-any` — no returning `Any` from typed functions
- `--no-implicit-reexport` — `__init__.py` must use `from x import y as y` or `__all__` for public API

**The `--no-implicit-reexport` implication:** `fulcrum_trust/__init__.py` already uses `__all__` correctly. This is fine.

**Pre-ship verification:**
```bash
mypy fulcrum_trust/ --no-error-summary    # zero errors required
ruff check .                               # zero errors required
ruff format --check .                      # zero diff required
pytest --tb=short                          # all 97 tests pass, >=95% coverage
twine check dist/*                         # Passed (0 warnings)
```

### Anti-Patterns to Avoid

- **Uploading to real PyPI before TestPyPI dry run:** Once uploaded, a version cannot be deleted or re-uploaded. Name your version right the first time.
- **Using `master` branch for pypa/gh-action-pypi-publish:** That branch is sunset. Use `release/v1`.
- **Setting `id-token: write` at workflow level:** Set it at the job level only — minimum privilege.
- **Tagging before CI passes:** Tag only from a clean main with passing CI. Use `--verify-tag` in gh release create.
- **Forgetting to build both wheel AND sdist:** `python -m build` creates both by default. Always upload both.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PyPI auth in CI | Custom token management, secret rotation | PyPI Trusted Publishing (OIDC) | Tokens leak via logs, need rotation; OIDC tokens expire per-job automatically |
| Package metadata validation | String parsing of pyproject.toml | `twine check dist/*` | Catches README rendering, missing fields, invalid classifiers |
| CHANGELOG linking | Custom link generation | Keep a Changelog footer link syntax | Standard tooling (auto-changelog, release-drafter) expects this format |
| API reference generation | Writing docs by hand | mkdocstrings with `:::` syntax | Docstrings already exist; auto-generation stays in sync with code |

**Key insight:** The packaging ecosystem has solved every step of this pipeline. The task is configuration, not code.

---

## Common Pitfalls

### Pitfall 1: Version Already Exists on PyPI

**What goes wrong:** After uploading v0.1.0, you discover a bug and try to re-upload `fulcrum_trust-0.1.0.tar.gz`. PyPI rejects it with HTTP 400.
**Why it happens:** PyPI prohibits re-uploading any version that has ever been published (even on TestPyPI, once uploaded it's immutable for that version string).
**How to avoid:** Use TestPyPI for all dry runs. Clean `dist/` before rebuilding. Don't upload to real PyPI until `twine check` passes and TestPyPI install is verified.
**Warning signs:** `400 File already exists` error from twine.

### Pitfall 2: Pending Publisher Name Race

**What goes wrong:** You configure the pending publisher for `fulcrum-trust` on PyPI, but don't publish quickly. Someone else registers `fulcrum-trust` on PyPI, invalidating your pending publisher.
**Why it happens:** Pending publishers don't reserve the name — only publishing does.
**How to avoid:** Configure the pending publisher and publish within the same session (same day). Don't let it sit for weeks.
**Warning signs:** First publish attempt fails with a name conflict error.

### Pitfall 3: `--no-implicit-reexport` Breaks Consumer Imports

**What goes wrong:** After strict mypy pass, consumers importing `from fulcrum_trust import TrustManager` get mypy errors because `TrustManager` isn't explicitly re-exported.
**Why it happens:** mypy strict mode treats imports in `__init__.py` as private unless listed in `__all__` or imported with `from x import y as y`.
**How to avoid:** The existing `__init__.py` already has `__all__` listing all 6 public names. Verify this is complete before tagging.
**Warning signs:** mypy error `Module "fulcrum_trust" does not explicitly export attribute "TrustManager"` in consumer code.

### Pitfall 4: README Doesn't Render on PyPI

**What goes wrong:** PyPI shows raw Markdown or a warning that README failed to render, making the package page look broken.
**Why it happens:** Relative image paths, non-standard Markdown extensions, or missing `readme = "README.md"` in pyproject.toml.
**How to avoid:** Run `twine check dist/*` — it specifically validates README rendering. The existing pyproject.toml already sets `readme = "README.md"`.
**Warning signs:** `twine check` output shows `FAILED` or `WARNING` for description.

### Pitfall 5: GitHub Actions Upload-Artifact v3 vs v4 Mismatch

**What goes wrong:** CI fails because upload-artifact and download-artifact versions don't match, or v3 is deprecated.
**Why it happens:** `actions/upload-artifact@v3` and `actions/download-artifact@v3` were deprecated in 2024. They still work but emit warnings.
**How to avoid:** Use `actions/upload-artifact@v4` and `actions/download-artifact@v4` consistently. The artifact name format changed between v3 and v4.
**Warning signs:** CI warnings about deprecated actions; download-artifact fails to find artifact by name.

### Pitfall 6: HN Post Rejected / Ignored

**What goes wrong:** Show HN post gets no traction or is flagged.
**Why it happens:** Title sounds like marketing copy; post is a blog post not an installable package; no first comment explaining backstory.
**How to avoid:** Title must start with `Show HN:`. The package must be installable (`pip install fulcrum-trust`). First comment: technical backstory + what's different + honest limitations.
**Warning signs:** Zero upvotes in first 30 minutes; post stays on New page without reaching front page.

---

## Code Examples

Verified patterns from official sources:

### TestPyPI Install Verification
```bash
# Source: https://packaging.python.org/en/latest/guides/using-testpypi/
# Install from TestPyPI (no dependencies on TestPyPI, so use --extra-index-url for PyPI deps)
pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  fulcrum-trust==0.1.0
```

### gh release create (full example)
```bash
# Source: https://cli.github.com/manual/gh_release_create
git tag -a v0.1.0 -m "v0.1.0 — initial release"
git push origin v0.1.0

gh release create v0.1.0 \
  --title "v0.1.0 — Initial Release" \
  --notes-file RELEASE_NOTES.md \
  --latest \
  dist/fulcrum_trust-0.1.0-py3-none-any.whl \
  dist/fulcrum_trust-0.1.0.tar.gz
```

### Clean Build + Check
```bash
# Full pre-publish checklist in order
rm -rf dist/ build/ *.egg-info
python -m build           # creates dist/ with .whl and .tar.gz
twine check dist/*        # must output: PASSED for both files
```

### Show HN Title + First Comment Template
```
Title: Show HN: fulcrum-trust – Trust-based circuit breaking for multi-agent AI systems

First comment:
I built this after seeing (and writing about) the pattern where two LLM agents
get into a loop — each producing valid responses, none making progress. Hard
iteration caps don't help because legitimate pipelines need variable step counts.

fulcrum-trust uses a Beta(α,β) distribution to track interaction quality for
each agent pair. When the trust score drops below a threshold, should_terminate()
returns True. Stale relationships decay exponentially toward the uninformative prior.

The math is intentionally simple (200 LOC core), zero runtime deps, Python 3.9+.

pip install fulcrum-trust

Three demos in the repo show the failure modes: gratitude loops, gradual drift,
and recovery after intervention.

Limitations: you still need to classify each interaction as SUCCESS/PARTIAL/FAILURE
— the library gives you the math, not the signal. And it won't fix agents that
consistently produce garbage.

Happy to answer questions about the Beta distribution choice or the decay model.
```

### r/MachineLearning [P] Post Template
```
Title: [P] fulcrum-trust: Trust-based circuit breaking for multi-agent AI systems (Python, Apache 2.0)

Beta(α,β) trust model for LLM agent pairs. When accumulated evidence of poor
interactions drives the trust score below a threshold, the circuit opens.
Exponential decay toward the uninformative prior handles stale relationships.

Zero runtime deps, mypy strict, 97% coverage.

pip install fulcrum-trust

GitHub: github.com/Fulcrum-Governance/fulcrum-trust

[link to blog post or README]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PyPI API tokens in GitHub Secrets | Trusted Publishing (OIDC) | 2023 (PyPI blog) | No secrets stored; tokens expire per-job; now the recommended approach |
| `setup.py` / `setup.cfg` | `pyproject.toml` (PEP 517/518) | 2021–2023 | Hatchling already configured correctly; no action needed |
| `python setup.py sdist bdist_wheel` | `python -m build` | 2020–2021 | Build tool agnostic; works with any PEP 517 backend |
| `actions/upload-artifact@v3` | `actions/upload-artifact@v4` | 2024 | v3 deprecated; artifact name format changed |
| Sphinx + autodoc | MkDocs + mkdocstrings | 2022–present | Markdown-native; simpler config; growing adoption for small packages |

**Deprecated/outdated:**
- `master` branch of `pypa/gh-action-pypi-publish`: Use `release/v1`
- `PYPI_API_TOKEN` GitHub secret pattern: Replace with Trusted Publishing
- `python setup.py upload`: Never use; use twine

---

## Open Questions

1. **Does the project need a hosted docs site (Read the Docs / GitHub Pages) for v0.1.0?**
   - What we know: DIST-03 says "API reference documentation covers all public classes/methods" — doesn't specify hosted
   - What's unclear: Whether a `docs/api-reference.md` in the repo satisfies the requirement, or if it needs to be hosted at a URL
   - Recommendation: For v0.1.0, commit `docs/api-reference.md` and link from README. Treat hosted docs site as a post-v0.1.0 milestone.

2. **Optimal HN post timing**
   - What we know: Data is noisy. General consensus: Tuesday–Thursday, US morning (7–9 AM Eastern) is well-trafficked
   - What's unclear: No authoritative dataset. Some sources say Sunday; others say midweek
   - Recommendation: Post Tuesday or Wednesday 8 AM Eastern. Show HN posts appear on the Show HN page even if they don't hit the front page, so timing matters less than content quality.

3. **Discord target communities**
   - What we know: DIST-05 mentions Discord but doesn't specify which servers
   - What's unclear: LangChain Discord, LangGraph Discord, and Hugging Face Discord are likely candidates
   - Recommendation: Plan should note the three likely servers and leave channel selection to the human. Plan should produce the copy, not attempt to post.

4. **TestPyPI credentials setup**
   - What we know: TestPyPI has a separate account database from PyPI
   - What's unclear: Whether the user already has a TestPyPI account
   - Recommendation: Plan for 04-03 should include a checkpoint: "verify TestPyPI account exists" before attempting upload.

---

## Sources

### Primary (HIGH confidence)
- `https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/` — official PyPA guide for GitHub Actions publishing with Trusted Publishing
- `https://packaging.python.org/en/latest/guides/using-testpypi/` — official TestPyPI upload and install commands
- `https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/` — pending publisher setup for new projects
- `https://docs.pypi.org/trusted-publishers/using-a-publisher/` — Trusted Publishing configuration and required permissions
- `https://keepachangelog.com/en/1.1.0/` — Keep a Changelog 1.1.0 format specification
- `https://cli.github.com/manual/gh_release_create` — gh release create flags (--title, --notes-file, --latest, asset upload)
- `https://mypy.readthedocs.io/en/stable/command_line.html` — exhaustive list of flags enabled by --strict
- `https://mkdocstrings.github.io/python/usage/` — mkdocstrings-python ::: syntax and mkdocs.yml config
- `https://github.com/pypa/gh-action-pypi-publish` — action version, YAML structure, TestPyPI repository-url

### Secondary (MEDIUM confidence)
- `https://news.ycombinator.com/showhn.html` — Show HN official guidelines (title format, first comment recommendation, what qualifies)
- `https://til.simonwillison.net/pypi/pypi-releases-from-github` — practical Trusted Publishing setup walkthrough
- WebSearch: r/MachineLearning uses `[P]` flair for personal projects; periodic self-promotion threads exist

### Tertiary (LOW confidence)
- HN timing: Multiple conflicting sources. No single authoritative dataset. Tuesday–Thursday 7–9 AM Eastern is a reasonable consensus but not statistically proven.
- Reddit r/MachineLearning rules: Could not fetch subreddit wiki directly. Rules confirmed from secondary sources only — verify before posting.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — build/twine/gh-action-pypi-publish verified from official PyPA docs
- Architecture (publish.yml): HIGH — sourced from official pypa/gh-action-pypi-publish repo and PyPA guide
- TestPyPI flow: HIGH — official packaging.python.org
- CHANGELOG format: HIGH — keepachangelog.com official spec
- mypy strict flags: HIGH — mypy official docs
- mkdocstrings config: HIGH — official mkdocstrings-python docs
- HN posting best practices: MEDIUM — official guidelines + community consensus; timing LOW
- Reddit community patterns: MEDIUM — confirmed via multiple secondary sources; rules page not directly fetched

**Research date:** 2026-02-18
**Valid until:** 2026-06-01 (PyPI tooling stable; gh-action-pypi-publish release/v1 is a stable branch pointer)
