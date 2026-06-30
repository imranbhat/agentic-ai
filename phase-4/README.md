# Phase 4 — Frameworks and patterns

**Goal:** know which framework to reach for and why — and *feel* what a framework adds and hides versus the loop you hand-wrote in Phase 3.

**Ship deliverable (from the roadmap):** rebuild the **exact** Phase 3 research agent on the **Claude Agent SDK**, then compare lines of code, robustness, and behavior against the hand-rolled version.

> **Status: 🚧 in progress (4/9).** Sequence confirmed. Exercises 04–08 (the *Building Effective Agents*
> patterns) are built in **plain Anthropic API** on purpose — they're workflows, and a framework would hide
> the orchestration they're meant to teach. Exercise 09 adds **LangGraph** for a true 3-way comparison.

## Progress — 4 of 9

| # | Deliverable | Status |
|---|---|---|
| 01 | [`01_sdk_hello.py`](01_sdk_hello.py) — SDK hello-world: the simplest `query()`, the typed message stream, cost computed for you | ✅ shipped |
| 02 | [`02_research_agent_sdk.py`](02_research_agent_sdk.py) — **the ship**: Phase 3's research agent, ported to the SDK (same 3 tools, no hand-written loop) | ✅ shipped |
| 03 | [`03_sdk_vs_scratch.md`](03_sdk_vs_scratch.md) — the comparison: LOC, robustness, behavior; what the framework adds and what it hides | ✅ shipped |
| 04 | [`04_prompt_chaining.py`](04_prompt_chaining.py) — sequential LLM calls with a **gate** between them (the first BEA pattern) | ✅ shipped |
| 05 | `05_routing.py` — a classifier sends input to a specialized handler | ⏳ next |
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

# Exercise 02 ✅ — THE SHIP: Phase 3's research agent, rebuilt on the SDK (same 3 tools, loop deleted)
uv run phase-4/02_research_agent_sdk.py "What is the ReAct prompting pattern and who introduced it?"
uv run phase-4/02_research_agent_sdk.py "Compare RAG vs fine-tuning for keeping an LLM current" --model claude-sonnet-4-6
# reports are written to phase-4/reports/ (checked in as sample output)

# Exercise 04 ✅ — prompt chaining (BEA pattern #1): draft → GATE → translate. Plain anthropic, no framework.
uv run phase-4/04_prompt_chaining.py "a CLI tool that turns git history into a changelog"
uv run phase-4/04_prompt_chaining.py "a budgeting app for freelancers" --lang Spanish
uv run phase-4/04_prompt_chaining.py "a note-taking app" --max-words 10   # force the GATE to fail → step ③ skipped
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

## What Exercise 02 adds: the ship — port the research agent

A *faithful port* of [`phase-3/05_research_agent.py`](../phase-3/05_research_agent.py): **same three tools** (web_search via `ddgs`, fetch_url with the 6,000-char cap, write_file), **same system prompt**, **same kind of output** (a cited markdown report in [`phase-4/reports/`](reports/)). Exactly one thing is deleted — the hand-written agent loop. Put the two files side by side; the diff *is* Phase 4:

| Phase 3 — you own the loop | Phase 4 — the SDK owns it |
|---|---|
| `for iteration in range(max_iterations):` | `max_turns=15` — a config field |
| `response = client.messages.create(...)` | `async for message in query(...)` |
| append assistant content, then loop | the SDK appends and re-calls for you |
| run each tool, build `tool_result`, append | the SDK calls your `@tool` and feeds the result back |
| `if stop_reason == "end_turn": break` | the SDK decides when it's done |
| `PRICES` table + manual token math | `ResultMessage.total_cost_usd` |
| unknown-tool guard, error round-trip by hand | the SDK dispatches and relays tool errors |

**What you still write — and a framework can't:** the three tools. Tool *design* (bounded output, sanitized paths, useful return strings) is yours in every framework. That's the durable Phase 3 skill; the loop was the disposable part.

### Same behavior, measured (the early read on Exercise 03)

Run it on the exact Phase 3 question — *"What is the ReAct prompting pattern and who introduced it?"* — and you get the same trajectory and a near-identical bill:

