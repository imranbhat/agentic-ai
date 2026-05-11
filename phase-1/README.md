# Phase 1 — LLM mental model

**Goal:** strong intuition for how LLMs work at the API level. You don't need to train one — you need to know what knobs you have.

**Ship deliverable:** a structured-output quiz CLI ([`02_quiz_cli.py`](02_quiz_cli.py)) plus a small eval scoreboard ([`evals/eval_quiz.py`](evals/eval_quiz.py)).

---

## Run order

```bash
export PATH="$HOME/.local/bin:$PATH"

# Exercise 0 — count tokens (free endpoint, no charge)
uv run phase-1/00_count_tokens.py "In 2 sentences, what is an LLM token?"

# Exercise 1 — feel the API. Streaming tokens.
uv run phase-1/01_stream_hello.py
uv run phase-1/01_stream_hello.py "Explain transformers in 3 sentences"

# Ship deliverable — structured-output quiz CLI
uv run phase-1/02_quiz_cli.py "the Krebs cycle"
uv run phase-1/02_quiz_cli.py "Roman aqueducts" --n 3 --difficulty easy
uv run phase-1/02_quiz_cli.py "TCP handshake" --json    # raw JSON

# Eval scaffold — runs the quiz against 5 topics, scores structural checks
uv run phase-1/evals/eval_quiz.py
```

---

## What each file teaches

| File | Concept |
|---|---|
| [`00_count_tokens.py`](00_count_tokens.py) | Tokenizer intuition. Cost estimation. Why leading spaces and acronyms matter. |
| [`01_stream_hello.py`](01_stream_hello.py) | The bare API. Streaming. Token usage. The fact that an LLM call is just an HTTP request. |
| [`02_quiz_cli.py`](02_quiz_cli.py) | **Tool use as forced structured output.** This pattern is the foundation of agents. |
| [`evals/eval_quiz.py`](evals/eval_quiz.py) | Eval-first habit. Structural checks before semantic judges. |

---

## The 8 core concepts

Come back here whenever a Phase 2+ concept stops making sense — it's almost always one of these eight things.

### 1. Token

A chunk of text the model thinks in — usually 3–5 characters of English. The model **reads tokens, writes tokens, and you pay per token.** Common words are 1 token (`the`); rare words split (`tokenization` → 3 tokens). Spaces matter — `token` and ` token` are different tokens. Acronyms (`LLM`) and non-English text use more tokens per character.

### 2. Message format

The wrapper you put your text in:

```python
{"role": "user", "content": "your prompt"}
```

Universal across Claude, GPT, Gemini. A conversation is a list of these. `role` is `user`, `assistant`, or `system` (instructions). That's the whole format.

### 3. The API call

A plain HTTPS POST to `api.anthropic.com`. The Python SDK is a thin wrapper. **No magic** — your code sends JSON, their server sends JSON back.

### 4. Streaming

Instead of waiting 10 seconds for the full reply, the server sends tokens as it generates them. Better UX, and you can stop early. Same data, different delivery.

### 5. `max_tokens`

A cap on how many tokens the model is allowed to generate in *one* response. **If it hits the cap mid-output, the response is truncated, not failed.** This bit us in the eval — the model produced half a JSON object and Pydantic crashed reading fields that weren't there. Always set this with headroom for structured output.

### 6. Tool use

You hand the model a list of "tools" — each one has a name, a description, and a JSON schema for its arguments:

```python
tools = [{
    "name": "submit_quiz",
    "description": "Submit a structured quiz",
    "input_schema": { ... }
}]
```

The model's response can be **prose**, or it can be a **tool call** (the tool's name + filled-in arguments matching the schema). You decide what to do with the call.

**This one concept is 80% of agent code.**

### 7. Forced tool use (`tool_choice`)

Tells the model it **must** call a specific tool — no rambling, no choosing:

```python
tool_choice={"type": "tool", "name": "submit_quiz"}
```

Turns "I hope you give me JSON" into "the API contract requires you give me JSON." The most reliable way to get structured output.

### 8. Eval

