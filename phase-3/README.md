# Phase 3 — Build agents from scratch

**Goal:** understand what an agent actually is before you reach for a framework.

**Ship deliverable:** a research agent in ~200 lines of pure Python, no framework. Tools: web search, fetch URL, write file. Input: a question. Output: a cited markdown report.

## What is an agent (in one paragraph)

An **agent** is an LLM call wrapped in a `while` loop. Each iteration: the model sees the conversation so far plus a list of tools it can call. It either replies with text (done) or asks to call a tool. Your code runs the tool, appends the result to the conversation, and loops. The loop ends when the model stops asking for tools.

That's it. Everything else — ReAct, planning, multi-agent, MCP — is variation on this loop.

## Run order

```bash
export PATH="$HOME/.local/bin:$PATH"

# Exercise 1 — feel the loop with trivial math tools
uv run phase-3/01_agent_loop_minimal.py
uv run phase-3/01_agent_loop_minimal.py "What is 17 squared minus 9?"

# 02-05 + eval come in subsequent turns
```

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
