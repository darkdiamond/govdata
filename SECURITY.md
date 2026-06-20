# Security Policy

## Reporting a vulnerability

Please report security vulnerabilities **privately** — do not open a
public GitHub issue.

Use GitHub's private vulnerability reporting:
**[Report a vulnerability](https://github.com/darkdiamond/govdata/security/advisories/new)**
(the *Security* tab → *Report a vulnerability* button).

We aim to acknowledge reports within a few days and will coordinate a
fix and disclosure timeline with you.

## Scope

This project runs an AI agent that executes model-generated `bash` and
`python` as part of building each page. The threat model and a
**known, accepted risk** at the sandbox boundary are documented in
[`CLAUDE.md`](CLAUDE.md) (see the "Sandbox boundary" note): in
production the agent's tool processes run as subprocesses in the builder
container with a scrubbed environment, private workdirs, and per-command
timeouts, but they can reach the GCP metadata server. The service
account is deliberately kept minimal to bound the blast radius.

Reports that demonstrate a way to escalate beyond that documented
boundary — or any leak of secrets, credentials, or user data — are in
scope and very welcome.

## Supported versions

This is a continuously deployed project; security fixes target the
`main` branch. There are no long-term-support release branches.

## Secrets

All credentials are injected at runtime via environment variables and
Google Secret Manager — none are committed to the repository. If you
ever find a secret committed to git history, please report it privately
using the link above.
