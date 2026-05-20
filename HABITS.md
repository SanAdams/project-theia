# Claude Code Habits

## Session Habits (Phase 2)

| #   | Habit                         | How                                                                                   |
| --- | ----------------------------- | ------------------------------------------------------------------------------------- |
| 1   | **Plan before coding**        | `Shift+Tab` to enter plan mode. Say "execute" to proceed.                             |
| 2   | **One goal per segment**      | `/clear` when switching tasks.                                                        |
| 3   | **Compact at 60%**            | `/compact but keep: [.env decisions, current task, confirmed root causes]`            |
| 4   | **Diagnose before debugging** | `/diagnose` — no exceptions.                                                          |
| 5   | **Verify each task**          | Prompt: "Don't mark done until 95% confident it works. Don't move on until verified." |
| 6   | **Exit early**                | `Escape` the moment Claude goes wrong. Reprompt.                                      |
| 7   | **Challenge outputs**         | "Scrap that, try a more elegant approach."                                            |

## Advanced (Phase 4 — add when basics are habit)

| #   | Habit                      | How                                                                                     |
| --- | -------------------------- | --------------------------------------------------------------------------------------- |
| 1   | **Sub-agents**             | "Use sub-agents to handle [X] and [Y] in parallel." Run data-heavy ones on Haiku.       |
| 2   | **Git worktrees**          | `claude-worktree feature-name` — isolated branch per session, merge when done.          |
| 3   | **Notification hooks**     | `/hooks` — configure a sound for when Claude finishes a long task.                      |
| 4   | **Context7 MCP**           | Prompt: "Use Context7 to check current docs for [library] before implementing."         |
| 5   | **`/loop` for monitoring** | "Every 5 minutes, check the deployment status." Persists up to 3 days within a session. |

## Quality Gates (Phase 3)

| Gate          | When                                                           | Command                         |
| ------------- | -------------------------------------------------------------- | ------------------------------- |
| Quick review  | After every meaningful change                                  | `/review`                       |
| Deep review   | Before merging anything high-stakes                            | `/ultrareview` ($5–20)          |
| Hard problems | Architecture decisions, failed after 2 attempts, big refactors | Add `ultrathink` to your prompt |
