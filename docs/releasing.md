# Releasing fulcrum-trust

Publishing runs through `.github/workflows/publish.yml` using PyPI **Trusted Publishing**
(OIDC). There are no API tokens anywhere — not in repo secrets, not in environment
secrets. Do not add any.

The pipeline is `build → TestPyPI → PyPI`. TestPyPI is a hard gate: `publish-pypi` has
`needs: publish-testpypi`, so a red TestPyPI job skips the real release. Do not remove
that gate.

## Cutting a release

1. Bump `version` in `pyproject.toml` and update `CHANGELOG.md`. Merge to `main`.
2. Tag it: `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. Watch Actions → **Publish**. The pipeline uploads to TestPyPI, then to PyPI.

### Push the tag — never pre-upload

Do not run `twine upload` by hand before pushing the tag. The pipeline publishes the
release; a manual upload races it and breaks it.

This is not hypothetical. For v0.2.0, `0.2.0` was hand-uploaded to PyPI at
`2026-04-10T00:50:42Z`; the tag run started at `00:51:18Z`. Thirty-six seconds later the
pipeline's prod upload hit an already-existing file and the job went red — with the
package already on PyPI. The prod job deliberately has **no** `skip-existing`, so a
duplicate is a hard failure by design.

## Verifying the trusted publisher without cutting a release

`publish.yml` has a `workflow_dispatch` trigger. Actions → **Publish** → *Run workflow*.

A dispatch run:

- builds the full artifact (sdist + wheel), so a dry run proves the real thing;
- skips the tag/version check (on a dispatch `GITHUB_REF_NAME` is a branch, not a tag);
- publishes to **TestPyPI only** — `publish-pypi` is gated on `github.event_name == 'push'`
  and can never fire from a manual run;
- is repeatable: the TestPyPI step sets `skip-existing: true`, and the **Report upload
  result** step writes a job summary naming every file uploaded and every file skipped as
  already-existing. A green run that uploaded nothing says so explicitly.

A green TestPyPI job proves the publisher registration is valid. `skip-existing` cannot
mask that: OIDC authenticates before any upload, so a bad registration still fails red
with `invalid-publisher`.

## Trusted publisher registration

Registration happens on the PyPI side, in a browser, by a project owner. Two indexes must
each carry an entry.

### The casing rule — read this before typing anything

PyPI matches the OIDC claim against the stored publisher with **exact, case-sensitive SQL
equality** on `repository_name`, `repository_owner`, `repository_owner_id`, and
`workflow_filename`. Only `environment` is normalized (lowercased). See
`lookup_by_claims` in
[`warehouse/oidc/models/github.py`](https://github.com/pypi/warehouse/blob/main/warehouse/oidc/models/github.py).

The repository's canonical name on GitHub is:

```
Fulcrum-Governance/Fulcrum-Trust
```

Capital **F**, capital **T**. Enter it exactly that way.

`[project.urls]` in `pyproject.toml` carries this canonical casing as of FUL-369. The
prose GitHub URLs elsewhere — `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`,
`docs/blog-trust-circuit-breaker.md` — still say lowercase `fulcrum-trust`, and that is
fine: GitHub redirects, so they resolve in a browser and in `git clone`. But a publisher
registered as `fulcrum-trust` will **never** match a claim, and the failure message
(`invalid-publisher: valid token, but no corresponding publisher`) does not tell you that
casing is the reason.

### Check for an existing entry first

On each index's Publishing page, look at what is already registered before adding
anything:

- **An entry exists but differs** (typically lowercase `fulcrum-trust`) — remove it and
  re-add with the canonical casing below. A stale entry is what a repository rename leaves
  behind.
- **No entry exists** — add it fresh.

The project already exists on both indexes, so use each project's **publishing settings** —
not the "pending publisher" flow, which is only for projects that do not exist yet.

### TestPyPI

<https://test.pypi.org/manage/project/fulcrum-trust/settings/publishing/>

| Field | Value |
|---|---|
| Owner | `Fulcrum-Governance` |
| Repository name | `Fulcrum-Trust` |
| Workflow name | `publish.yml` |
| Environment name | `testpypi` |

### PyPI (production)

<https://pypi.org/manage/project/fulcrum-trust/settings/publishing/>

| Field | Value |
|---|---|
| Owner | `Fulcrum-Governance` |
| Repository name | `Fulcrum-Trust` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

Check the prod entry whenever you touch the TestPyPI one. Prod OIDC demonstrably worked
once — the pipeline published `0.1.0` to PyPI on 2026-02-23 — but has not been exercised
since, so a broken prod publisher would go unnoticed until a release tag. Whatever
invalidates one entry (account-side removal, a repository rename) invalidates both.

## Claims the workflow presents

Useful when comparing a registration against reality. Taken verbatim from a real run:

```
sub                : repo:Fulcrum-Governance/Fulcrum-Trust:environment:testpypi
repository         : Fulcrum-Governance/Fulcrum-Trust
repository_owner   : Fulcrum-Governance
repository_owner_id: 253385089
job_workflow_ref   : Fulcrum-Governance/Fulcrum-Trust/.github/workflows/publish.yml@refs/tags/v0.3.0
environment        : testpypi
```

When a publish fails with `invalid-publisher`, the job log prints this same claim set.
Compare it field by field against the registration page.
