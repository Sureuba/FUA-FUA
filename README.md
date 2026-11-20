# Hackathon Template

Starter for a team hackathon with Claude Code: spec-first, issue-per-branch, `agent-skills` plugin, session handoffs.

## Use it
1. `cp -R hackathon-template <new-project> && cd <new-project>` (drop any `.git`, then `git init`).
2. Create the GitHub repo, push `main`.
3. Open Claude Code; accept the `addyosmani/agent-skills` marketplace prompt (config in `.claude/settings.json`).
4. Run skills in order: `idea-refine` → `docs/ideas/` · `spec-driven-development` → `SPEC.md` · `planning-and-task-breakdown` → `tasks/plan.md` + GitHub issues.
5. Fill every `TODO` in `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`. Add `.github/workflows/ci.yml`.
6. Repo settings (replace `OWNER/REPO`):
```bash
gh api -X PATCH repos/OWNER/REPO -f allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false -F delete_branch_on_merge=true
```
   Then protect `main` (PR required, no force push) in Settings → Branches.
7. Each teammate: `mkdir -p handoffs/<github-handle>/archive`.

`.claude/settings.json` turns off heavier skills (security, shipping, ADRs, etc.) and asks before `git push` / `gh pr merge`. Edit `skillOverrides` per project.

## Blocker process
- Every issue uses `.github/ISSUE_TEMPLATE/task.md`: **Blocked by** and **Blocks** list issue numbers.
- **Checkpoint** issues (`checkpoint` label) are blocked by every issue in their phase; close one only after the go/no-go criteria pass.
- Blocked work builds against fixtures until the blocker merges. A blocker that slips: comment on the issue, add the `blocked` label, tell the team.
- `gh issue list --label blocked` shows everything stuck. Assign with `gh issue edit <N> --add-assignee <handle>`.
