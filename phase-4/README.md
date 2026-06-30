# Phase 4 — Frameworks and patterns

**Goal:** know which framework to reach for and why — and *feel* what a framework adds and hides versus the loop you hand-wrote in Phase 3.

**Ship deliverable (from the roadmap):** rebuild the **exact** Phase 3 research agent on the **Claude Agent SDK**, then compare lines of code, robustness, and behavior against the hand-rolled version.

> **Status: 🚧 in progress (7/9).** Sequence confirmed. Exercises 04–08 (the *Building Effective Agents*
> patterns) are built in **plain Anthropic API** on purpose — they're workflows, and a framework would hide
> the orchestration they're meant to teach. Exercise 09 adds **LangGraph** for a true 3-way comparison.

## Progress — 7 of 9

| # | Deliverable | Status |
|---|---|---|
| 01 | [`01_sdk_hello.py`](01_sdk_hello.py) — SDK hello-world: the simplest `query()`, the typed message stream, cost computed for you | ✅ shipped |
| 02 | [`02_research_agent_sdk.py`](02_research_agent_sdk.py) — **the ship**: Phase 3's research agent, ported to the SDK (same 3 tools, no hand-written loop) | ✅ shipped |
| 03 | [`03_sdk_vs_scratch.md`](03_sdk_vs_scratch.md) — the comparison: LOC, robustness, behavior; what the framework adds and what it hides | ✅ shipped |
| 04 | [`04_prompt_chaining.py`](04_prompt_chaining.py) — sequential LLM calls with a **gate** between them (the first BEA pattern) | ✅ shipped |
| 05 | [`05_routing.py`](05_routing.py) — a classifier **branches** input to a specialized handler (cost/quality routing) | ✅ shipped |
| 06 | [`06_parallelization.py`](06_parallelization.py) — fan-out concurrent calls, then **vote** or **section**-aggregate (async) | ✅ shipped |
| 07 | [`07_orchestrator_workers.py`](07_orchestrator_workers.py) — a model **dynamically plans** subtasks, workers run them in parallel, a synthesizer combines | ✅ shipped |
| 08 | `08_evaluator_optimizer.py` — generate → critique → refine (the Phase 3 self-critique, framed as a pattern) | ⏳ next |
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

# Exercise 05 ✅ — routing (BEA pattern #2): a cheap classifier BRANCHES to one specialized handler.
uv run phase-4/05_routing.py "What is the capital of France?"              # → simple    (Haiku)
uv run phase-4/05_routing.py "Prove that the square root of 2 is irrational."   # → reasoning (Sonnet)
uv run phase-4/05_routing.py "Which blood pressure medication should I take?"   # → refuse    (no LLM, $0)

# Exercise 06 ✅ — parallelization (BEA pattern #3): fan out concurrent calls, then aggregate. Async.
uv run phase-4/06_parallelization.py "Stunning visuals but the plot dragged and I nearly left."   # vote (majority)
uv run phase-4/06_parallelization.py "Stunning visuals but the plot dragged and I nearly left." --sequential  # same cost, slower
uv run phase-4/06_parallelization.py "a password manager for families" --mode section   # independent subtasks at once

# Exercise 07 ✅ — orchestrator-workers (BEA pattern #4): a model PLANS subtasks, workers run them, a synthesizer combines.
uv run phase-4/07_orchestrator_workers.py "the impact of remote work on companies"
uv run phase-4/07_orchestrator_workers.py "how the James Webb Space Telescope sees the early universe"   # note: a DIFFERENT plan
uv run phase-4/07_orchestrator_workers.py "a topic" --synth-model claude-sonnet-4-6   # stronger editor at the join
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

