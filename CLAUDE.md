# learn-ai — rules for AI agents

This is a **learning workspace**, not a production codebase. Optimize every change for pedagogical clarity over cleverness.

## The README rule (most important)

Every phase has its own `phase-N/README.md`. **Keep it current as we go.**

When you do any of the following, update the corresponding `phase-N/README.md` in the same turn — never defer:

| When you… | Update README to… |
|---|---|
| **Ship, start, or finish any exercise (progress changes)** | **Update the progress/status markers in the SAME turn — see "The progress rule" below. This is non-negotiable.** |
| Add a new exercise file in `phase-N/` | Add it to the run-order block + the per-file concept map |
| Introduce a new concept the user hasn't seen | Add a numbered entry to that phase's concepts list (with a tight one-paragraph explanation) |
| Hit and fix a bug together (`max_tokens` truncation, eval scoreboard lying, dependency snags) | Add it to the gotchas section with the lesson, not just the fix |
| Change file order, file names, or run commands | Update the run-order block immediately so users following along don't get stuck |
| Refactor or rename a Python file | Grep for references in all README/CLAUDE.md files and update links |
| Decide to swap a library/provider (e.g. sentence-transformers → fastembed) | Note it and *briefly* say why — the lesson matters more than the change |

Root `README.md` is a **brief overview only** — setup steps, the phase status table, and project structure. It must not duplicate phase-specific content; link to phase READMEs instead.

### The progress rule (added 2026-06-24, by user request)

Progress must always be visible and current. **In the same turn that progress changes** (an exercise is started, shipped, or finished; a phase flips status), update ALL THREE of these — never defer to "later" or a cleanup pass:

1. **`phase-N/README.md` → the `## Progress` block** — the at-a-glance table of that phase's deliverables with ✅ shipped / ⏳ next / ⏳ pending markers, and the "X of Y" count in the heading.
2. **Root `README.md` → the phase status table** — keep the granular count current (e.g. `🚧 in progress (4/6)`), not just a vague `in progress`.
3. **Root `README.md` → the project-structure tree** — add new files as they're created; don't let the tree fall behind the directory.

Why: the user follows along across many sessions and relies on the READMEs to answer "where are we?" without re-reading code. A stale tree or a vague status is a real failure, not a cosmetic one. If you start an exercise, mark it ⏳/in-progress immediately so the work is never invisible.

## Style

- **Teach, don't just ship.** Every Python file's docstring should explain *why* the exercise exists, not just what it does.
- **Comments on WHY, not WHAT.** The user is learning — explain non-obvious choices (forced tool use, max_tokens headroom, normalized embeddings).
- **One concept per file when possible.** Phase 1's split (count → stream → quiz → eval) is the model. Resist combining.
- **Default to Claude Haiku 4.5** in code examples. Cheap, fast, plenty capable for learning. Note where Sonnet would be the right upgrade.
- **Anthropic-first.** When introducing alternatives (Voyage, OpenAI, fastembed), say so explicitly — don't quietly drift.

## Anti-patterns to avoid

- ❌ Building Phase N+1 deliverables before Phase N's README is current.
- ❌ Adding a third dependency without justifying it in the phase README.
- ❌ Silently catching exceptions in teaching code — surface failures loudly so the user can learn from them.
- ❌ Long docstrings that describe what every line does. Short docstring at top, occasional `# Why:` comment inline.
- ❌ Writing `CONCEPTS.md` or other variants. Each phase has exactly one `README.md`.

## When the user asks a substantive conceptual question mid-phase

If they ask "why does X work?" or "what's the difference between A and B?" and the answer is genuinely *new material* (not in the current phase README), add the answer to the phase README **after** answering them in chat. The chat answer was for now; the README is for future-them.

## Verification before declaring "done"

Before marking a phase exercise complete:
1. The Python file runs end-to-end (or a clear reason why it can't, e.g. needs API credits).
2. The phase README's run-order block reflects the current state.
3. The phase README's concept list covers everything the file introduces.
4. Any gotchas hit during the session are recorded.

## Git etiquette (not yet relevant — no repo init)

When the user eventually `git init`s this directory, default to one logical commit per phase exercise + one for the corresponding README updates. Don't bundle "build exercise + fix earlier bug" into one commit.
