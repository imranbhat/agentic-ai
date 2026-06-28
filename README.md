# learn-ai

Hands-on workspace for the [agentic AI roadmap](ROADMAP.md).

## Setup (one-time)

```bash
# 1. uv is installed at ~/.local/bin — make sure it's on PATH
export PATH="$HOME/.local/bin:$PATH"

# 2. Install deps + a managed Python (uv handles the version)
uv sync

# 3. Add your API key
cp .env.example .env
# edit .env, paste your key from https://console.anthropic.com/settings/keys
```

📖 **Stuck on a word?** [GLOSSARY.md](GLOSSARY.md) — every term used in plain English, with cheat-sheet tables.

## Phase guides

Each phase has its own README with run order, concepts, and gotchas.

| Phase | Focus | Status |
|---|---|---|
| [Phase 1](phase-1/README.md) | LLM mental model — tokens, streaming, tool use, structured output, evals | ✅ shipped |
| [Phase 2](phase-2/README.md) | Application primitives — embeddings, RAG, prompt caching, LLM-as-judge | ✅ shipped |
| [Phase 3](phase-3/README.md) | Build agents from scratch — the loop, tools, research agent | ✅ shipped |
| Phase 4 | Frameworks and patterns | 🔜 next |
| Phase 5 | Production-grade agents | — |
| Phase 6 | Frontiers (computer use, browser agents, voice, fine-tuning) | — |

## Cost note

Examples default to `claude-haiku-4-5` — ~$0.80/M input, ~$4/M output. A full Phase 1 eval run is well under a cent. Set `ANTHROPIC_MODEL=claude-sonnet-4-6` in `.env` if you want to see Sonnet's quality on the same prompts.

Phase 2 adds local embeddings (free, runs on your CPU) and prompt caching (cuts repeated-call cost ~10×).

## Project structure

```
learn-ai/
├── ROADMAP.md            # the curriculum
├── README.md             # this file
├── CLAUDE.md             # rules for AI agents working in this repo
├── pyproject.toml        # uv-managed Python project
├── .env.example          # template for ANTHROPIC_API_KEY
├── phase-1/              # ✅ done — LLM mental model
│   ├── README.md         #    run order + 8 core concepts + gotchas
│   ├── 00_count_tokens.py
│   ├── 01_stream_hello.py
│   ├── 02_quiz_cli.py    #    ship: forced tool use → structured JSON
│   └── evals/
│       ├── eval_quiz.py  #    structural eval
│       └── topics.jsonl
├── phase-2/              # ✅ done — RAG, embeddings, caching, LLM-as-judge
│   ├── README.md         #    run order + 8 new concepts + two RAG patterns
│   ├── 01_embeddings.py  #    embedding basics + similarity
│   ├── 02_build_index.py #    chunk + embed corpus → disk
│   ├── 03_retrieve.py    #    top-K semantic search
│   ├── 04_rag_chat.py    #    ship #1: vector-search RAG (cited, grounded)
│   ├── 05_with_caching.py #   ship #2: cached-context RAG
│   └── evals/
│       ├── eval_rag.py   #    LLM-as-judge across retrieval/gen/refusal
│       └── eval_set.jsonl
└── phase-3/              # ✅ done — agents from scratch (the loop, real tools)
    ├── README.md         #    run order + concepts + ReAct/critique/eval notes
    ├── 01_agent_loop_minimal.py  # the bare while-loop
    ├── 02_agent_loop_robust.py   # 3 tools, error recovery, cost, --trace
    ├── 03_agent_loop_react.py    # ReAct: Thought → Action → Observation
    ├── 04_self_critique.py       # generate → critique → revise (Reflexion)
    ├── 05_research_agent.py      # ship: web_search + fetch_url + write_file → cited report
    ├── reports/                  # generated reports (checked in as samples)
    └── evals/
        ├── eval_research.py      # 5-dimension eval: trajectory + grounded citations + judge
        └── eval_set.jsonl        # research questions with known-fact checks
```