> **Don't misread the cost table above.** The headline reason to chain is **accuracy**, not cost — you split a
> hard task into simpler subtasks so each call does one easy job reliably. Chaining normally *increases* total
> cost and latency (you make *more* calls). The fail-fast savings (`$0.0003` vs `$0.0006`) is a **failure-case
> cushion**, not the goal: it only kicks in when the gate *rejects* a step. You reach for chaining to be
> *right*, and fail-fast just softens the bill when a step is bad. Also note: a gate can do more than **stop** —
> it can trigger a **retry/fix** (that's Exercise 08) or **route** to a different next step; "stop on fail" is
> just the simplest kind. And a chain needn't have a gate at all (`outline → draft → polish` is still a chain) —
> decomposition makes it *chaining*; the gate makes it *robust*.

## What Exercise 05 adds: routing (BEA pattern #2 — a branch, not a sequence)

Where prompt chaining (Ex 04) runs every step in order, **routing makes a branch**: a cheap **classifier** call
inspects the input and **exactly one** specialized handler runs.

```
input ──▶ classifier ──▶ ┌─ simple    → Haiku  handler (terse)
             (LLM)       ├─ reasoning → Sonnet handler (thorough)
                         └─ refuse    → canned message (NO LLM, $0)
```

| Chaining (Ex 04) | Routing (Ex 05) |
|---|---|
| "and then, and then" — all steps run | "which one?" — one handler runs |
| gate decides *continue vs stop* | classifier decides *which path* |

**The production payoff is cost/quality routing.** A single do-everything prompt forces one model on every
input — you either overpay (Sonnet on "capital of France?") or underperform (Haiku on a hard proof). A cheap
classifier breaks that bind: it decides *what kind* of question this is, then you spend expensively **only**
where it helps. Measured on three inputs:

| Route | Classifier | Handler | Total | Model |
|---|---|---|---|---|
| simple ("capital of France") | $0.0009 | $0.0001 | **$0.0010** | Haiku |
| reasoning ("prove √2 irrational") | $0.0009 | $0.0088 | **$0.0097** | Sonnet |
| refuse ("which BP medication") | $0.0009 | $0.0000 | **$0.0009** | none |

Two callbacks to earlier exercises:
1. **The classifier uses forced tool use** (Phase 1's `tool_choice`) — the category comes back as reliable JSON
   `{category, reason}`, never prose you'd parse. An `enum` on the schema pins it to the three valid labels.
2. **The `refuse` route runs no LLM** — a canned string, $0. Same lesson as Ex 04's pure-Python gate: a branch
   doesn't have to call a model. Routing to a non-LLM path (refusal, cache hit, human handoff) is first-class.

> **The model note:** the `reasoning` route defaults to **Sonnet** — a more expensive *Claude*, not a drift to
> another provider. Spending more there is the whole point; the classifier and the simple route stay on Haiku.

### Two refinements (from a mid-phase Q&A)

**The classifier doesn't have to be an LLM.** We used a Haiku classifier, so we pay the tax every request — but
that's a *choice*, not a requirement. BEA says routing "can be handled by an LLM **or a more traditional
classification algorithm**": keyword/regex match, an intent model, embedding-similarity, a rules table. If the
categories are clean enough to detect in Python, you route for **$0** — no tax. Use an *LLM* classifier only
when the routing decision is too fuzzy for cheap code (ours — "reasoning vs. medical advice?" — is). Same shape
as Ex 04's gate: the classifier step might not need a model either.

**The five patterns compose — they aren't five separate choices.** A route's *handler* can itself be another
router (coarse → fine), a chain (Ex 04), or a full agent loop. Real systems are a *tree* of these blocks, not
one in isolation. `classify → handle → classify → handle …` is valid — **but watch the boundary**: if *you*
hardcoded that structure it's still a **workflow**; if the cycle repeats "until done" and the **model** decides
whether to loop again, you've crossed into an **agent**. The dividing line is the Phase 3 one — *who owns the
control flow, your code or the model?* Compose freely; just always know which side of that line you're on, because
it changes how you cost, debug, and guardrail the system.

## What Exercise 06 adds: parallelization (BEA pattern #3 — the first non-sequential one)

Chaining (04) and routing (05) ran one call at a time. Parallelization **fans out multiple calls at once**, then
aggregates. Two flavors, both in the file (`--mode`):

- **vote** — run the *same* prompt N times in parallel, aggregate by **majority**. Buys *reliability* (when there's variance to reduce).
- **section** — split a task into *independent* subtasks, run them at once, **stitch**. Buys *latency*.

**What it changes — and what it doesn't.** It changes **latency**: N concurrent calls finish in ≈ one call's
wall-clock. It does **not** reduce cost — you make N calls, so you pay N× a single call, every time. The
`--sequential` flag proves it by running the *same* calls one-by-one:

| Run | Result | Cost | Wall-clock |
|---|---|---|---|
| vote ×5 **parallel** | negative×5 | $0.0035 | **1.15s** |
| vote ×5 **sequential** (identical calls) | negative×5 | $0.0035 | **4.35s** |
| section ×3 parallel | 3 stitched sections | $0.0004 | 1.88s |

Same `$0.0035`, 4.35s → 1.15s. `asyncio.gather` removed *latency and only latency*.

**Why async here (not in 04/05):** concurrency needs it. We use `AsyncAnthropic` so the `await`ed calls actually
overlap on the network instead of blocking each other; `asyncio.gather` schedules them together.

> **The voting result is a lesson in itself: it didn't split.** Every borderline review came back unanimous
> (negative×5, then positive×7) because a capable model at temp 1.0 is *already consistent* on sentiment — there
> was no variance to reduce, so the 5–7 votes just paid N× for agreement. **Voting only earns its keep when the
> calls genuinely disagree:** subjective/hard judgments where the model wavers, weaker models with more variance,
> or **high-recall guardrails** ("flag if *any* of N says unsafe" — valuable precisely to catch the rare
> dissent). Don't reach for voting on a task your model already nails consistently.

## What Exercise 07 adds: orchestrator-workers (BEA pattern #4 — dynamic decomposition)

A central **orchestrator** LLM reads the task and *decides how to break it up*, dispatches each subtask to a
**worker** call (in parallel — this reuses Ex 06's `asyncio.gather`), then a **synthesizer** combines the
results.

```
topic ─▶ ORCHESTRATOR ─▶ plan = [sub₁ … subₙ]   →  workerᵢ (all at once)  →  SYNTHESIZER ─▶ final
            (model invents the subtasks)            (parallel fan-out)        (stitch + smooth)
```

**The one thing that separates it from Ex 06 sectioning:** there, the subtasks were fixed in your code
(`headline/features/tagline`, every run). Here **the model invents the subtasks at runtime** — so two topics
produce two different plans:

| Topic | Plan the orchestrator generated |
|---|---|
| "impact of remote work" | Productivity · Culture & Team Dynamics · Operational Costs · Talent |
| "how JWST sees the early universe" | Infrared Tech · Redshift & Light-Travel · Key Discoveries · Observational Methods |

Nothing shared — each plan fits *its* topic. You own the **shape** (plan → work → synthesize); the model owns
the **content** (which subtasks). Both runs were 6 calls (1 plan + 4 workers + 1 synth) at ~$0.0056 / ~$0.0074.

**The synthesizer is the natural cost/quality upgrade point.** It didn't just concatenate — on the JWST run it
*reordered* sections and trimmed cross-section redundancy. Quality matters most at the join, so `--synth-model
claude-sonnet-4-6` lets you spend there while workers stay on Haiku (a callback to Ex 05's cost/quality idea).

### "Is this still a workflow, or an agent?" — the question this pattern forces

**Still a workflow.** The control flow is fixed and *you* wrote it: exactly one plan, one parallel worker batch,
one synthesis — no loop, no "do I need another round?" decision. The model chooses the **content** of the steps
(which subtasks), never the **structure** (how many phases, whether to repeat). The moment you let the
orchestrator *loop* — "look at the draft, decide if it needs more workers, repeat until satisfied" — the **model**
owns the control flow and you've crossed into an **agent** (Phase 3's while-loop). This exercise stops one step
short of that line on purpose; Exercise 08 (evaluator-optimizer) adds the loop back.

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
| 39 | **Routing** (BEA pattern #2) | A *branch*: a cheap classifier inspects the input and dispatches to exactly one specialized handler. Chaining is a sequence; routing is a switch. |
| 40 | **Classifier** | The cheap LLM call (here Haiku, forced tool use) that labels the input so the router can branch. Its cost is a flat per-request tax — see the gotcha. |
| 41 | **Cost/quality routing** | The payoff of routing: send easy inputs to a cheap model, hard ones to a strong model, out-of-scope ones to a $0 non-LLM path — instead of forcing one model on everything. |
| 42 | **Parallelization** (BEA pattern #3) | Fan out multiple LLM calls *concurrently*, then aggregate. The first non-sequential pattern. Changes latency, not cost. |
| 43 | **Voting vs sectioning** | The two flavors of parallelization. *Voting*: same prompt N×, majority-aggregate (reliability). *Sectioning*: independent subtasks at once, stitch (latency). |
| 44 | **`AsyncAnthropic` + `asyncio.gather`** | The async machinery concurrency needs: `await`ed calls overlap on the network instead of blocking; `gather` schedules them together so total time ≈ the slowest one. |
| 45 | **Orchestrator-workers** (BEA pattern #4) | A model *plans* subtasks, workers do them (in parallel), a synthesizer combines. Builds on parallelization — but a model call produces the list being fanned out. |
| 46 | **Dynamic decomposition** | The defining trait of orchestrator-workers: the subtasks are decided by the model at runtime (different per input), not fixed in your code like Ex 06's sections. You own the *shape*; the model owns the *content*. |
| 47 | **Workflow↔agent boundary** | Orchestrator-workers is the closest workflow to an agent. It stays a workflow because the control flow (plan→work→synthesize, once) is fixed by you. Let the orchestrator *loop* on "is it done?" and the model owns control flow → agent. |

## Gotchas

- **The SDK is project-aware by default.** It loads the working directory and `CLAUDE.md` — so a "hello world" answer references your repo, and input cost is higher than a bare `messages.create()` call. If you ever want a hermetic agent (no repo context), you'd configure that explicitly; the *default* is "knows everything about where it's running."
- **A Haiku hello-world cost $0.003–0.013, and it varied run to run.** Phase 1's hello-world was a fraction of a cent. The gap is the injected harness/project context (and prompt-cache read vs. write across runs — repeated runs are cheaper). The framework's convenience has a baseline token tax.
- **`claude-agent-sdk` is a heavy install.** One `uv add` pulled in **17 packages (~66 MiB)** — it bundles a Node-based Claude Code CLI plus `mcp`, `starlette`, `uvicorn`, `cryptography`. Contrast Phase 3's agent: ~200 lines on `anthropic` + `httpx`. Weight-for-convenience is the trade Exercise 03 measures.
- **Don't drain only the `ResultMessage`.** A throwaway probe that iterated `query()` but only inspected `ResultMessage` intermittently raised `Claude Code returned an error result: success` and reported zero cost. Iterating and handling *each* message type (as the shipped script does) is stable. Lesson: consume the SDK's full message stream, not just the final frame.
- **Blocking tools inside `async` (Ex 02).** Our ported `web_search`/`fetch_url` call synchronous `ddgs`/`httpx` inside an `async def`, which blocks the event loop for the call's duration. Fine for a single-user teaching script (nothing else is running), but a production port would use `httpx.AsyncClient` and run `ddgs` in a thread. We surfaced the shortcut in a comment rather than hiding it.
- **`num_turns` ≠ Phase 3 "iterations" (Ex 02).** The SDK's `num_turns` (≈6 for the ReAct question) counts message exchanges, not model calls; Phase 3's loop counted ~4 model calls for the same work. Don't compare the two counters directly — compare cost and trajectory instead.
- **Use `uv run python`, not `python3`, to inspect the SDK.** `python3` is the system interpreter and can't see the uv-managed venv (`ModuleNotFoundError: claude_agent_sdk`). Anything that imports project deps must go through `uv run`.
- **Routing has a classifier tax (Ex 05).** The classifier costs a flat ~$0.0009 on *every* request — and on the `simple` route that's **9× the handler it routed to** ($0.0009 vs $0.0001). Routing only nets out ahead when the cost spread between handlers is big enough to dwarf that tax (the Sonnet route, ~$0.0088, is what justifies it). For a uniformly-cheap workload, always-Haiku beats routing. Don't add a router unless the routes genuinely differ in cost or quality.
- **Parallel wall-clock is noisy (Ex 06).** Two identical 5-call parallel runs clocked 1.15s and 4.86s — network/load jitter, not your code. Parallel time ≈ the *slowest* call in the batch, and the slowest call varies run to run. Compare parallel-vs-sequential *within the same conditions* (the 1.15s vs 4.35s pair), not across separate runs.
- **Voting needs variance to be worth it (Ex 06).** Our borderline reviews came back unanimous (negative×5, positive×7) — a capable model at temp 1.0 was already consistent, so the votes paid N× for nothing. Voting earns its keep only on genuinely uncertain/subjective tasks, weaker models, or high-recall guardrails ("flag if *any* of N flags"). Match the pattern to the task — same rule as Phase 3's self-critique.
