# Phase 3 — Build agents from scratch

**Goal:** understand what an agent actually is before you reach for a framework.

**Ship deliverable:** a research agent in ~200 lines of pure Python, no framework. Tools: web search, fetch URL, write file. Input: a question. Output: a cited markdown report.

## Progress — 4 of 6 (🚧 in progress)

| # | Deliverable | Status |
|---|---|---|
| 01 | [`01_agent_loop_minimal.py`](01_agent_loop_minimal.py) — the bare `while` loop | ✅ shipped |
| 02 | [`02_agent_loop_robust.py`](02_agent_loop_robust.py) — 3 tools, error recovery, cost tracking, `--trace` | ✅ shipped |
| 03 | [`03_agent_loop_react.py`](03_agent_loop_react.py) — ReAct (Thought → Action → Observation) | ✅ shipped |
| 04 | [`04_self_critique.py`](04_self_critique.py) — generate → critique → revise (Reflexion) | ✅ shipped |
| 05 | `05_research_agent.py` — **the ship**: web search + fetch + write file → cited report | ⏳ next |
| — | `evals/` — Phase 3 eval | ⏳ pending |

## What is an agent (in one paragraph)

An **agent** is an LLM call wrapped in a `while` loop. Each iteration: the model sees the conversation so far plus a list of tools it can call. It either replies with text (done) or asks to call a tool. Your code runs the tool, appends the result to the conversation, and loops. The loop ends when the model stops asking for tools.

That's it. Everything else — ReAct, planning, multi-agent, MCP — is variation on this loop.

## Run order

```bash
export PATH="$HOME/.local/bin:$PATH"

# Exercise 1 ✅ — feel the loop with trivial math tools
uv run phase-3/01_agent_loop_minimal.py
uv run phase-3/01_agent_loop_minimal.py "What is 17 squared minus 9?"

# Exercise 2 ✅ — robust loop: 3 tools, system prompt, error recovery, cost tracking
uv run phase-3/02_agent_loop_robust.py "What's 2+2*3 and how many words in 'the quick brown fox'?"
uv run phase-3/02_agent_loop_robust.py "What is 10 divided by 0?"        # error recovery demo
uv run phase-3/02_agent_loop_robust.py "Hello!"                           # zero-tool case
uv run phase-3/02_agent_loop_robust.py "compute (2+3)*(4+5)" --trace      # full conversation dump

# Exercise 3 ✅ — ReAct: same loop, but the model emits Thought → Action → Observation
uv run phase-3/03_agent_loop_react.py "What's 2+2*3 and how many words in 'the quick brown fox'?"
uv run phase-3/03_agent_loop_react.py "What is 10 divided by 0?"          # watch the Thought after the ERROR
uv run phase-3/03_agent_loop_react.py "Hello!"                            # zero-tool case still emits a Thought

# Exercise 4 ✅ — self-critique (Reflexion): generate → critique → revise → ... until accept
uv run phase-3/04_self_critique.py "Explain recursion to a 10-year-old"
uv run phase-3/04_self_critique.py "Write a 4-line poem about gradient descent"     # watch score climb each round
uv run phase-3/04_self_critique.py "Explain TCP handshake" --critic-model claude-sonnet-4-6   # stronger critic
uv run phase-3/04_self_critique.py "Explain recursion to a 10-year-old" --show-drafts          # see every revision

# 05 (the ship) + eval come in subsequent turns
```

## What Exercise 2 adds on top of Exercise 1

Same loop, more instrumentation — the bits production agents need:

| Addition | Why it matters |
|---|---|
| **3 tools** (calculator, get_current_time, word_count) | Forces the model to *choose*. Tool selection is where the real intelligence lives. |
| **System prompt** | Carries the agent's rules (use tools when they help, recover from errors, don't over-call). |
| **Error recovery** | Tool exceptions round-trip back to the model as `ERROR: ...` strings — the model can recognize the failure and adapt. |
| **Cost tracking** | Per-iteration tokens + running dollar total. Agents add up fast. |
| **Unknown-tool guard** | If the model hallucinates a tool name, return an error instead of crashing on KeyError. |
| **`--trace` mode** | Dumps the full messages list at the end. The single best debugging tool when an agent goes sideways. |

