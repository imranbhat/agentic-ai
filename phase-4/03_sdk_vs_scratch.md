# Exercise 03 — Hand-rolled vs. Claude Agent SDK: the comparison

The Phase 4 deliverable from the roadmap, in full: take the *same* research agent built two ways —
[`phase-3/05_research_agent.py`](../phase-3/05_research_agent.py) (you wrote the loop) and
[`phase-4/02_research_agent_sdk.py`](02_research_agent_sdk.py) (the SDK runs the loop) — and weigh them on
**lines of code, robustness, and behavior**. Every number below is measured from those two files and from real
runs on the identical question, not estimated.

---

## TL;DR

> The framework saved **code**, not **cost** or **quality**. On the same task the SDK agent took ~half the
> code lines, produced the same trajectory, and cost essentially the same dollar amount. What it bought was
> *deleting the loop you'd already learned to write* — plus retries, cost accounting, a turn guard, and MCP
> tool wiring for free. What it cost was ~66 MiB and 17 dependencies, a Node runtime, async-first code, and a
> pile of default behavior you now have to *know about* (project-awareness, a hidden system prompt) because you
> no longer control it directly.
>
> **Reach for the framework once you've felt the loop and want to stop maintaining it. Keep hand-rolling while
> the loop itself is the thing you're trying to understand or tightly control.**

---

## 1. Lines of code

Measured with an AST-based line classifier over both files:

| File | Total | Code (~) | Comments | Docstrings | Blank |
|---|---:|---:|---:|---:|---:|
| `phase-3/05_research_agent.py` (hand-rolled) | 384 | ~250 | 26 | 57 | 51 |
| `phase-4/02_research_agent_sdk.py` (SDK) | 241 | ~133 | 35 | 41 | 32 |

**~250 → ~133 code lines (~47% less).** But the raw total undersells it, because the two files don't have the
same *shape*:

- The **three tools are ~the same in both** (~70 lines each) — that code didn't move, because the SDK can't
  write your tools for you.
- Almost the entire difference is **loop machinery**. In Phase 3 that's `run_agent`'s body + the `_result`,
  `_print_summary`, and `_print_trace` helpers — roughly **150 lines** of: the `for` loop, appending assistant
  content, dispatching tools, building `tool_result` blocks, the unknown-tool guard, the `PRICES` table and
  per-iteration token math, the trajectory recorder, and the trace dumper.
- In the SDK port, that same surface is **~40 lines** of `run_agent` — `query()` plus an `async for` that
  renders the messages. The cost summary is three fields off `ResultMessage`; the trace is the message stream
  itself.

So the honest framing isn't "47% smaller file." It's: **the ~150 lines that were purely *agent plumbing*
collapsed to ~40, and every line that was *your problem* (the tools) stayed exactly the same size.**

---

## 2. Dependencies & install weight

| | Phase 3 hand-rolled | Phase 4 SDK |
|---|---|---|
| Direct deps the agent needs | `anthropic`, `httpx`, `beautifulsoup4`, `ddgs` (+ `rich`, `dotenv`) | all of those **plus** `claude-agent-sdk` |
| What the new dep dragged in | — | **17 packages, ~66 MiB** (`mcp`, `starlette`, `uvicorn`, `cryptography`, …) |
| Runtime beyond Python | none | **Node.js** — the SDK shells out to a bundled Node-based Claude Code CLI |

