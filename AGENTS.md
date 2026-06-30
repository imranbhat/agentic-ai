# learn-ai — AGENTS.md

Learning workspace, not production. Optimize for pedagogical clarity.

## Setup

- **uv** is the package manager (not pip/poetry). Installed at `~/.local/bin` — add to PATH: `export PATH="$HOME/.local/bin:$PATH"`
- Install: `uv sync` (reads `pyproject.toml` + `uv.lock`)
- Run scripts: `uv run phase-N/0X_filename.py [args]` — never `python phase-N/...`
- **`ANTHROPIC_API_KEY`** required in `.env` (copy from `.env.example`). Without it, API-dependent exercises fail silently.
- Python >=3.11 required. **No linter, no formatter, no test framework configured** (`[dependency-groups] dev = []`).

## Running exercises

Every exercise is a top-level script (not a module), run directly:

```bash
uv run phase-1/00_count_tokens.py "your text here"
uv run phase-1/01_stream_hello.py
uv run phase-1/02_quiz_cli.py "topic" --n 3 --difficulty hard
uv run phase-1/evals/eval_quiz.py        # structural eval, reads topics.jsonl
```

Eval reads `phase-1/evals/topics.jsonl` — 5 rows, each with `topic`, `difficulty`, `expected_n`.

```bash
uv run phase-3/05_research_agent.py "your question"     # research agent → cited report
uv run phase-3/evals/eval_research.py                   # 5-dimension agent eval
```

```bash
uv run phase-4/01_sdk_hello.py                          # Claude Agent SDK hello-world (async, no while loop)
uv run phase-4/01_sdk_hello.py "your question"
uv run phase-4/02_research_agent_sdk.py "your question"  # Phase 3 research agent, ported to the SDK → cited report
uv run phase-4/04_prompt_chaining.py "a product idea"   # BEA pattern #1: draft → gate → translate (plain anthropic)
uv run phase-4/04_prompt_chaining.py "a note-taking app" --max-words 10   # force the gate to fail
uv run phase-4/05_routing.py "What is the capital of France?"            # BEA pattern #2: classifier → handler
uv run phase-4/05_routing.py "Which blood pressure medication should I take?"   # → refuse route (no LLM, $0)
uv run phase-4/06_parallelization.py "a review to classify"             # BEA pattern #3: vote (fan-out, majority)
uv run phase-4/06_parallelization.py "a topic" --mode section           # sectioning (independent subtasks at once)
uv run phase-4/06_parallelization.py "a review" --sequential            # same cost, slower — proves it's latency-only
uv run phase-4/07_orchestrator_workers.py "a briefing topic"            # BEA pattern #4: plan → parallel workers → synthesize
uv run phase-4/07_orchestrator_workers.py "a topic" --synth-model claude-sonnet-4-6   # stronger editor at the join
```

`phase-4/02_research_agent_sdk.py` is a faithful port of `phase-3/05_research_agent.py`: identical three tools, now registered as one in-process MCP server (`@tool` + `create_sdk_mcp_server`). Writes to `phase-4/reports/`, **which is tracked** (sample output, like `phase-3/reports/`). Faithful-port options: `tools=[]` (no built-in tools), `setting_sources=[]` (isolation — no `CLAUDE.md`), `system_prompt=<string>` (replaces the preset), `max_turns=15` (built-in loop guard), `permission_mode="bypassPermissions"`. Inspect SDK objects with `uv run python -c ...`, never bare `python3` (system interpreter can't see the venv).

## Phase 2 index

`phase-2/index/` is gitignored — derived data, never committed. Build with:
```bash
uv run phase-2/02_build_index.py             # no-op if exists
uv run phase-2/02_build_index.py --rebuild   # force
```

Produces `embeddings.npy` (N×384 float32) + `chunks.jsonl` (parallel metadata). ~30s build time.

## Phase 3 research agent

`phase-3/05_research_agent.py` is the ship — an agent with three real tools (`web_search` via `ddgs`, `fetch_url` via httpx+BeautifulSoup, `write_file`). Writes reports to `phase-3/reports/`, which **is tracked** (checked in as sample output, not gitignored). `run_agent` returns a trajectory dict and takes `quiet=True` so the eval can run it silently.

`phase-3/evals/eval_research.py` scores the agent on 5 dimensions (completed, trajectory order/budget, grounded citations, known-fact, LLM-judge). It loads the agent module via `importlib.util.spec_from_file_location` because the filename starts with a digit.

## Dependency pinning quirks

- `fastembed<0.6.0` — ONNX-based embeddings, no PyTorch
- `onnxruntime<1.20` — newer versions dropped Intel Mac wheels
- `ddgs` + `beautifulsoup4` — Phase 3 web tools (keyless search + HTML→text). `ddgs` pulls `primp`/`lxml` transitively; we parse with the built-in `html.parser`.
- `claude-agent-sdk` — Phase 4 agent framework. **Heavy:** one `uv add` pulled 17 packages (~66 MiB) because it bundles a Node-based Claude Code CLI and ships `mcp`/`starlette`/`uvicorn`/`cryptography`. **Requires Node.js present** (the Python SDK shells out to the bundled CLI; we run on Node v23). It also reads `CLAUDE.md` + the working dir by default, so SDK agents are project-aware — expect higher input cost than a bare `messages.create()` call.

## Critical rules (from CLAUDE.md)

1. **Update phase README in the same turn** whenever you add/rename a file, introduce a concept, hit+fix a bug, or change run commands. Never defer.
2. **No separate doc files** — each phase has exactly one `phase-N/README.md`. No `CONCEPTS.md` or variants.
3. **Comments on WHY, not WHAT.** Short docstring at top. Inline comments only for non-obvious choices.
4. **Before marking done:** file runs end-to-end, README run-order is current, README concepts cover the file, gotchas are recorded.

## Quirks

- Filenames start with digits (not valid Python identifiers), so evals import their target by path: `importlib.import_module("02_quiz_cli")` in Phase 1, `importlib.util.spec_from_file_location(...)` for `05_research_agent.py` in Phase 3.
- Default model `claude-haiku-4-5`. Override with `ANTHROPIC_MODEL` in `.env`.
- `count_tokens` endpoint is free (no charge).
- `.claude/settings.local.json` has an allowlist — `uv run *` and `uv sync *` are the main pattern.
- **Git is initialized**; remote is `https://github.com/imranbhat/agentic-ai` (main). Convention: one commit per exercise + one for README/docs updates — don't bundle both. Attribution trailers are disabled.
- **Progress rule** (see CLAUDE.md): the same turn progress changes, update the phase `## Progress` block, the root README status table (with the X/Y count), and the root structure tree.