A test suite for AI. A small set of inputs + checks (cheap structural ones, then expensive LLM-as-judge ones) that you run whenever you change a prompt or model. Without evals you're flying blind. Our 5-row JSONL + 5 boolean checks is already a real eval.

---

## Tool use, two ways

This is the distinction worth memorizing. The **same API mechanism** powers two completely different use cases:

### Mode A — Real tools (the agent pattern)

```python
for block in response.content:
    if block.type == "tool_use" and block.name == "search_web":
        results = my_real_search_function(block.input["query"])  # ← actually run it
        # then send results BACK to the model so it can keep working
```

The model "calls" your tool. **Your code actually runs something** — searches the web, queries a database, executes Python — and feeds the result back. The model keeps going. This loop **is** what an agent is.

### Mode B — Fake tools as a structuring trick (what we did in `02_quiz_cli.py`)

```python
for block in response.content:
    if block.type == "tool_use":
        return Quiz(**block.input)   # ← just KEEP the arguments. Never run anything.
```

There is no `submit_quiz` function anywhere. We don't run anything. We hijack the tool-use mechanism because **forcing the model to fill in a schema is the most reliable way to get structured JSON.** The model thinks it's calling a function. It's actually just filling out a form for us.

| Mode | When | What runs after the tool call |
|---|---|---|
| **A — Real tool** | You want the model to take actions | Your real function executes; result goes back to model |
| **B — Fake tool (structuring)** | You want typed JSON output | Nothing. You just keep `block.input` as your data |

**Naming convention for fake tools:** name them after the thing being produced (`submit_quiz`, `extract_invoice`, `classify_email`), not after an action.

---

## How the 8 concepts fit together

```
You write a PROMPT
    └─ wrap it in MESSAGE format
        └─ send via API CALL
            └─ ask for STREAMING (or not)
                └─ optionally include TOOLS (with TOOL_CHOICE for structure)
                    └─ model generates up to MAX_TOKENS tokens
                        └─ EVAL the output to know if it's any good
```

Every agent system you'll ever build is a longer chain of these same eight links.

---

## Gotchas we hit (write these on a sticky note)

1. **Truncated structured output is silent.** If `max_tokens` is too low and the model is mid-JSON, you get a "successful" response with broken JSON. Detect by checking `response.stop_reason == "max_tokens"` and erroring loudly.
2. **Eval scoreboards lie if you let them.** Errored runs that contribute `0/0` to the score inflate the headline percentage. Decide your error-counting policy *before* you trust the number.
3. **Mix difficulty in your eval set.** All easy topics will mask `max_tokens`-class bugs that only appear under load. Our hard topic ("Bayesian vs frequentist") is the only one that caught the bug.
4. **`load_dotenv()` doesn't override existing env vars by default.** If something in your shell sets `ANTHROPIC_API_KEY=""` (an empty string — not unset, *empty*), `dotenv` silently respects it and your script fails auth even though `.env` has a valid key. The fix: `load_dotenv(override=True)` in any script that reads from `.env`. **Lesson: silent precedence rules cause more debugging pain than loud errors.**

---

## Per-file concept map

| File | Concepts used |
|---|---|
| [`00_count_tokens.py`](00_count_tokens.py) | 1 (token), 2 (message format), 3 (API call) |
| [`01_stream_hello.py`](01_stream_hello.py) | 1, 2, 3, 4 (streaming), 5 (max_tokens) |
| [`02_quiz_cli.py`](02_quiz_cli.py) | All of the above + 6 (tool use, Mode B) + 7 (forced tool use) |
| [`evals/eval_quiz.py`](evals/eval_quiz.py) | 8 (eval) wrapping all of the above |

---

## Next: Phase 2

Phase 2 introduces three more concepts on top of these eight:

- **Embeddings** — turning text into a vector of numbers so you can compare meaning.
- **RAG (retrieval-augmented generation)** — chunking documents, retrieving relevant pieces, stuffing them into the prompt as context.
- **Prompt caching** — Anthropic-specific. Cache long prompt prefixes to slash cost and latency on repeated calls.

Plus your first real **LLM-as-judge** eval — using one model to score another model's output for semantic correctness, not just structure.

→ [`phase-2/README.md`](../phase-2/README.md)
