# Phase 2 — LLM application primitives

**Goal:** you can build any non-agentic LLM app from scratch.
**Ship deliverable:** a RAG chatbot over your own markdown files, with an LLM-as-judge eval set.

## New concepts (added to the 8 from Phase 1)

| # | Concept | One-line |
|---|---|---|
| 9 | **Embedding** | A vector of numbers representing the meaning of text. |
| 10 | **Cosine similarity** | A cheap way to score how close two embeddings are (-1 to 1). |
| 11 | **Chunking** | Splitting a long doc into bite-sized passages before embedding. |
| 12 | **Vector index** | A data structure for fast nearest-neighbor lookup over many vectors. |
| 13 | **Retrieval** | At query time: embed the question, find top-K closest chunks. |
| 14 | **RAG (retrieval-augmented generation)** | Stuff retrieved chunks into the prompt, then generate. |
| 15 | **Prompt caching** | Cache long prompt prefixes server-side. Anthropic-specific superpower. |
| 16 | **LLM-as-judge** | Use one LLM call to score another LLM call's output for semantic correctness. |

## File order (build in sequence)

```bash
# 1. ✅ Feel embeddings — what is a vector? what's similarity?
uv run phase-2/01_embeddings.py

# 2. ✅ Chunk + embed your own .md files; save the index to disk.
uv run phase-2/02_build_index.py             # build (no-op if exists)
uv run phase-2/02_build_index.py --rebuild   # force rebuild

# 3. ✅ Query the index — top-K retrieval.
uv run phase-2/03_retrieve.py "what is tool_choice?"
uv run phase-2/03_retrieve.py "how do embeddings work?" --k 3
uv run phase-2/03_retrieve.py "RAG" --full --show-bottom

# 4. ✅ THE SHIP — RAG chatbot. Ask questions, get answers grounded in your notes.
uv run phase-2/04_rag_chat.py "what is forced tool use?"
uv run phase-2/04_rag_chat.py "how does our chunker fail?" --k 5
uv run phase-2/04_rag_chat.py            # interactive REPL mode

# 5. ✅ Different RAG: stuff entire corpus in prompt, cache the prefix.
uv run phase-2/05_with_caching.py "what is forced tool use?"
uv run phase-2/05_with_caching.py            # interactive — feel the cache hits

# 6. ✅ Eval — LLM-as-judge across retrieval / generation / refusal
uv run phase-2/evals/eval_rag.py
```

## What `02_build_index.py` produces

```
phase-2/index/
├── embeddings.npy    # numpy array, shape (N, 384) — one row per chunk
└── chunks.jsonl      # one chunk per line: {id, file, chunk_index, n_chars, text}
```

The two files share row ordering — `embeddings.npy[k]` is the vector for `chunks.jsonl` line `k`.
This split (vectors in numpy, metadata in JSONL) keeps things inspectable: you can `head chunks.jsonl` to see what got indexed. Real systems graduate to a vector DB (Chroma, pgvector, Pinecone), but starting raw makes the mechanics visible.

The `phase-2/index/` directory is gitignored — it's derived from the `.md` source files.

## How retrieval works (Exercise 3)

`03_retrieve.py` loads the two index files, embeds your query, scores it against every chunk in one matrix op, and prints the top K. Per-query cost:

- one embed call (small, ~50ms)
- one (N × 384) · (384,) dot product (microseconds for 81 chunks; fast even at 100k+)

Three flags worth knowing:
- `--k 3` — change how many results you want
- `--full` — show entire chunk text, not a preview
- `--show-bottom` — also print the 3 *lowest*-scoring chunks. Useful for sanity-checking that the retriever is correctly *rejecting* irrelevant chunks, not just elevating relevant ones.

Cosine similarity rules of thumb: **>0.5** usually relevant, **>0.7** strong, **>0.85** near-duplicate, **<0.3** irrelevant. Calibrate on your own corpus — these vary by domain.

## How RAG works (Exercise 4 — the ship)

`04_rag_chat.py` is where retrieval finally meets generation:

```
question → embed → top-K chunks → <context> prompt → Claude streams → cited answer
```

Three things this file does that earlier files didn't:

1. **Wraps chunks in XML tags** (`<passage id="1" source="..."`). Anthropic's docs recommend this over free text concatenation — it's clearer to the model where the passages end and the question begins.
2. **Uses the system prompt as a guardrail.** The system prompt tells Claude to cite passage numbers, refuse to guess if the answer isn't in the context, and surface contradictions instead of picking one silently. This is the single biggest hallucination-prevention lever in RAG.
3. **Shows what was retrieved before generating.** The user sees which chunks the model is about to read — RAG is debuggable only when the retrieved set is visible.

Two flags:
- `--show-context` — print the entire prompt sent to Claude (useful for diagnosing weird answers)
- `--k 5` — retrieve more chunks (more context = more cost; balance against answer quality)

Run with no question → interactive REPL. Model and index load once, you ask as many follow-ups as you want.

## The RAG eval (Exercise 6)

