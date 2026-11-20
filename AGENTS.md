# AGENTS.md

Context for AI coding agents (Claude Code, Cursor, Codex, Copilot…) and humans. Keep this file short; details live in the linked docs.

## Project
<TODO: one paragraph. What it is, who it is for, core interaction.>

**Source of truth:** `SPEC.md` (success criteria, boundaries). Why we chose this direction: `docs/ideas/`. Plan + issue index: `tasks/plan.md`.

## Architecture
<TODO: data flow diagram, one line per stage. Note deploy target and "no backend" style constraints.>

## Layout
<TODO: one line per top-level folder.>

## Commands
```bash
# TODO: install / test / lint / build / dev commands
```

## Conventions
<TODO: units in names, naming, language strictness, where logic may live.>

## Workflow (enforced)
- Every change: **GitHub issue → branch `<issue#>-<short-desc>` → PR with `Closes #N` → checks pass → squash merge** (no approval required). `main` is protected; never push to it directly.
- **Stay inside the issue's "Files owned by this issue" list.** Touching others' files → say so in the PR.
- Shared contracts (`SPEC.md` → Data Contract) change only with team agreement, never inside a feature PR.
- New ideas → `SPEC.md` "Out of Scope (Deferred)". Don't build features that aren't in the spec or an issue.
- **Agents:** commit freely on the issue branch (small, frequent commits). **Never `git push` or `gh pr merge` unless the user explicitly says so in this session.** Opening a PR (`gh pr create`) for an already-pushed branch is fine. (Claude Code also asks for confirmation via `.claude/settings.json`.)
- See `CONTRIBUTING.md`.

## Session handoffs
- When the session reaches **~40–50% context** (or before stopping mid-task), **stop and write a handoff** from `handoffs/TEMPLATE.md` to `handoffs/<github-handle>/<YYYY-MM-DD-HHMM>-<issue#>-<slug>.md`. Then start a fresh session.
- Be precise: exact files/lines, commands, verification results, decisions + reasons, failed attempts, ordered next steps. The next session must be able to continue from the file alone.
- A new session on an issue first reads the **newest** handoff for that issue. Handoffs are **local only** (gitignored; never commit them). When the issue closes, move its handoffs to `handoffs/<github-handle>/archive/`. Only write in your own folder.

## Testing
- Every exported function has a test. Never delete, skip or weaken a failing test to get green. Fix the code or flag it.

## Never
- Commit secrets, `.env`, files over 25 MB, or raw datasets.
- Add a dependency without asking the team.
- <TODO: project-specific never-rules.>