The hand-rolled agent is `anthropic` + an HTTP client + an HTML parser. The SDK agent ships a whole agent
*harness* — a second language runtime, an MCP stack, even a web server (`uvicorn`/`starlette`) — to run three
Python functions in a loop. That weight buys real capability (hooks, permissions, subagents, built-in tools we
didn't use), but for *this* agent it's almost all unused surface.

---

## 3. Behavior (measured, same question)

Both agents were run on the exact same prompt: *"What is the ReAct prompting pattern and who introduced it?"*

| | Phase 3 hand-rolled | Phase 4 SDK |
|---|---|---|
| Trajectory | search → fetch ×3 → write → summary | **search → fetch ×3 (parallel) → write → summary** |
| Loop count | 4 iterations / 6 tool calls | 6 `num_turns` / 6 tool calls |
| Wall time | (comparable) | ~21 s |
| **Cost** | **$0.0184** | **$0.0194** |
| Output | cited markdown report, Yao et al. 2022 | cited markdown report, Yao et al. 2022 |

Same shape, same answer, ~5% cost difference (well within run-to-run noise — agents are non-deterministic, the
Phase 3 lesson). Note the counters aren't directly comparable: Phase 3 counts *model calls* (4); the SDK's
`num_turns` (6) counts *message exchanges*. Compare trajectory and cost, not the two integers.

**The framework did not make the agent cheaper, faster, or smarter.** Identical model, identical tools,
identical prompt → identical behavior. That's the point of porting the *exact* agent: it isolates the framework
so you can see it changes the *developer's* experience, not the *agent's*.

---

## 4. What the framework ADDS (for free)

Everything here is something you hand-wrote (or skipped) in Phase 3 and got for free in Phase 4:

| You got… | In Phase 3 it was… |
|---|---|
| The agent loop | a `for` loop you wrote and had to terminate correctly |
| `max_turns=15` loop guard | a hand-written `range(max_iterations)` cap |
| `max_budget_usd` cost ceiling | nothing — you'd have to add it |
| Cost / usage / turn accounting | a `PRICES` table + manual token math every iteration |
| Tool dispatch + error relay | your own `TOOLS_BY_NAME` lookup, `try/except`, and `tool_result` assembly |
| Parallel tool execution | the model *asked* for parallel fetches; you executed them in a plain `for` |
| Retries on transient API errors | nothing — a 529 would just raise |
| MCP-native tools | not applicable — but it's the on-ramp to external MCP servers (Phase 5) |
| Permissions, hooks, subagents, built-in Bash/Read/Edit | none of it exists in the hand-rolled version |

---

## 5. What the framework HIDES or IMPOSES

The flip side — convenience you pay for in control and surprise:

| Cost | Why it bites |
|---|---|
| **The loop is invisible** | The thing Phase 3 *taught* is now behind `query()`. Great once you know it; a black box if you don't. |
| **Async-first** | `async`/`await` + `asyncio.run` is mandatory, even for a one-shot. Phases 1–3 were synchronous. |
| **Project-awareness by default** | Left at defaults (Exercise 01), the SDK reads your `CLAUDE.md` and cwd — the agent silently knows things you didn't put in the prompt. We had to *opt out* with `setting_sources=[]` for a faithful port. |
| **A hidden system prompt** | The Claude Code preset ships its own instructions; a plain-string `system_prompt` *replaces* it, but you have to know that to reason about behavior. |
| **Heavier failure surface** | A bare-`ResultMessage` probe raised `Claude Code returned an error result: success` — a failure mode that simply can't exist in the hand-rolled version. More moving parts = more novel failures. |
| **66 MiB + Node** | A second runtime and 17 packages to install, pin, and trust, to run three Python functions. |

---

## 6. Robustness

Not "which is more robust" — they're robust in *different directions*.

- **The SDK is more robust to the boring failures.** Transient API errors get retried; a runaway agent is
  capped by `max_turns`/`max_budget_usd`; tool errors are dispatched and relayed without you writing the
  plumbing. These are the failures that bite in production, and the framework handles them so you can't forget to.
- **The hand-rolled agent is more *legible* under failure.** When it misbehaves, the cause is in ~200 lines you
  wrote and can read top to bottom — there's a `--trace` flag that dumps the entire message list. The SDK's
  failures can originate in the bundled CLI, the MCP layer, or the async plumbing — more surface you don't own,
  and the `error result: success` quirk is exactly that kind of opaque failure.

Rule of thumb: the SDK wins on *handling* failures, the hand-rolled version wins on *understanding* them.

---

## 7. When to reach for which (the Phase 4 goal, in one paragraph)

**Hand-roll when the loop is the point** — when you're learning what an agent is (Phase 3's entire purpose),
when you need tight, auditable control over every turn, or when the task is simple enough that a 200-line file
on `anthropic` + `httpx` is *less* to reason about than a 66-MiB harness. **Reach for the Claude Agent SDK once
the loop is settled and you want to stop maintaining it** — when you want retries, budgets, permissions, hooks,
subagents, and built-in tools without writing them, when you're going MCP-first (consuming external tool
servers), or when "an agent that already knows how to read files and run bash in my repo" is a feature, not a
surprise. The framework is not a smarter agent; it's *less code you have to own*. You only know whether that
trade is worth it because you wrote the loop by hand first — which is exactly why the roadmap put Phase 3 before
Phase 4.

---

## Appendix — reproduce the numbers

```bash
export PATH="$HOME/.local/bin:$PATH"

# Same question, both agents:
uv run phase-3/05_research_agent.py "What is the ReAct prompting pattern and who introduced it?"
uv run phase-4/02_research_agent_sdk.py "What is the ReAct prompting pattern and who introduced it?"

# LOC breakdown (AST line classifier): see the table in §1 — measured at ship time.
# Dependency weight: `uv add claude-agent-sdk` reported "Installed 17 packages" (~66 MiB).
```

Costs and turn counts vary run to run (non-deterministic agents) — expect the *shape* to hold, not the exact
cents.
