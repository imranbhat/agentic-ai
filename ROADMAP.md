# Agentic AI Learning Roadmap

A practical, build-first path. Each phase has a goal, the concepts to learn, and a project to ship before moving on. Don't skip the projects — agentic AI is mostly intuition you only get from breaking things.

---

## Phase 0 — Prerequisites (skip if you have them)

**Goal:** comfortable in Python, comfortable calling an HTTP API.

- Python 3.11+: functions, classes, async/await, virtualenvs, typing
- Git, command line, JSON, basic SQL
- One LLM provider account: **Anthropic (Claude)** is the recommended starting point. OpenAI/Gemini optional.

**Ship:** a script that calls the Claude API and prints a streamed response.

---

## Phase 1 — How LLMs actually work (1 week)

**Goal:** strong mental model. You don't need to train one — you need to know what knobs you have.

- Tokens, context windows, temperature, top-p
- The transformer at a 10,000-ft level (attention, not the math)
- Pretraining vs. instruction tuning vs. RLHF — what each fixes
- Embeddings: what they are, cosine similarity, why semantic search works
- Prompt engineering: system prompts, few-shot, chain-of-thought, XML tags

**Resources:**
- Andrej Karpathy's *"Intro to Large Language Models"* (YouTube, 1hr)
- Anthropic's [Prompt Engineering docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)
- Jay Alammar's *Illustrated Transformer* (blog)

**Ship:** a CLI tool that takes a topic and generates a 5-question quiz with answers, using a structured output (JSON schema).

---

## Phase 2 — LLM application primitives (2 weeks)

**Goal:** you can build any non-agentic LLM app from scratch.

- Streaming responses (SSE)
- **Tool use / function calling** — this is the single most important agentic primitive
- Structured outputs (JSON mode, schema-validated outputs)
- Prompt caching (huge for cost — Anthropic prompt caching docs)
- Vector DBs: pgvector, Pinecone, or Chroma for local
- **RAG** (Retrieval-Augmented Generation): chunking, embedding, retrieval, reranking
- Evals: how do you know if your prompt got better? Write a test set.

**Ship:** a RAG chatbot over a corpus you care about (your own notes, a textbook PDF, internal docs). Include an eval set of 20 Q&A pairs and a score.

---

## Phase 3 — Build agents from scratch (2 weeks)

**Goal:** understand what an agent actually is before you reach for a framework.

- **The agent loop:** model → tool call → tool result → model → ... until done
- The **ReAct** pattern (Reason + Act)
- Tool design: descriptions, schemas, idempotency, error returns
- Short-term memory (conversation history) vs long-term (vector store, files)
- Planning: explicit plan-then-execute vs implicit (let the model decide)
- Self-reflection / critique loops

**Read this first, twice:** Anthropic's [*Building Effective Agents*](https://www.anthropic.com/engineering/building-effective-agents) — the canonical primer. It distinguishes workflows (deterministic chains) from agents (LLM-driven loops) and shows when each is right.

**Ship:** a research agent in ~200 lines of pure Python — no framework. Tools: web search, fetch URL, write file. It should accept a question and produce a cited markdown report.

---

## Phase 4 — Frameworks and patterns (2–3 weeks)

**Goal:** know which framework to reach for and why.

Pick **one** as your default, learn another for breadth:

| Framework | Strength | When |
|---|---|---|
| **Claude Agent SDK** | Production agents, file/bash tools, hooks, MCP-first | Default for agentic work on Claude |
| **LangGraph** | Explicit graph-based control flow, durable state | Multi-step workflows, human-in-the-loop |
| **OpenAI Agents SDK** | Lightweight, handoffs between agents | OpenAI-native multi-agent |
| **Vercel AI SDK** | Streaming UIs, Next.js apps, provider-agnostic | Web/chat UIs |
| **Pydantic AI** | Typed, FastAPI-vibes | Python-typed, structured-first |

