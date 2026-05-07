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
| [Phase 2](phase-2/README.md) | Application primitives — embeddings, RAG, prompt caching, LLM-as-judge | 🚧 in progress |
| Phase 3 | Build agents from scratch | — |
| Phase 4 | Frameworks and patterns | — |
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
├── phase-1/              # ✅ done
│   ├── README.md         #    phase 1 run order + concepts reference
│   ├── 00_count_tokens.py
│   ├── 01_stream_hello.py
│   ├── 02_quiz_cli.py
│   └── evals/
└── phase-2/              # 🚧 in progress
    ├── README.md         #    phase 2 run order + new concepts
    └── 01_embeddings.py
```
