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
# 1. Feel embeddings — what is a vector? what's similarity?
uv run phase-2/01_embeddings.py

# 2. Build an index over your own .md files (coming next)
# uv run phase-2/02_build_index.py

# 3. Query the index — top-K retrieval (coming next)
# uv run phase-2/03_retrieve.py "what is tool use?"

# 4. THE SHIP — RAG chatbot. Ask questions, get answers grounded in your notes.
# uv run phase-2/04_rag_chat.py

# 5. Same chatbot, with prompt caching. Compare cost.
# uv run phase-2/05_with_caching.py

# 6. Eval — does the chatbot actually answer correctly?
# uv run phase-2/evals/eval_rag.py
```

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