`evals/eval_rag.py` is your first **LLM-as-judge** eval. Phase 1's eval only checked structural shape (was JSON valid?). RAG answers are prose — you can't grade prose with deterministic checks. So another LLM does the grading.

The eval set lives in `evals/eval_set.jsonl` — 10 rows: 8 in-corpus questions with reference answers + expected source files, plus 2 out-of-corpus "should refuse" questions.

For each row we measure **three independent things**:

| Dimension | How it's measured | LLM call? |
|---|---|---|
| **Retrieval@K** | Did top-K include the expected source file? | No — deterministic |
| **Generation** | Judge scores correctness, completeness, groundedness (1-5 each, averaged) | Yes — Sonnet judges Haiku |
| **Refusal** | Substring match against known refusal phrases | No — deterministic |

**Why grade each dimension separately?** Because retrieval failing and generation failing are *different bugs needing different fixes*. A bad retrieval can be fixed by better chunking. A bad answer with good retrieval needs prompt-engineering or a stronger model. A single conflated score hides the diagnosis.

**Why Sonnet judges Haiku?** Self-grading is biased — Haiku grading itself tends to be lenient. Pairing a stronger judge with a weaker generator is the standard pattern.

A full eval run makes ~20 API calls and costs ~$0.02–0.05 — cheap enough to run on every prompt-engineering change.

## The cached-context pattern (Exercise 5)

`05_with_caching.py` is a *different* RAG architecture for small corpora. Instead of retrieving top-K chunks per query, it puts the **entire corpus** in the prompt — and marks it as cacheable.

```
system + entire corpus  ─ CACHED ─→  paid 1.25× ONCE, then 0.1× per hit
question (varies)        ─────────→  paid normally
```

Cache lifetime: 5 minutes (ephemeral). Cache write is slightly more expensive than a normal call (1.25× input cost). Cache read is dirt cheap (0.1× input cost). After two queries against the same cached prefix, you're already net cheaper than no caching.

**Two patterns, side by side:**

| Pattern | Implementation | Best when |
|---|---|---|
| Vector search (`04_rag_chat.py`) | Embed query → top-K chunks → small prompt | Corpus is large (> ~50k tokens) or grows over time |
| Cached context (`05_with_caching.py`) | Stuff whole corpus → cache the prefix → ask | Corpus is small (≤ ~50k tokens) and relatively stable |

For 90% of internal-docs RAG, the cached-context pattern is simpler, cheaper, and just as good. The vector-search version becomes necessary only when the corpus outgrows the context window.

Two API mechanics worth noting:
- Wrap cacheable content in a `{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}` block — that marks "everything up to here is the cacheable prefix."
- `usage.cache_creation_input_tokens` (paid 1.25×) and `usage.cache_read_input_tokens` (paid 0.1×) are returned alongside `usage.input_tokens` — the cost breakdown.

## Chunking is a real lever

The chunker in `02_build_index.py` is intentionally simple: split on paragraph boundaries, greedy-pack toward ~500 chars. **Chunking strategy is one of the biggest levers in RAG quality.** Once retrieval works, come back and try smarter splitters (markdown-aware, semantic, recursive character) and watch the eval score move.

## What's different from Phase 1

- **First non-Anthropic dependency.** sentence-transformers runs locally — no API key, no per-call cost. Embeddings will use your CPU and a ~130MB model cached in `~/.cache/huggingface`.
- **First time we touch state on disk.** The index gets pickled. Real RAG systems use a vector DB (Chroma, pgvector, Pinecone) — we'll start with numpy + a JSON sidecar to keep the mechanics visible.
- **First time we build something *useful* to you.** A chatbot over your own learning notes. Use it.

## Experiments to build embedding intuition

Edit the `texts` list in `01_embeddings.py` and rerun. Predict the result first, then check.

| Try | Expect | Lesson |
|---|---|---|
| `"happy"`, `"joyful"`, `"elated"` | all pairs ~0.75+ | embeddings know synonyms |
| `"hot day"`, `"cold day"` | ~0.85 (surprise!) | antonyms aren't opposites in vector space — they share concepts |
| `"elephant"`, `"elephnat"` | ~0.75 | robust to typos |
| `"dog"`, `"perro"`, `"chien"` | ~0.4 | BGE-small is English-only; model choice matters |
| Python vs JavaScript snippet of same function | ~0.7 | code semantics translate across languages |
| `"AI is awesome"` vs a 30-word AI definition | high | embeddings care about meaning, not length |

Also try changing the `query` in section 4 — e.g. `"animals"` retrieves all pet sentences; `"weather"` retrieves nothing relevant.

## Reading while you wait for the model download

While the BGE model downloads (~130MB, one-time), read these — they're the canonical references for Phase 2:

- [The Illustrated Word2vec](https://jalammar.github.io/illustrated-word2vec/) — Jay Alammar, why embeddings work
- [Anthropic — Prompt Caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) — the docs
- [Anthropic — Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) — the modern RAG upgrade