## What Exercise 3 adds: ReAct

**ReAct = Reason + Act.** The change is shockingly small. The LOOP doesn't change. The TOOLS don't change. Only two things move:

| What changes | What stays the same |
|---|---|
| **System prompt** — model must emit `Thought:` before every action, and `Thought:` then `Answer:` before any final reply | Loop structure, `stop_reason` exit condition, tool definitions, error recovery, cost tracking |
| **Display logic** — text blocks get split on `Thought:` / `Answer:` markers and styled separately from tool calls | Tool execution, message append, trace dump |

That's it. **Most "agent patterns" are prompt-level, not architectural.** You can stack ReAct on top of any loop — including the agents you'll write in Phase 4 using a framework. The framework doesn't give you ReAct; the prompt does.

### Why ReAct earns its keep

| Without ReAct (Exercise 2) | With ReAct (Exercise 3) |
|---|---|
| You see WHAT the model called (`calculator("10/0")`) | You see WHY (`"...attempt with the calculator to see how it handles division by zero"`) |
| When the agent loops weirdly, you guess at the cause | The repeating Thought tells you exactly which observation it ignored |
| Errors round-trip silently — model recovers but you can't see the reasoning | The Thought after the error explicitly names the failure (`"The calculator correctly returned an error because division by zero is undefined..."`) |

The "watch the model think after a tool ERROR" case is the single most pedagogically valuable invocation in this exercise. Run it and read the trace top-to-bottom.

### Cost tradeoff (small but real)

ReAct adds output tokens — the model writes its reasoning every turn. In the test above, the Thought adds ~30-60 tokens per iteration. On Haiku 4.5 that's ~$0.00012/iter. On Opus it's ~$0.005/iter. Worth it for development and debugging; consider stripping ReAct from production prompts where the trace isn't surfaced anywhere.

### Source

