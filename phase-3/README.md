# Phase 3 — Build agents from scratch

**Goal:** understand what an agent actually is before you reach for a framework.

**Ship deliverable:** a research agent in ~200 lines of pure Python, no framework. Tools: web search, fetch URL, write file. Input: a question. Output: a cited markdown report.

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

# 03-05 + eval come in subsequent turns
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