```
search → fetch ×3 (in parallel) → write_file → 2-sentence summary
6 turns • ~21 s • $0.0194        (Phase 3 hand-rolled: 4 iters / 6 tool calls / $0.0184)
```

Nearly the same cost. The framework didn't make the agent cheaper or smarter — it made *you* write less code. That's the honest takeaway, and Exercise 03 will lay the two side by side in full.

### The faithful-port options (each a deliberate choice)

| Option | Why |
|---|---|
| `tools=[]` | Drop **all** built-in tools (Bash/Read/Edit/…). The agent has only our three, exactly like Phase 3. |
| `setting_sources=[]` | **Isolation** — do *not* load `CLAUDE.md`. This is the deliberate opposite of Exercise 01: here we want a clean agent that sees only the question, not the repo. |
| `system_prompt=<string>` | A plain string **replaces** the Claude Code preset with our research prompt. |
| `max_turns=15` | The SDK's built-in version of Phase 3's loop guard — a field, not a `for` range. |
| `permission_mode="bypassPermissions"` | Run non-interactively (our `write_file` tool touches disk; no approval prompts). |

### Deep dive: what is MCP, and how did we actually use it? (asked mid-phase)

Exercise 02 wrapped three plain Python functions in `create_sdk_mcp_server` — which raises a fair question: why
did three *local* functions suddenly need a "server"?

**MCP (Model Context Protocol) is an open standard for how an LLM app talks to a tool provider.** The analogy:
**MCP is USB-C for AI tools.** It defines one uniform plug — a standard format for "here are my tools (name +
description + input schema)," "call this tool with these args," and "here's the result." It solves the **M×N
explosion**: M apps × N tools would be M×N bespoke integrations; with MCP each tool is written once as a
*server* and each app speaks MCP once as a *client*, so it becomes M+N. Two roles: the **client/host** (the LLM
app — discovers tools, forwards them to the model, routes the calls) and the **server** (owns and executes the
tools).

**Phase 3 used no MCP.** The tools were hardwired into your loop, in two hand-written pieces:

```python
TOOL_DEFINITIONS = [{"name": "web_search", "input_schema": {...}}, ...]   # raw schema dicts
response = client.messages.create(..., tools=TOOL_DEFINITIONS)           # passed inline
fn = TOOLS_BY_NAME.get(block.name); result = fn(**block.input)           # YOUR loop dispatches
```

No protocol — just your dict → the API's `tools` param → a `tool_use` block → *your code* calls the function.

**Exercise 02 used MCP because the SDK is MCP-first** — it has no "raw tool dicts + dispatch table" path. The
only way to give it *your* functions is to package them as a server:

```python
@tool("web_search", "Search the web...", {"query": str})                 # generates the schema
server = create_sdk_mcp_server(name="research", tools=[web_search, ...])
options = ClaudeAgentOptions(mcp_servers={"research": server},
                             allowed_tools=["mcp__research__web_search", ...])  # namespaced
```

Now the **SDK** plays client: it asks your server "what tools do you have?", passes them to the model, and
routes `mcp__research__web_search` calls back to your function. The dispatch you wrote by hand in Phase 3 is
exactly what the SDK does for you, over MCP.

| | Phase 3 (no MCP) | Exercise 02 (MCP) |
|---|---|---|
| Tool schema | hand-written dict | `@tool` generates it |
| Who runs the function | **your loop**: `fn(**input)` | **the SDK**, via the MCP layer |
| Tool name | bare `web_search` | namespaced `mcp__research__web_search` |
| The interface | none — direct Python | MCP |

**The nuance that makes it feel like ceremony:** `create_sdk_mcp_server` builds an **in-process** server — it
runs *inside your script*, no subprocess, no network. You get the MCP *shape* without the MCP *cost*.

**Did we need MCP here? Honestly, no.** For three local functions, Phase 3's inline approach is simpler. We used
MCP only because the SDK imposes it as its universal tool door (built-in tools, your tools, and external servers
all enter the same way — uniformity is the benefit, a little ceremony is the price). **Where MCP actually pays
off** is the case we haven't hit: consuming *someone else's* tools — point the SDK at a GitHub or Slack MCP
server and get those tools with zero integration code. That's a **Phase 5** topic. In Phase 4 we only used the
"wrap my own functions" corner of MCP — the shape, not yet the payoff.

