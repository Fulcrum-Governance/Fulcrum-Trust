# Security Policy

## Scope

`fulcrum-trust` is a trusted-code library for trust scoring, circuit breaking,
and related adapters. It is not a general-purpose sandbox, policy-enforced
execution boundary, or safe environment for untrusted code.

## Supported Versions

We currently support security fixes for the latest released `0.2.x` series.
Older versions may receive best-effort guidance, but fixes are not guaranteed.

## Reporting A Vulnerability

Please do not report vulnerabilities through public GitHub issues.

Send reports to `security@fulcrumlayer.io` and include:

- affected version(s)
- impact and attack preconditions
- reproduction steps or proof of concept
- any mitigation ideas or operational constraints

## Security Boundaries And Known Limitations

- Trusted-code-only: if an attacker can run arbitrary Python in the same
  process, they are already outside this package's security boundary.
- Pure-Python sandbox limitations: the RLM prototype uses Python `exec` with a
  restricted builtin namespace. That is not a security boundary and must not be
  used to execute untrusted navigation programs, prompts, or model-generated
  code.
- OS-level isolation required for untrusted workloads: if you need to evaluate
  untrusted code or generated programs, run them in a hardened external
  boundary such as a dedicated VM or container with least-privilege filesystem,
  network, and credential access, plus OS-level controls such as seccomp,
  AppArmor, SELinux, or equivalent platform isolation.
- Adapter and store privileges matter: file, network, Redis, and backend store
  integrations should run with only the minimum credentials and network access
  required for the calling application.

## Disclosure Policy

We follow coordinated disclosure with a default 90-day window.

- Please keep reports private while we investigate and prepare a fix.
- We will coordinate on disclosure timing if a fix is ready earlier.
- If remediation needs more time, we may request an extension by mutual
  agreement.
- If no extension is agreed, we expect public disclosure no later than 90 days
  after initial report receipt.
