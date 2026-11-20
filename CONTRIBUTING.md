# Contributing

<TODO: N-hour hackathon, N people, one `main>. These rules exist so we never block each other.

## The rules
1. **Never push directly to `main`.** Every change goes through a pull request.
2. **One issue → one branch → one PR.** Pick an issue from the <TODO: project board / issues link>, assign yourself, then branch.
3. **Branch name = `<issue-number>-<short-description>`**, kebab-case, from the latest `main`:
   ```bash
   git switch main && git pull
   git switch -c 8-short-description
   ```
4. **PR title** = issue title; **PR description** starts with `Closes #<issue-number>` so the issue closes on merge.
5. **Stay inside your issue's "Files owned by this issue" list.** If you must touch another file, say so in the PR description and ping that issue's owner.
6. **Small PRs, merged often.** Rebase on `main` before opening (`git pull --rebase origin main`).
7. **Check before opening a PR:** <TODO: test / lint / build commands>
8. **Review:** approvals are **not required** (hackathon speed). You may squash-merge your own PR once checks pass, but ask a teammate to look at anything touching shared contracts. **Squash merge only.** `main` is protected (PR required, no direct or force pushes). Branches auto-delete after merge. (See README setup for the `gh` commands.)

Using an AI coding agent? It reads [`AGENTS.md`](AGENTS.md) / [`CLAUDE.md`](CLAUDE.md). Keep those short and up to date when conventions change.

## AI session handoffs (~40–50% context)
Long agent sessions degrade. When yours hits **~40–50% context** (check with `/context` in Claude Code), have the agent write a handoff and start a fresh session.
- **Template:** [`handoffs/TEMPLATE.md`](handoffs/TEMPLATE.md)
- **Where:** your own folder, `handoffs/<github-handle>/<YYYY-MM-DD-HHMM>-<issue#>-<slug>.md` (no conflicts)
- **Start the next session with:** "Read `handoffs/<handle>/<file>` and continue."
- **Local only:** `handoffs/` is gitignored (except the template). Create your folder yourself (`mkdir -p handoffs/<github-handle>/archive`); when an issue closes, move its handoffs to `archive/`.

## Commit messages
Short, imperative, reference the issue: `Add feature X (#8)`.

## Blocked?
- An issue's **Blocked by** list shows what must merge first. Build against fixtures until it does.
- Need a change to a shared contract? Raise it with the team first.
- New idea mid-build? Add it to **Out of Scope (Deferred)** in `SPEC.md`. No new P0 features after the mid checkpoint.

## Never commit
Secrets, `.env`, files over 25 MB, raw datasets.

## Where things are
| Read | For |
|---|---|
| [`SPEC.md`](SPEC.md) | What we're building (source of truth) |
| [`tasks/plan.md`](tasks/plan.md) | Timeline, phases, issue index, critical path |
| [`docs/ideas/`](docs/ideas/) | Why we chose this direction |
