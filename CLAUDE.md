@AGENTS.md

## Claude Code specifics
- Before starting work, read the GitHub issue (`gh issue view <N>`) and only the spec section it links.
- Skills come from the `agent-skills` plugin (`.claude/settings.json`). If a built-in Claude Code skill or slash command does the same job (`/code-review`, `/simplify`, `/security-review`, …), **use the `agent-skills` one instead**. Use them for these situations:

| When | Use |
|---|---|
| Starting/implementing an issue | `agent-skills:incremental-implementation` |
| Logic, any bug fix | `agent-skills:test-driven-development` |
| Building UI (controls, views, layout) | `agent-skills:frontend-ui-engineering` |
| Failing test, broken build, wrong output | `agent-skills:debugging-and-error-recovery` |
| Any library / API / data-format call | `agent-skills:source-driven-development` (check official docs, don't guess) |
| Perf budgets (TODO: list yours) | `agent-skills:performance-optimization` (measure first) |
| CI workflow, deploy | `agent-skills:ci-cd-and-automation` |
| Reviewing a teammate's PR | `agent-skills:code-review-and-quality` |
| Before opening a PR | `agent-skills:code-review-and-quality`, run in an `agent-skills:code-reviewer` subagent (fresh context) on `git diff main...HEAD`; fix its findings first. Not the built-in `/code-review`. |
| Commits, branches, PRs | `agent-skills:git-workflow-and-versioning` (branch/PR rules in `CONTRIBUTING.md` win) |
- Personal overrides go in `CLAUDE.local.md` (gitignored), not here.