## What Exercise 03 adds: the comparison (read [`03_sdk_vs_scratch.md`](03_sdk_vs_scratch.md))

No new code — the roadmap's actual ask, written up: the two agents weighed on **lines of code, robustness, and
behavior**, with measured numbers from real runs. The one-line verdict:

> The framework saved **code**, not **cost** or **quality**. ~250 → ~133 code lines (the ~150 lines of *loop
> plumbing* collapsed to ~40; the tools — *your* problem — stayed the same size). Same trajectory, ~$0.0184 vs
> ~$0.0194 on the same question. You pay for it in 66 MiB + Node, async-first code, and default behavior you
> now have to *know about* rather than control.

**When to reach for which:** hand-roll while the loop is the thing you're learning or must tightly control;
reach for the SDK once the loop is settled and you'd rather not maintain retries, budgets, permissions, and MCP
wiring yourself. You can only judge that trade *because* you wrote the loop by hand first — which is why Phase 3
came before Phase 4. The full tables (what the framework adds, what it hides) are in the writeup.

## What Exercise 04 adds: prompt chaining (BEA pattern #1 — and the first *workflow*)

Exercises 01–03 were about an **agent** (the model drives an open-ended loop). Exercise 04 flips to the other
half of *Building Effective Agents*: a **workflow** — a fixed sequence of steps **you** wire in Python. No
while-loop, no tool use, no framework. Just `messages.create()` calls with control flow around them.

```
topic ──▶ ① draft blurb ──▶ ②  GATE  ──▶ ③ translate ──▶ done
              (LLM)        (pure Python)     (LLM)
                               │
                               └─ fails ──▶ STOP (skip the paid step ③)
```

**The one idea: the GATE is what makes this a chain.** Calling the model twice in a row is not prompt chaining
— the check *between* the calls is. The gate here is pure Python (`len(text.split())` + a hype-word set), which
is itself a lesson: **not every step needs an LLM.** A free check that stops a bad draft before the paid
translate call is the entire value proposition.

| Run | What you see |
|---|---|
| `"…changelog"` (defaults) | ① 31-word blurb → ② gate **passes** → ③ French translation. 2 LLM calls + 1 gate, **$0.0006**. |
| `"a note-taking app" --max-words 10` | ① 43-word blurb → ② gate **fails** (`too long`) → **chain stops**. Step ③ never runs — **$0.0003**, half the bill. |

That cost difference *is* the takeaway: the gate is a cheap guard that protects the expensive downstream step.

