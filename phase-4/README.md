# Phase 4 — Frameworks and patterns

**Goal:** know which framework to reach for and why — and *feel* what a framework adds and hides versus the loop you hand-wrote in Phase 3.

**Ship deliverable (from the roadmap):** rebuild the **exact** Phase 3 research agent on the **Claude Agent SDK**, then compare lines of code, robustness, and behavior against the hand-rolled version.

> **Status: 🚧 in progress (1/9).** Sequence confirmed. Exercises 04–08 (the *Building Effective Agents*
> patterns) are built in **plain Anthropic API** on purpose — they're workflows, and a framework would hide
> the orchestration they're meant to teach. Exercise 09 adds **LangGraph** for a true 3-way comparison.

## Progress — 1 of 9

| # | Deliverable | Status |
|---|---|---|
| 01 | [`01_sdk_hello.py`](01_sdk_hello.py) — SDK hello-world: the simplest `query()`, the typed message stream, cost computed for you | ✅ shipped |
| 02 | `02_research_agent_sdk.py` — **the ship**: port Phase 3's research agent (web_search + fetch_url + write_file) to the SDK | ⏳ next |
| 03 | `03_sdk_vs_scratch.md` — the comparison: LOC, robustness, behavior; what the framework adds and what it hides | ⏳ pending |
| 04 | `04_prompt_chaining.py` — sequential LLM calls with a gate between them | ⏳ pending |
| 05 | `05_routing.py` — a classifier sends input to a specialized handler | ⏳ pending |
| 06 | `06_parallelization.py` — fan-out, then vote/aggregate | ⏳ pending |
| 07 | `07_orchestrator_workers.py` — central LLM dispatches subtasks to workers | ⏳ pending |
| 08 | `08_evaluator_optimizer.py` — generate → critique → refine (the Phase 3 self-critique, framed as a pattern) | ⏳ pending |
| 09 | `09_langgraph_research_agent.py` — breadth: the same agent on **LangGraph**, to feel graph-based control vs the SDK | ⏳ pending |

## The one idea behind this phase

Phase 3 proved an agent is *"an LLM call wrapped in a `while` loop."* You wrote that loop by hand. Phase 4 asks: **now that you've felt the loop, what does a framework actually buy you?**

The answer splits cleanly, and the exercise order reflects it:

- **For agent loops (open-ended, LLM-driven), a framework earns its keep.** It runs the loop, manages context, retries, streams, and wires tools for you. That's exercises 01–03 (Claude Agent SDK) and 09 (LangGraph).
- **For workflows (deterministic chains), you mostly don't need a framework at all.** The five *Building Effective Agents* patterns are orchestration logic — `if`/`for`/function calls around plain API calls. Seeing them in ~40 lines of pure Python each is the point. That's exercises 04–08.

This is the central lesson of Anthropic's [*Building Effective Agents*](https://www.anthropic.com/engineering/building-effective-agents): **most things people call "an agent" should have been a workflow.** Phase 4 makes that concrete by building both kinds side by side.

## Run order

```bash
export PATH="$HOME/.local/bin:$PATH"

# Exercise 01 ✅ — Claude Agent SDK hello-world (no while loop, async, cost computed for you)
uv run phase-4/01_sdk_hello.py
uv run phase-4/01_sdk_hello.py "Explain what an agent loop is in two sentences."
```

## What Exercise 01 adds: the SDK hello-world

The entire file is **one `query()` call** — and there is no `while` loop in it. That absence *is* the lesson. Side by side with what you wrote before:

| In Phase 1–3 you… | In the Agent SDK you… |
|---|---|
| called `client.messages.create(...)` **synchronously** and read `response.content` | `async for message in query(prompt, options)` — the SDK is **async-first** |
| wrote the `while` loop, appended tool results, checked `stop_reason` | the SDK runs the loop internally; you just consume the messages it yields |
| indexed `response.content[0].text` | pattern-match typed objects: `AssistantMessage` (with `TextBlock`s) → `ResultMessage` |
| kept a `PRICES` table and multiplied tokens by hand every iteration | read `ResultMessage.total_cost_usd` / `usage` / `num_turns` — **the framework tallied it for you** |

`ClaudeAgentOptions` is the SDK's single config object — the rough analogue of the kwargs you passed to `messages.create()` (`model`, `system_prompt`), but it also carries the knobs a *whole agent* needs: `allowed_tools`, `mcp_servers`, `permission_mode`, `hooks`, `cwd`. Exercise 02 will use `mcp_servers` to register the three Phase 3 tools.

### The surprise on turn one (the key observation)

Ask the hello-world to say hello and it replies *"Ready to continue your **learn-ai** project…"* — even though our system prompt only said "You are a concise teaching assistant." **The Agent SDK is project-aware by default**: it *is* Claude Code under the hood, so it picks up the working directory and reads your `CLAUDE.md`. That's the framework doing things you never asked it to — the exact opposite of the raw API, where the model sees *only* what you put in `messages`. It's convenient (an agent that knows its repo) and it's a tax (more input context = higher, variable cost). This is "what the framework adds and hides," made concrete before you've written a single tool.

## Concepts (the new Phase 4 vocabulary, continuing from Phase 3's 24)

| # | Concept | One-line |
|---|---|---|
| 25 | **Agent framework** | A library that runs the agent loop *for* you (vs. the loop you hand-wrote in Phase 3). |
| 26 | **Claude Agent SDK** (`claude-agent-sdk`) | Anthropic's agent framework — wraps the Claude Code harness (bundled Node CLI), MCP-first, with built-in tools, hooks, permissions. |
| 27 | **`query()`** | The SDK's entry point — an **async generator** that yields the conversation's messages as the agent runs. |
| 28 | **`ClaudeAgentOptions`** | The one config object: `model`, `system_prompt`, `allowed_tools`, `mcp_servers`, `permission_mode`, `cwd`, `hooks`. |
| 29 | **Typed messages** (`AssistantMessage` / `ResultMessage`) | You consume structured message objects, not raw `response.content`. `ResultMessage` carries cost/usage/turns. |
| 30 | **In-process MCP server** | How the SDK takes *your* Python functions as tools — `@tool` + `create_sdk_mcp_server`, referenced as `mcp__<server>__<tool>`. (Used in Ex 02.) |
| 31 | **Async-first** | The SDK forces `async`/`await` + `asyncio.run`, unlike the synchronous code of Phases 1–3. |

## Gotchas

- **The SDK is project-aware by default.** It loads the working directory and `CLAUDE.md` — so a "hello world" answer references your repo, and input cost is higher than a bare `messages.create()` call. If you ever want a hermetic agent (no repo context), you'd configure that explicitly; the *default* is "knows everything about where it's running."
- **A Haiku hello-world cost $0.003–0.013, and it varied run to run.** Phase 1's hello-world was a fraction of a cent. The gap is the injected harness/project context (and prompt-cache read vs. write across runs — repeated runs are cheaper). The framework's convenience has a baseline token tax.
- **`claude-agent-sdk` is a heavy install.** One `uv add` pulled in **17 packages (~66 MiB)** — it bundles a Node-based Claude Code CLI plus `mcp`, `starlette`, `uvicorn`, `cryptography`. Contrast Phase 3's agent: ~200 lines on `anthropic` + `httpx`. Weight-for-convenience is the trade Exercise 03 measures.
- **Don't drain only the `ResultMessage`.** A throwaway probe that iterated `query()` but only inspected `ResultMessage` intermittently raised `Claude Code returned an error result: success` and reported zero cost. Iterating and handling *each* message type (as the shipped script does) is stable. Lesson: consume the SDK's full message stream, not just the final frame.