ReAct is from [Yao et al. 2022 (arxiv)](https://arxiv.org/abs/2210.03629). Worth skimming the abstract — the whole modern tool-using agent paradigm is downstream of this one paper.

## Gotcha: agents are non-deterministic

Running `03_agent_loop_react.py "What is 10 divided by 0?"` will sometimes give you a 2-iteration trace (model calls `calculator("10/0")`, sees `ERROR: ZeroDivisionError`, then explains) and sometimes a 1-iteration trace (model decides it knows the answer without calling the tool, answers directly). **Both are correct.** The system prompt explicitly allows skipping tools when prose suffices.

Two causes:

1. **Sampling temperature.** Anthropic's default temp is ~1.0. The model picks the next token probabilistically. Different runs → different first tokens → divergent traces. Pass `temperature=0` to `messages.create` to reduce (but not eliminate) variance.
2. **Genuine judgment.** "Use the tool or trust training data?" is a legitimate decision. The model lands differently on the boundary across runs.

This is the single biggest reason **evals matter**. A one-off trace tells you nothing. Run the same input 20 times, look at the distribution of behaviors, *that's* your signal. We'll build this in the Phase 3 eval.

Practical implication: don't debug agents by running once. Run 5–10 times. The intermittent failure is the bug.

## Where does the "Thought:" come from?

It's not a special API feature. There's no `Thought` content block in Anthropic's API. The model emits the literal string `"Thought: ..."` because the system prompt told it to. The display in `03_agent_loop_react.py` then splits on that marker and styles it.

Rename "Thought:" to "REASONING:" in the system prompt and the model will emit "REASONING:" instead — same pattern, different label. ReAct is **a prompt convention, not an architecture**. The convention comes from the original paper, which is why everyone uses the same vocabulary — but the machinery is just instruction-following.

## What Exercise 4 adds: self-critique (Reflexion)

Exercises 1-3 wired the model to **external** tools — Python functions like `calculator()`. Exercise 4 wires the model to **itself**. Same while-loop shape, but the thing producing each "result" is a whole second LLM call.

```
GENERATE draft → CRITIQUE it → if "revise": REGENERATE with feedback → CRITIQUE → ... → ACCEPT (or hit max rounds)
```

| The loop is still… | But now… |
|---|---|
| model → result → model → ... → exit-on-condition | the "tool" is a **critic LLM call**, not a Python function |
| capped by `--max-rounds` (same as max-iterations) | the agent improves **its own output** instead of fetching facts |
| exits on a stop condition | the condition is the **critic's `verdict == "accept"`**, not `stop_reason` |

**This is the seed of multi-agent.** A *generator* and a *critic* are two agents passing work back and forth. In Phase 4 you'll wire this with a framework and see it's the same two prompts and a loop — no magic.

### The critic is where the leverage is

The critic uses **forced tool use** (Phase 1's `tool_choice`) so its verdict comes back as reliable JSON — `{score, issues[], verdict}` — never prose you have to parse. The `CRITIC_SYSTEM` prompt is deliberately *demanding*: a polite critic accepts the round-1 draft and the loop teaches you nothing. A ruthless critic finds concrete, actionable problems and forces real revisions. **Tune `CRITIC_SYSTEM` and watch the round count move** — that's the single biggest lever in this exercise.

A healthy run looks like a climbing score with shrinking issue lists:

```
Round 1: 8/10  — 3 issues  → revise
Round 2: 8/10  — 1 issue   → revise
Round 3: 9/10  — accepted ✓
```

### The asymmetric-critic pattern (a real production trick)

`--critic-model` lets the critic be a *different* (usually stronger) model than the generator. Cheap generator + expensive critic is a common cost-saver: you spend Haiku tokens on the many generation attempts and Sonnet/Opus tokens only on grading. Try `--critic-model claude-sonnet-4-6` against a Haiku generator and feel the difference in critique sharpness.

### When NOT to use this

Self-critique roughly **doubles-to-quadruples cost** (every round is generate + critique). It earns that on open-ended generative tasks where quality is subjective and improvable — writing, explanations, summaries. It's **wasted on deterministic tasks** (`2+2`) where there's nothing to critique. Match the pattern to the task.

## The 8 new concepts (added to Phase 1+2's 16)

| # | Concept | One-line |
|---|---|---|
| 17 | **Agent loop** | The `while` loop driving model → tool → model → ... → done. |
| 18 | **`stop_reason`** revisited | `tool_use` = keep looping. `end_turn` = exit. |
| 19 | **Real tool execution** | Mode A from Phase 1 — your code runs functions and feeds results back. |
| 20 | **Tool result blocks** | The `{"type": "tool_result", "tool_use_id": ..., "content": ...}` shape. |
| 21 | **Growing conversation** | Messages accumulate every iteration. The model sees the full trace. |
| 22 | **Max-iteration guard** | Always cap the loop. Bugs that don't terminate are agent debt. |
| 23 | **ReAct (Reason + Act)** | Make reasoning explicit: Thought → Action → Observation. |
| 24 | **Self-critique** | Agent grades its own draft and revises. |

## Required reading

Anthropic's [**Building Effective Agents**](https://www.anthropic.com/engineering/building-effective-agents) — the canonical primer. Read it twice. It distinguishes *workflows* (deterministic chains) from *agents* (LLM-driven loops) and tells you when each is right. Most of "I built an agent" should have been a workflow.

## Why hand-roll instead of using a framework?

Frameworks hide the loop. The loop **is** the lesson. Once you've written it, every framework is just a labelled abstraction over the same five lines. You'll know what's worth using and what's just import noise.