**Deliberate non-overlap with Exercise 08.** Here the gate's only job is to **stop**. Looping its feedback back
into step ① to *improve* the draft is a different pattern — generate→critique→retry, the
**evaluator-optimizer** (Exercise 08, and the descendant of Phase 3's self-critique). Keeping "gate that stops"
and "loop that fixes" separate is intentional: they're two different BEA patterns.

**When to reach for prompt chaining:** when a task cleanly decomposes into fixed subtasks and you'll trade a
little latency (more sequential calls) for higher accuracy per step — outline → check → write; generate →
verify → translate. **When not to:** if one call does the job, chaining is just added cost and latency.

## Concepts (the new Phase 4 vocabulary, continuing from Phase 3's 24)

| # | Concept | One-line |
|---|---|---|
| 25 | **Agent framework** | A library that runs the agent loop *for* you (vs. the loop you hand-wrote in Phase 3). |
| 26 | **Claude Agent SDK** (`claude-agent-sdk`) | Anthropic's agent framework — wraps the Claude Code harness (bundled Node CLI), MCP-first, with built-in tools, hooks, permissions. |
| 27 | **`query()`** | The SDK's entry point — an **async generator** that yields the conversation's messages as the agent runs. |
| 28 | **`ClaudeAgentOptions`** | The one config object: `model`, `system_prompt`, `allowed_tools`, `mcp_servers`, `permission_mode`, `cwd`, `hooks`. |
| 29 | **Typed messages** (`AssistantMessage` / `ResultMessage`) | You consume structured message objects, not raw `response.content`. `ResultMessage` carries cost/usage/turns. |
| 30 | **In-process MCP server** | How the SDK takes *your* Python functions as tools — `@tool` + `create_sdk_mcp_server`, referenced as `mcp__<server>__<tool>`. |
| 31 | **Async-first** | The SDK forces `async`/`await` + `asyncio.run`, unlike the synchronous code of Phases 1–3. |
| 32 | **`@tool` return shape** | A custom tool receives `args` (a dict) and must return `{"content": [{"type": "text", "text": ...}]}`. That text is all the model sees — same as a Phase 3 tool's return string. |
| 33 | **`max_turns` (built-in loop guard)** | The SDK config field that replaces Phase 3's hand-written max-iteration cap. Also `max_budget_usd` for a built-in cost ceiling. |
| 34 | **Isolation (`setting_sources=[]`)** | Tell the SDK to load *no* project settings — so the agent does **not** read `CLAUDE.md`. The deliberate opposite of Exercise 01's default project-awareness. |
| 35 | **`permission_mode`** | Governs whether tool calls need approval. `"bypassPermissions"` runs non-interactively; the default would prompt for non-allowlisted tools. |
| 36 | **Prompt chaining** (BEA pattern #1) | A *workflow*: a fixed sequence of LLM calls you wire in Python, each step feeding the next, with a **gate** between them. Not an agent — *you* own the control flow. |
| 37 | **Gate** | A cheap check *between* chain steps that decides whether to continue. Often pure Python (no LLM). The thing that distinguishes a chain from "calling the model twice." |
| 38 | **Workflow (vs agent), made concrete** | Phase 3 built agents (model drives the loop). Exercises 04–08 build workflows (code drives the steps). Most "agents" should have been workflows — this is where you feel why. |

## Gotchas

- **The SDK is project-aware by default.** It loads the working directory and `CLAUDE.md` — so a "hello world" answer references your repo, and input cost is higher than a bare `messages.create()` call. If you ever want a hermetic agent (no repo context), you'd configure that explicitly; the *default* is "knows everything about where it's running."
- **A Haiku hello-world cost $0.003–0.013, and it varied run to run.** Phase 1's hello-world was a fraction of a cent. The gap is the injected harness/project context (and prompt-cache read vs. write across runs — repeated runs are cheaper). The framework's convenience has a baseline token tax.
- **`claude-agent-sdk` is a heavy install.** One `uv add` pulled in **17 packages (~66 MiB)** — it bundles a Node-based Claude Code CLI plus `mcp`, `starlette`, `uvicorn`, `cryptography`. Contrast Phase 3's agent: ~200 lines on `anthropic` + `httpx`. Weight-for-convenience is the trade Exercise 03 measures.
- **Don't drain only the `ResultMessage`.** A throwaway probe that iterated `query()` but only inspected `ResultMessage` intermittently raised `Claude Code returned an error result: success` and reported zero cost. Iterating and handling *each* message type (as the shipped script does) is stable. Lesson: consume the SDK's full message stream, not just the final frame.
- **Blocking tools inside `async` (Ex 02).** Our ported `web_search`/`fetch_url` call synchronous `ddgs`/`httpx` inside an `async def`, which blocks the event loop for the call's duration. Fine for a single-user teaching script (nothing else is running), but a production port would use `httpx.AsyncClient` and run `ddgs` in a thread. We surfaced the shortcut in a comment rather than hiding it.
- **`num_turns` ≠ Phase 3 "iterations" (Ex 02).** The SDK's `num_turns` (≈6 for the ReAct question) counts message exchanges, not model calls; Phase 3's loop counted ~4 model calls for the same work. Don't compare the two counters directly — compare cost and trajectory instead.
- **Use `uv run python`, not `python3`, to inspect the SDK.** `python3` is the system interpreter and can't see the uv-managed venv (`ModuleNotFoundError: claude_agent_sdk`). Anything that imports project deps must go through `uv run`.
