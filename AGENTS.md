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

## Phase 2 index

`phase-2/index/` is gitignored — derived data, never committed. Build with:
```bash
uv run phase-2/02_build_index.py             # no-op if exists
uv run phase-2/02_build_index.py --rebuild   # force
```

Produces `embeddings.npy` (N×384 float32) + `chunks.jsonl` (parallel metadata). ~30s build time.

## Dependency pinning quirks

- `fastembed<0.6.0` — ONNX-based embeddings, no PyTorch
- `onnxruntime<1.20` — newer versions dropped Intel Mac wheels

## Critical rules (from CLAUDE.md)

1. **Update phase README in the same turn** whenever you add/rename a file, introduce a concept, hit+fix a bug, or change run commands. Never defer.
2. **No separate doc files** — each phase has exactly one `phase-N/README.md`. No `CONCEPTS.md` or variants.
3. **Comments on WHY, not WHAT.** Short docstring at top. Inline comments only for non-obvious choices.
4. **Before marking done:** file runs end-to-end, README run-order is current, README concepts cover the file, gotchas are recorded.

## Quirks

- `importlib.import_module("02_quiz_cli")` used in eval because filenames starting with digits aren't valid Python identifiers.
- Default model `claude-haiku-4-5`. Override with `ANTHROPIC_MODEL` in `.env`.
- `count_tokens` endpoint is free (no charge).
- `.claude/settings.local.json` has an allowlist — `uv run *` and `uv sync *` are the main pattern.
- When `git init` happens: one commit per exercise + one for README updates. Don't bundle both.