Patterns to learn (from *Building Effective Agents*):
- **Prompt chaining** — sequential LLM calls with checks
- **Routing** — classifier sends input to specialized handler
- **Parallelization** — fan-out, vote/aggregate
- **Orchestrator-workers** — central LLM dispatches subtasks
- **Evaluator-optimizer** — generate → critique → refine loop

**Ship:** the same research agent from Phase 3, but with the Claude Agent SDK. Compare lines of code, robustness, and behavior.

---

## Phase 5 — Production-grade agents (3–4 weeks)

**Goal:** ship something real that doesn't fall over.

- **Evals as a first-class artifact** — Inspect, Promptfoo, or LangSmith. Eval-driven development is the agentic equivalent of TDD.
- **Observability** — LangSmith, Langfuse, Helicone. You cannot debug an agent you can't trace.
- **Cost control** — prompt caching, model routing (Haiku for cheap steps, Sonnet for hard ones), batch APIs
- **Safety/guardrails** — input/output validation, allowlists, sandboxing tool execution
- **MCP (Model Context Protocol)** — the emerging standard for agent ↔ tool wiring; learn to consume servers and write a small one
- **Durable execution** — Vercel Workflow DevKit, Temporal, Inngest. For agents that pause, resume, and survive crashes.
- **Multi-agent orchestration** — supervisor, debate, swarm patterns

**Ship:** an end-to-end agent deployed on Vercel/Fly/Railway with: an eval suite, a tracing dashboard, prompt caching, and a graceful failure path.

---

## Phase 6 — Frontiers (ongoing)

Pick the ones that excite you:

- **Computer use agents** — Claude's `computer-use` API; agents that drive a real desktop
- **Browser agents** — Playwright/Puppeteer + LLM, or platforms like Browserbase
- **Code-generating agents** — Aider, Claude Code itself, Devin-style loops
- **Voice agents** — realtime APIs, latency budgets, interruption handling
- **Agentic RAG** — agent decides what to retrieve, when, and how to reformulate
- **Fine-tuning** — when prompting hits its ceiling
- **RL for agents** — DSPy, GRPO, learning from traces

---

## Project ladder (build these in order)

1. **Streamed Q&A CLI** — Phase 1
2. **RAG chatbot over your own docs** — Phase 2
3. **From-scratch research agent** (no framework) — Phase 3
4. **Same agent, with Claude Agent SDK** — Phase 4
5. **Multi-agent orchestrator** (e.g. one planner + N workers) — Phase 4
6. **Production agent with evals + tracing + MCP tools** — Phase 5
7. **Computer-use or browser agent** — Phase 6

Don't move to the next without finishing the prior. The portfolio matters less than the intuition you build by debugging.

---

## Anchor resources (curated, no link rot if possible)

- **Anthropic — *Building Effective Agents*** (read 3x): https://www.anthropic.com/engineering/building-effective-agents
- **Anthropic Cookbook**: https://github.com/anthropics/anthropic-cookbook
- **Anthropic Courses** (free): https://github.com/anthropics/courses
- **DeepLearning.AI short courses** — "AI Agents in LangGraph", "Functions, Tools and Agents with LangChain", "Multi AI Agent Systems with crewAI"
- **Hugging Face Agents Course** (free): https://huggingface.co/learn/agents-course
- **Lilian Weng's *LLM Powered Autonomous Agents***: https://lilianweng.github.io/posts/2023-06-23-agent/
- **LangChain Academy** (free): https://academy.langchain.com
- **MCP spec**: https://modelcontextprotocol.io

---

## A few opinions to save you time

- **Start without a framework.** Build the agent loop yourself once. Frameworks make sense after you've felt the pain they solve.
- **Evals beat vibes.** A 20-row eval set early is worth more than 200 rows of clever prompts.
- **Prompt caching is free money** on Claude. Learn it in Phase 2, not Phase 5.
- **One model family at a time.** Ship things on Claude first. Multi-provider is a Phase 5 concern, not a learning concern.
- **Read other people's traces.** LangSmith public traces, GitHub repos, blog post screenshots. Watching agents fail is the fastest learning loop.

---

_Last updated: 2026-05-07_
