# learn-ai — Full Chat Transcript

A reconstructed record of the conversations that built this project, from Phase 1 setup through Phase 3 complete (the research agent and its eval — all 6 deliverables shipped).

**Note on faithfulness:** User messages are verbatim. Assistant responses are reconstructed from working memory — accurate in substance but the exact wording of long passages may differ slightly from what was originally written. Tool calls (bash commands, file writes, etc.) are summarized where relevant; the full output isn't reproduced. For the canonical artifacts, see the files in the repo.

---

## Session 1 — Phase 1 setup

**User:**
> I need to learn AI, primarily agentic AI, give me a clear path or roadmap.
>
> /model claude-opus-4-7
> Kick off phase 1

**Assistant:**
Set up Phase 1: a small Python project with a streamed hello-world, the structured-output quiz CLI (the ship deliverable), and an eval scaffold so we build the eval-first habit from day one.

Found the project at `/Users/imranbhat/cosmos/ai/claude/learn-ai`, system Python was 3.9.6 (too old). Installed `uv` (Astral's Python toolchain — the modern standard) to `~/.local/bin`. Created:

- `pyproject.toml` with anthropic, pydantic, python-dotenv, rich
- `.env.example` template
- `.gitignore`
- `phase-1/01_stream_hello.py` — streamed API call with usage tracking
- `phase-1/02_quiz_cli.py` — the ship: forced tool use → guaranteed JSON
- `phase-1/evals/eval_quiz.py` — 5-row eval set with structural checks
- `README.md` — project overview and run instructions

Ran `uv sync`, installed anthropic 0.100.0 + deps. All three files passed syntax checks.

Said: "Two things to do now — copy `.env.example` to `.env`, paste your key, then run the three scripts in order."

---

**User:**
> Traceback (most recent call last):
>   File "phase-1/01_stream_hello.py", line 28, in <module>
>     with client.messages.stream(...) as stream:
> anthropic.BadRequestError: Error code: 400 - 'Your credit balance is too low to access the Anthropic API.'

**Assistant:**
Good news: the setup works end-to-end. The API call left your machine, hit Anthropic, authenticated, and was rejected at billing. Everything before the credit check is correct.

You need credits on the Anthropic account. Two paths:

**Path A (recommended) — add $5 at console.anthropic.com/settings/billing.** At Haiku 4.5 prices (~$0.004/quiz), $5 buys ~1,400 runs.

**Path B — free tier on a different provider.** Refactor to OpenRouter/Groq/Gemini. Tradeoff: the rest of the roadmap leans on Claude-specific things.

Recommendation: Path A. The whole roadmap through Phase 5 will cost you well under $20.

---

**User:**
> i have claude max plan

**Assistant:**
Important clarification — **Max plan and API credits are separate products**:

- **Claude Max** ($100–200/mo) → Claude.ai web/desktop, Claude Code. Subscription-based.
- **Anthropic API** (console.anthropic.com) → pay-per-token, used when code calls `api.anthropic.com` directly.

The Python script calls the API directly, so it needs API credits. Max doesn't carry over.

Two real options:
- **Add $5 in API credits** (recommended). Standard learning path. Phase 1's pedagogical point requires hitting the bare API.
- **Refactor to Claude Agent SDK with Max auth.** Higher-level abstraction; you'd miss what's underneath.

My honest recommendation: spend the $5. The blind spot from option 2 is real and you'll feel it later.

---

**User:**
> how to add 5 dollars?

**Assistant:**
1. Go to https://console.anthropic.com/settings/billing
2. Sign in with the same email your API key belongs to
3. Click **"Add to credit balance"** (top-right)
4. Enter **$5** and card details
5. Submit — credits appear instantly

Two gotchas:
- **Wrong organization** — if you're in multiple orgs, use the switcher (top-left). Credits must be on the same org that owns the key in `.env`.
- **Auto-reload off by default** — skip for now.

---

## Phase 1 — Running the exercises

**User:**
[Ran `01_stream_hello.py` successfully and shared partial output]
> how many tokens is this "In 2 sentences, what is an LLM token?" and how did you calculate?

**Assistant:**
Great question — exactly the right thing to be curious about in Phase 1.

**The string `"In 2 sentences, what is an LLM token?"` is approximately 11 tokens by itself.** When wrapped in an API message it becomes roughly **16–20 input tokens** total because of message structure overhead.

Tokens are **subword units**, not words. Claude uses a variant of **Byte-Pair Encoding (BPE)**. Walked through a plausible split:

| Token | Note |
|---|---|
| `In` | 1 token |
| ` 2` | leading space + digit |
| ` sentences` | 1 token (leading space matters!) |
| `,` | punctuation |
| ` what`, ` is`, ` an` | common words |
| ` LL`, `M` | "LLM" is uppercase + uncommon → splits |
| ` token`, `?` | 1 token each |

≈ **11 tokens**.

Three things to internalize:
1. **Leading spaces are part of the token.** ` token` and `token` are different.
2. **Acronyms often split.**
3. **Numbers are often per-digit.**

Rule of thumb: ~4 characters per token, ~1.3 tokens per word.

Offered to add `phase-1/00_count_tokens.py` to demonstrate properly.

---

**User:**
> yes

**Assistant:**
Built `phase-1/00_count_tokens.py` — calls the free `count_tokens` endpoint, prints character/word/token counts and per-model cost estimates. Updated README to add it as Exercise 0.

Suggested experiments:
- `"token"` vs `" token"` — different tokens because of leading space
- `"the the the"` — ultra-common words = cheap
- `"LLM AI API"` — acronyms split badly
- `"トークン化"` — same word in Japanese, way more tokens

---

**User:**
> i ran all of this and below is the output of last one
> [Eval scoreboard showing 4 passes, 1 ERROR for "Bayesian vs frequentist", "Overall: 20/20 (100%)"]

**Assistant:**
This is the best possible Phase 1 outcome. Your eval just earned its keep — caught a real bug.

**What happened:** "Bayesian vs frequentist" (difficulty=`hard`) errored with `questions: Field required`. The model's tool-call JSON came back without the `questions` field.

The almost-certain cause: **`max_tokens=1500` was too low for a hard topic.** When the model generates a tool-call and hits the token cap mid-JSON, you get truncated structured output — sometimes missing whole fields.

**A second, sneakier bug — in the eval itself.** The summary `20/20 (100%)` is wrong. The errored row contributed 0/0 (zero pass, zero total) instead of 0/N. The failure silently disappeared from the score.

**Two fixes:**
1. Bumped `max_tokens` from 1500 to 4096 in `02_quiz_cli.py`
2. Added a `stop_reason == "max_tokens"` check that raises a clear error
3. Made the eval count errored runs as full failures, with separate "runs ok / errored" tally

**Three lessons in 5 minutes:**
1. `max_tokens` is a footgun for structured output — truncated JSON is silent
2. Difficulty distribution matters in eval sets
3. Evals lie if you let them

This is how you build agent intuition — not by reading theory, but by running things and watching them break.

---

**User:**
> explain to me in simple terms what we did at code level in each phase?

**Assistant:**
Walked through each file at the code level in plain language:

**`00_count_tokens.py`** — "How big is my prompt?"
```python
client = Anthropic()                          # connection
resp = client.messages.count_tokens(...)      # free endpoint
print(resp.input_tokens)                      # the number
```
A calculator endpoint. No model "thinks."

**`01_stream_hello.py`** — Send a message, get an answer one token at a time
```python
with client.messages.stream(model="claude-haiku-4-5", ...) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```
The chat format `{"role": "user", "content": ...}` is universal. `final.usage` is the receipt.

**`02_quiz_cli.py`** — The interesting one
Three moves:
1. Describe the JSON shape as a "tool" with an input_schema
2. Send the request with `tool_choice={"type": "tool", "name": "submit_quiz"}` — forces it
3. Pull the structured data out: `block.input` IS the JSON

**`evals/eval_quiz.py`** — Run the function 5 times and check it didn't lie. Cheap structural checks first; expensive LLM-as-judge later.

| File | What's the model doing? |
|---|---|
| `00_count_tokens.py` | Nothing. Just tokenizing. Free. |
| `01_stream_hello.py` | Generating prose, token by token. |
| `02_quiz_cli.py` | Filling in arguments to a fake function. |
| `evals/eval_quiz.py` | Wrapping the above in a measurement loop. |

Every piece of agentic AI later is a recombination of these four primitives.

---

**User:**
> can you explain the basic concepts we used here in simpler but concise way

**Assistant:**
The 8 core concepts:

1. **Token** — a chunk of text (~4 chars of English), what you're billed on
2. **Message format** — `{"role": "user", "content": "..."}`, universal across providers
3. **API call** — plain HTTPS POST to api.anthropic.com
4. **Streaming** — tokens arrive as generated
5. **`max_tokens`** — cap on output; truncates silently when hit
6. **Tool use** — model can "call" functions you describe with JSON schemas. Two modes: real (agent) and fake (structured output).
7. **Forced tool use (`tool_choice`)** — model MUST call a specific tool
8. **Eval** — test suite for AI

How they fit together:
```
PROMPT → MESSAGE format → API CALL → STREAMING (or not)
       → optionally TOOLS (with TOOL_CHOICE) → max_tokens cap → EVAL
```

---

**User:**
> ..."submit_quiz" is an existing tool or we just created a fake one?

**Assistant:**
**We invented it. `submit_quiz` exists only in our Python file.** There is no Anthropic tool called `submit_quiz`. The API doesn't know or care whether tools you describe actually exist anywhere.

Two completely different things people do with tool use:

**Mode A — Real tools (the agent pattern):**
```python
for block in response.content:
    if block.type == "tool_use" and block.name == "search_web":
        results = my_real_search_function(block.input["query"])  # ← actually run
        # send results BACK to model
```

**Mode B — Fake tools as structuring trick (what we did):**
```python
for block in response.content:
    if block.type == "tool_use":
        return Quiz(**block.input)   # ← just KEEP the arguments
```

There is no `submit_quiz` function anywhere. We hijack the tool-use mechanism because **forcing the model to fill in a schema is the most reliable way to get structured JSON.**

Same API mechanism. The only difference is whether your code does anything after extracting `block.input`.

---

**User:**
> summarize the above in an md file with link to it from main

**Assistant:**
Created `phase-1/CONCEPTS.md` (later renamed to `phase-1/README.md`) with the 8 concepts, the two modes of tool use, gotchas, and the pipeline diagram. Linked from main README.

---

## Phase 2 — RAG primitives

**User:**
> let's move to next phase

**Assistant:**
Phase 2 is bigger — 2 weeks of work. Setting up the foundation and Exercise 1 first.

**Phase 2 plan (the arc):**
```
01_embeddings.py       feel embeddings + similarity
02_build_index.py      chunk + embed corpus → disk
03_retrieve.py         top-K retrieval
04_rag_chat.py         THE SHIP: full RAG chatbot
05_with_caching.py     prompt caching
evals/eval_rag.py      LLM-as-judge
```

Created:
- `pyproject.toml` updated with sentence-transformers + numpy
- `phase-2/README.md` with phase plan
- `phase-2/01_embeddings.py` — embedding basics, cosine similarity, top-K preview

**Hit a snag:** PyTorch 2.11 has no Intel Mac wheels. Switched to fastembed (ONNX-based). Then hit it again — ONNX runtime 1.25 also dropped Intel Mac. Pinned `onnxruntime<1.20`. Install succeeded.

**Lesson recorded:** ML library platform support changes fast — pinning is sometimes the right answer.

---

**User:**
> how to change the inputs to understand better... and explain to me the jargons you used so far in simpler way

**Assistant:**
Two answers — experiments first, then glossary.

**Experiments to try in `01_embeddings.py`** — edit the `texts` list and rerun. Predict first, then check:

| Try | Expect | Lesson |
|---|---|---|
| `"happy"`, `"joyful"`, `"elated"` | ~0.75+ | embeddings know synonyms |
| `"hot day"`, `"cold day"` | ~0.85 (surprise!) | antonyms aren't opposites in vector space |
| `"elephant"`, `"elephnat"` | ~0.75 | robust to typos |
| `"dog"`, `"perro"`, `"chien"` | ~0.4 | BGE-small is English-only |
| Python vs JavaScript code | ~0.7 | code semantics across languages |
| `"AI is awesome"` vs 30-word definition | high | meaning, not length |

**Plain-language glossary** — saved to `GLOSSARY.md`, covering:
- Core LLM mechanics (LLM, token, prompt, message, API, SDK, streaming, max_tokens, context window, stop_reason, usage)
- Shaping output (structured output, JSON schema, tool use real/fake, tool_choice, tool call)
- Quality (eval, structural check, LLM-as-judge, Pydantic, validation)
- Search by meaning (embedding, vector, dimension, cosine similarity, dot product, normalization, top-K, chunking, vector index, RAG)
- Models and providers (provider, model tier, local vs API model)
- Tooling we touched (uv, ONNX, PyTorch, Hugging Face, CLAUDE.md, hook)
- "Which is which?" cheat-sheet for common confusions

---

**User:**
> Setup the rule to keep updating the corresponding readme.md as the conversation goes... also rename the concepts.md to standard README.md in phase 1

**Assistant:**
Two things done:

1. **Renamed `phase-1/CONCEPTS.md` → `phase-1/README.md`** and merged the run-order section in. Each phase now has one self-contained README. Slimmed root README to be a brief overview with a phase status table linking to per-phase READMEs.

2. **Created `CLAUDE.md`** at project root — the canonical Claude Code mechanism for project-scoped rules. Auto-loaded into every future session. Key rules:
   - When adding files, concepts, gotchas → update `phase-N/README.md` in the same turn
   - Root README is overview-only
   - Teach, don't just ship; comments on WHY not WHAT
   - One concept per file
   - Anthropic-first

Why CLAUDE.md vs a hook: CLAUDE.md is the standard mechanism; a hook would fire on every edit creating noise. CLAUDE.md is right.

---

## Phase 2 continued — chunking, retrieval, RAG

**User:**
> let's move to next phase / [eventually:] next

**Assistant:**
Built `phase-2/02_build_index.py` — chunked the 6 .md files in the project (CLAUDE.md, GLOSSARY.md, README.md, ROADMAP.md, phase-1/README.md, phase-2/README.md) into 81 chunks (median ~420 chars), embedded each chunk, saved to:
- `phase-2/index/embeddings.npy` (81, 384) float32 — vectors
- `phase-2/index/chunks.jsonl` — one chunk per line, parallel metadata

Row order shared between files: `embeddings[k]` corresponds to `chunks.jsonl` line k.

Gitignored `phase-2/index/` (derived data).

---

**User:**
> tell me more about phase 2 02_build_index and the chunking strategy... how do i make sense of @phase-2/01_embeddings.py and @chunks.jsonl

**Assistant:**
Walked through:
- **chunks.jsonl format** — 5 fields per row: id, file, chunk_index, n_chars, text
- **Chunking algorithm** — 4 lines: split on `\n\n`, greedily pack to ~500 chars, single oversized paragraphs stay whole
- **Connection between `01_embeddings.py` (lab demo) and `02_build_index.py` (production line)** — same `embed()` function, more rows
- **Two real flaws visible in the data**:
  - Heading-orphan chunks like `"## Quality assurance"` (20 chars, useless)
  - Oversized table chunks (1703 chars — a markdown table with no paragraph breaks)

Suggested inspection commands the user could run.

---

**User:** [Ran the inspection commands and shared output]

**Assistant:**
Real numbers: `p10=39, p50=420, p90=746, max=1703`. Found that I had given wrong chunk IDs in my exercise (id=26, id=23 weren't the outliers I claimed). The real outliers: `id=12` (smallest, 20 chars `"## Quality assurance"`) and `id=9` (largest, 1703-char glossary table).

**Discovered systematic chunker failure**: 5 of GLOSSARY.md's 16 chunks (31%) are heading orphans because the chunker refuses to combine a small chunk with an oversized one. Showed the one-line fix (`MIN_CHUNK_SIZE = 100` floor).

Lesson: I told the user wrong IDs confidently. Never trust an LLM's specific numbers without inspecting the artifact. The chunks.jsonl being human-readable is what made my mistake visible.

---

**User:**
> A
> [chose to build retrieval first, then improve chunker]

**Assistant:**
Built `phase-2/03_retrieve.py` — loads index, embeds query, dot-product against all 81 chunks, top-K with file/score breadcrumbs. Three flags: `--k`, `--full`, `--show-bottom`.

Tested on "what is tool_choice and why does it matter?" — top 3 results all from phase-1/README.md chunks 8/10/11 (scores 0.79, 0.71, 0.71). The retriever correctly found the region of the corpus where the concept lives. Bottom-3 scored ~0.49-0.51 because the corpus is topically narrow (everything is about AI), so the floor is high.

---

**User:**
> ok, let us go to next step

**Assistant:**
Built `phase-2/04_rag_chat.py` — the ship deliverable. Three new ideas:

1. **XML-tagged passages** (`<passage id="N">`) — Anthropic-recommended
2. **System prompt as guardrail** — answer from passages only, cite [N], refuse if not covered, surface contradictions
3. **Show-your-work UI** — print retrieved chunks before generation

Includes one-shot CLI and interactive REPL.

**Bug hit:** `load_dotenv()` returned True but `ANTHROPIC_API_KEY` was empty — the shell had it set to empty string. By default `load_dotenv()` doesn't override existing env vars.

**Fix:** `load_dotenv(override=True)` in all four scripts that use the API. Recorded as gotcha #4 in `phase-1/README.md`.

After fix, the system worked beautifully. Test query "what is forced tool use and why does it matter?" got a clean answer with citations `[1]`, `[4]` referencing the actual retrieved chunks. Cost: $0.0012.

---

**User:**
> got this answer for first one
> "The context doesn't cover this. The passages provided discuss AI/LLM concepts like structured output, tool use, and prompt engineering—not baking or sourdough recipes."

**Assistant:**
Better than expected. Three things it did right:
1. Refused, using the exact phrase from the system prompt
2. No fake citations
3. Helpfully named what the corpus DOES cover

**The big tradeoff:** Without RAG, ask Claude "how do I make sourdough?" and you get a recipe. RAG made Claude pretend not to know — by design.

Two production patterns:
- **Strict RAG** (what we built) — used in legal/medical/customer-service
- **Augmented chat** — falls back to general knowledge with citation

Switching is one paragraph in the system prompt.

---

**User:**
> where were the guardrails set?

**Assistant:**
In two places in `04_rag_chat.py`:

**Line 60 — the prompt content:**
```python
SYSTEM_PROMPT = """You are a precise assistant that answers questions using ONLY...

Rules:
- Cite the passage number(s)...
- If the passages do not contain the answer, say "The context doesn't cover this"...
- Synthesize across passages...
- ...
"""
```

**Line 144 — wired into the API call:**
```python
with client.messages.stream(
    model=args.model,
    system=SYSTEM_PROMPT,   # ← here
    ...
)
```

The `system=` parameter is the difference between "polite suggestion buried in the user message" and "behavioral rules the model treats as binding."

Anthropic and OpenAI train their models so `system` messages have **priority** over `user` messages in conflicts. This is the front line against prompt injection.

---

**User:**
> ok, let us go to next step

**Assistant:**
Built `phase-2/evals/eval_rag.py` — first real LLM-as-judge eval. Three independent dimensions per row:

1. **Retrieval@K** — deterministic: did expected file land in top-K?
2. **Generation** — LLM-as-judge: Sonnet grades Haiku on correctness/completeness/groundedness (1-5 each)
3. **Refusal** — deterministic: substring match on refusal phrases

Created `phase-2/evals/eval_set.jsonl` with 10 rows: 8 in-corpus + 2 out-of-corpus.

**Ran the eval. Results:**
- Retrieval@4: 7/8 (88%)
- Generation: avg 3.92/5
- Refusal: 2/2 (100%)

**Two real bugs surfaced:**
- Row 4 ("What is RAG?") — retrieval miss, generation still scored 4.0 (other chunks happened to cover it)
- Row 8 ("model tiers") — retrieval passed but generation got 1.0/5 (likely retrieved the heading-orphan chunk we found earlier)

Two different failure modes requiring two different fixes. **This is what evals are for.**

---

## Phase 2 ship — prompt caching

**User:**
> start with the caching part?

**Assistant:**
Built `phase-2/05_with_caching.py` — a *different* RAG architecture for small corpora. Instead of vector search, stuff the entire 81-chunk corpus into the prompt and mark it as cacheable.

```python
system=[
    {"type": "text", "text": SYSTEM_PROMPT},
    {"type": "text", "text": corpus_blob, "cache_control": {"type": "ephemeral"}},
]
```

**Ran two queries to demonstrate the cache miss → cache hit pattern:**

**Query 1 (cache MISS, first time):**
- cache_write: 11,730 tokens
- cost: $0.0127
- vs uncached: $0.0103 — **23% MORE expensive** on first call

**Query 2 (cache HIT, immediately after):**
- cache_read: 11,730 tokens
- cost: $0.0018
- vs uncached: $0.0103 — **82% CHEAPER**

**Break-even at N=2 queries.** After that, savings approach ~90%.

Two RAG patterns side by side: vector search (scales to millions of docs) vs cached context (works for ≤50k tokens, simpler, often better for internal docs).

---

**User:**
> what is my progress now?

**Assistant:**
Provided milestone summary — Phase 2 was officially shipped. 16 concepts internalized, 6 war stories survived, ~35% through the roadmap. Phase 3 (agents) ahead.

---

## Git commits and remote

**User:**
> commit to local git with multiple commits meaningful and create a new repo in my remote github named "agentic-ai"

**Assistant:**
Made 8 logical commits since the last commit:
1. `fix(env): use load_dotenv(override=True)`
2. `chore: gitignore the generated vector index directory`
3. `feat(phase-2): chunk + embed corpus, save index to disk`
4. `feat(phase-2): top-K retrieval over the indexed corpus`
5. `feat(phase-2): RAG chatbot — ship deliverable`
6. `feat(phase-2): LLM-as-judge eval for the RAG system`
7. `feat(phase-2): cached-context RAG with prompt caching`
8. `docs(phase-2): comprehensive README + AGENTS.md + experiment lines`

Created remote: https://github.com/imranbhat/agentic-ai (private). Pushed. Branch tracks origin/main.

---

**User:**
> update the phase 2 completion status / yes [commit and push]

**Assistant:**
Updated root README status table:
- Phase 2: 🚧 in progress → ✅ shipped
- Phase 3: — → 🔜 next

Refreshed the project structure tree with all the actual files. Committed and pushed as `docs: mark Phase 2 shipped and refresh project structure`.

---

## Phase 3 — Building agents from scratch

**User:**
> next but walk me through each step clearly

**Assistant:**
Pulled the Phase 3 section from ROADMAP. Goal: understand what an agent actually is before reaching for a framework. Ship: research agent in ~200 lines (web search, fetch URL, write file → cited markdown report).

**Phase 3 plan:**
```
01_agent_loop_minimal.py    THE MENTAL MODEL — two trivial math tools
02_agent_loop_robust.py     Multi-tool, error handling, cost tracking
03_research_agent.py        SHIP: the agent from the roadmap
04_react_explicit.py        Reason+Act pattern
05_self_critique.py         Self-grading + revision loop
evals/eval_research.py      Eval the agent
```

**Step 1.1:** Updated root README — Phase 3 to "🚧 in progress"

**Step 1.2:** Created `phase-3/README.md` with the plan, the 8 new concepts (agent loop, stop_reason revisited, real tool execution, tool_result blocks, growing conversation, max-iteration guard, ReAct, self-critique), and required reading.

**Step 1.3:** Built `phase-3/01_agent_loop_minimal.py` — two tools (add, multiply), question `(3+5) × (7+2)` that forces chaining.

**Step 1.4:** Ran it. Trace:
- Iter 1: model calls `add(3,5)` AND `add(7,2)` in parallel → results 8 and 9
- Iter 2: model sees results, calls `multiply(8,9)` → result 72
- Iter 3: model says "The answer is 72." → end_turn

**Step 1.5:** Walked through the five mechanics worth memorizing:
1. Exit condition is `stop_reason == "end_turn"` (NOT `block.type == "text"`)
2. Append the assistant's message BEFORE the tool result
3. Tool results are `role: "user"` even though no human is involved
4. Every tool result needs a `tool_use_id` back-reference
5. Always cap iterations

---

**User:** [interrupted] **test me**

**Assistant:** [6-question quiz testing the mechanics]

**User:** Q1: "tool_use to keep running, text to stop"

**Assistant:** Half credit (0.5/1). Got `tool_use` right but conflated two different fields:
- `response.stop_reason` is at the response level. Values: `end_turn`, `tool_use`, `max_tokens`
- `block.type` is per-content-block. Values: `text`, `tool_use`

Exit value is `"end_turn"`, not `"text"`. They're different fields with overlapping vocabularies (confusingly).

**User:** [continued through Q2-Q6]

Walked through each:
- **Q2** (text+tool_use blocks): 0.75/1 — got the iteration logic, missed that the text block is purely informational
- **Q3** (deleting the assistant.append line): 0.25/1 — too vague. Explained the specific failure: tool_results reference tool_use_id that no longer exists in any previous assistant message. API error: "tool_result block(s) provided when previous message does not contain any tool_use blocks"
- **Q4** (counting messages): 0.7/1 — said 6 entries, actually 5 because our code `return`s on `end_turn` BEFORE appending the final assistant message. Real production code would usually append it.
- **Q5** (max_iterations=2): 0.4/1 — said "right answer" but actually NO ANSWER. The math runs in 2 iterations, but the SYNTHESIS needs a 3rd iteration. Critical agent-design lesson: `iterations needed = tool-using turns + 1 synthesis turn`.
- **Q6** (divide by zero recovery): 0.85/1 — well captured. Errors round-trip as tool_result content so the model can self-recover.

Final: 3.45 / 6 (58%). Shape solid, precision still developing.

Asked: ready for Exercise 2 (robust loop with practice) or Exercise 3 (jump to research agent)?

---

**User:**
> commit locally

**Assistant:**
Two clean local commits:
- `feat(phase-3): kickoff — minimal agent loop + phase plan`
- `docs: mark Phase 3 in-progress and link to phase README`

Local only (user said "commit locally"), not pushed yet.

---

**User:**
> push

**Assistant:**
Pushed both commits to origin/main. Live on the remote.

---

**User:**
> quick recap of what we did so far?

**Assistant:**
Phase 1 ✅, Phase 2 ✅, Phase 3 in progress (1 of 6).
- 17 concepts internalized
- 4 ship deliverables built
- 7 war stories survived
- 20 git commits
- ~37% through the full roadmap

---

**User:**
> A

**Assistant:**
Built `phase-3/02_agent_loop_robust.py` — same loop skeleton, production-grade instrumentation:

1. **3 tools**: calculator (sandboxed eval), get_current_time, word_count
2. **System prompt** with the agent's rules
3. **Error recovery** — exceptions round-trip as `ERROR: ...` strings
4. **Cost tracking** — per-iteration tokens + running dollar total
5. **Unknown-tool guard** — returns error if model hallucinates a tool name
6. **`--trace` mode** — dumps full messages list at end for debugging

Updated `phase-3/README.md`.

**Ran two demos:**

**Demo 1 — multi-tool parallel:** "What is 2+2*3 and word count of 'the quick brown fox jumps over the lazy dog'?"
- Iter 1: model calls calculator AND word_count in parallel → 8 and 9
- Iter 2: synthesis. "2 + 2 × 3 = 8 (order of operations), sentence has 9 words"
- Total: 2 iterations, $0.0022

**Demo 2 — error recovery:** "What is 10 divided by 0?"
- Iter 1: calculator("10/0") raised ZeroDivisionError → packaged as `ERROR: ZeroDivisionError: division by zero`
- Iter 2: model read its own previous turn, recognized the failure, pivoted to explaining why division by zero is undefined using training-data knowledge
- Total: 2 iterations, $0.0022

**The Q5 and Q6 mechanics, now felt:**
- Synthesis iteration is separate from tool-using iteration
- Errors as tool_results make agents self-recoverable
- Input tokens GROW each iteration because conversation history accumulates

---

**User:**
> commit and push

**Assistant:**
One commit:
`feat(phase-3): robust agent loop with 3 tools, error recovery, cost tracking`

Pushed to origin/main. Repo state: 22 commits total, working tree clean, in sync.

Next up: Exercise 3 — the research agent ship.

---

**User:**
> can you save this whole chat in chat.md file locally?

**Assistant:**
[This file.]

---

## Session resume — orientation and per-phase summaries

**User:**
> where are we on this

**Assistant:**
Read ROADMAP and the phase READMEs. We're mid Phase 3: exercises 01 (minimal loop) and 02 (robust loop) shipped; 03 (ReAct), 04 (self-critique), 05 (research-agent ship), and the eval still ahead. Phases 1 and 2 done. Suggested kicking off 03 next.

---

**User:**
> can you summarize each phase with a little explanation

**Assistant:**
Walked the whole arc in plain English:

- **Phase 0** — prerequisites (skipped).
- **Phase 1** — the LLM mental model. An API call is just an HTTP request you pay for per token. Ship was the structured-output quiz CLI; the hidden lesson was that forced tool use is the same machinery agents use later.
- **Phase 2** — application primitives. LLMs forget and your data isn't in their training set; RAG fixes that by retrieving chunks at query time. Ship was the RAG chatbot + LLM-as-judge eval.
- **Phase 3** — agents from scratch. An agent is a `while` loop: model → tool → result → model → done. Every framework is a wrapper over those five lines.
- **Phase 4** — frameworks, now that you can see what they hide.
- **Phase 5+** — production: MCP, observability, cost/latency budgets, safety.

The one-liner: Phase 1 teaches the API, Phase 2 teaches memory, Phase 3 teaches autonomy, Phase 4 teaches abstraction, Phase 5+ teaches operations.

---

## Phase 2 revisited — embedding vs vector, and chunking

**User:**
> what do you mean by chunking the docs and embeded them... how to clearly compare embedding with vector?

**Assistant:**
**An embedding *is* a vector** — same way a price is a number. "Vector" names the data structure (a list of floats); "embedding" names the role (that vector represents text meaning). So `embeddings.npy` at shape `(81, 384)` is 81 vectors, each a 384-dim embedding. The model is trained so similar-meaning texts get vectors pointing the same way — which is all cosine similarity measures.

**Chunking** exists because embedding a whole doc fails twice: a hard input cap (~512 tokens), and the softer, worse problem that one vector can't represent a multi-topic doc (averaging blurs every topic). So you split the doc into ~500-char passages, embed each separately, and at query time retrieve only the matching passages.

Per the project's "answer in chat, then persist for future-them" rule, added both explanations to `phase-2/README.md` (sections "Embedding vs vector — same object, two lenses" and "What chunking actually does and why we need it").

---

## Phase 3 — what's next

**User:**
> what is next in the plan?

**Assistant:**
Next is Exercise 03 (ReAct) — same loop as 02, but the model is prompted to emit Thought → Action → Observation so the reasoning is visible. Then 04 (self-critique), then 05 (the research-agent ship), then the Phase 3 eval. Recommended starting with 03 as the smallest pedagogical step.

---

## Phase 3 Exercise 3 — ReAct

**User:**
> yes

**Assistant:**
Built `phase-3/03_agent_loop_react.py` as a tight diff over Exercise 2 — same loop, same three tools. The only real changes:

1. **System prompt** now enforces the ReAct format: a one-line `Thought:` before every Action, and `Thought:` then `Answer:` before any final reply.
2. **Display** splits each text block on the model's own `Thought:`/`Answer:` markers (regex) and styles them, so we never double-label and we handle the final turn that carries both in one block.

First run revealed a cosmetic bug — `💭 Thought: Thought: ...` double-labeling — fixed by parsing the model's markers instead of blindly prefixing. Verified three scenarios: two-tool parallel, error recovery (model reads the `ERROR` observation and adapts its next Thought), and a zero-tool greeting that still emits a Thought. Updated `phase-3/README.md` with the "What Exercise 3 adds: ReAct" section, the cost tradeoff, and the source paper.

---

**User:**
> explain this run to me, how it differs from phase 2 and how it fits ReAct? where did the Thought come from?
> [pasted a run of "What is 10 divided by 0?" that answered in ONE iteration with zero tool calls]

**Assistant:**
Flagged first that this run differed from the verified one — earlier it called the calculator and saw `ERROR: ZeroDivisionError`; this time it answered directly. Both are valid; LLMs are non-deterministic (default temp ~1.0 + a genuine judgment call about whether to use the tool).

- **vs Phase 2:** Phase 2 is one LLM call where *your code* fetches context. Phase 3 is a loop where *the model* decides which tool to call and when to stop. Agency moved from your code to the model.
- **How it fits ReAct:** `Thought → Answer` is the minimal valid ReAct trace. ReAct requires reasoning before doing, not necessarily a tool call.
- **Where the "Thought:" came from:** the system prompt. There is no Thought type in the API — the model emits the literal string because we told it to. Rename it "REASONING:" and it'd emit that instead.

Recorded two gotchas in `phase-3/README.md`: "agents are non-deterministic" (why a one-off trace proves nothing and evals matter) and "where does the Thought come from" (ReAct is a prompt convention, not an architecture).

---

**User:**
> so ReAct can be changes and is just a philosophy

**Assistant:**
Yes and no. The *labels and format* are convention — rename Thought/Action/Observation freely, use XML or JSON, change the granularity. But ReAct has real teeth: forcing reasoning into the text channel measurably improves tool selection (Yao et al. benchmarked it), it makes agents debuggable, and it leverages how the model was trained (humans externalize reasoning before acting). Laid out the taxonomy — CoT, ReAct, Plan-and-Execute, ReWOO, Reflexion — and noted the modern twist: Claude's extended thinking moves the "Thought" into a real API channel. Bottom line: a pattern with measured benefits, not a religion.

---

## Phase 3 Exercise 4 — self-critique (Reflexion)

**User:**
> /model claude-opus-4-8
> continue

**Assistant:**
Built `phase-3/04_self_critique.py`. The key shift: in 01–03 the "tool" was a Python function; here the tool is *another LLM call* (the critic). Loop: GENERATE → CRITIQUE → if "revise", REGENERATE with the feedback → ... → ACCEPT or hit `--max-rounds`.

- Two roles as system prompts: a GENERATOR that writes/revises, and a deliberately ruthless CRITIC.
- The critic uses **forced tool use** to return a structured `{score, issues[], verdict}` — reliable JSON, not prose (reinforces Phase 1's lesson).
- `--critic-model` enables the asymmetric pattern: cheap generator, stronger critic. Cost tracked across both models.

Verified both exit paths. The poem run was textbook: 8/10 (3 issues) → revise → 8/10 (1 issue) → revise → 9/10 → accept. The recursion run ran the full 3 rounds without acceptance (max-rounds exit). Updated `phase-3/README.md` with the "What Exercise 4 adds: self-critique" section, including the asymmetric-critic cost pattern and when *not* to use it. Noted this is the seed of multi-agent systems — a generator and a critic passing work back and forth.

---

## Commits and push

**User:**
> commit first and wait going to 05 untill i say so

**Assistant:**
Made 4 logical commits on `main` (honoring the "attribution disabled" rule — no Co-Authored-By trailer):

1. `docs(phase-2): explain embedding vs vector and why chunking exists`
2. `feat(phase-3): ReAct agent loop (exercise 3)`
3. `feat(phase-3): self-critique loop (exercise 4)`
4. `docs(phase-3): document ReAct and self-critique exercises`

Couldn't non-interactively split the two phase-3 doc sections, so they share one README commit. Left `chat.md` untracked (stale — only covered through Ex 2) and flagged it. Held on Exercise 05 as instructed.

---

**User:**
> push as well

**Assistant:**
Pushed `7474fd9..198f7d0 main -> main`. All 4 commits live on origin/main, branch in sync.

---

**User:**
> keep updating chat.md and push it as well

**Assistant:**
Brought this transcript current through Exercise 4 and the commits/push (this section), then started tracking `chat.md` and pushing it. From here it's a maintained artifact, not an untracked scratch file.

---

## The progress rule becomes law

**User:**
> you haven't updated the readme file with the progress so far.... i want this to be rule

**Assistant:**
Checked state and found the user was right: the root README's project-structure tree still ended at phase-2 (phase-3's four files were invisible), and the status was a vague "in progress" with no count. Fixed all of it AND codified it so it can't recur:

- Added a `## Progress` table to `phase-3/README.md` (at-a-glance ✅/⏳ per deliverable).
- Root README: status → `🚧 in progress (4/6)`; structure tree extended with the phase-3 files.
- **CLAUDE.md:** added "The progress rule" — in the SAME turn progress changes, update all three of (phase `## Progress` block, root status table with the X/Y count, root structure tree). Marked non-negotiable.
- Saved a cross-session memory so the directive persists outside this repo.

Why CLAUDE.md and not a hook: a hook can't do a *semantic* README update (it can't know "we just shipped an exercise"). That needs the agent's judgment, so a rule is the right mechanism. Committed + pushed.

---

## Phase 3 Exercise 5 — the ship: a research agent

**User:**
> start exercise 05, but walk me through each step and explain while running and show and explain the output to me

**Assistant:**
Built the Phase 3 deliverable: `phase-3/05_research_agent.py`, ~200 lines, no framework. Same loop as Exercise 2; three REAL tools:

- `web_search(query)` — DuckDuckGo via `ddgs` (no API key). Flagged as a non-Anthropic dependency per the Anthropic-first rule; production swaps in Tavily/Brave/Exa via a one-function change.
- `fetch_url(url)` — httpx + BeautifulSoup, output **capped at 6,000 chars**. Bounded tool output is the #1 cost lever — every returned char becomes an input token on every later turn.
- `write_file(name, content)` — writes to `phase-3/reports/`, `basename()`-sanitized so the model can't escape the directory.

Walked through it in steps: added deps (`ddgs`, `beautifulsoup4`) and probed each tool's real API in isolation BEFORE wiring the loop — which caught the ddgs result shape (`{title, href, body}`) and showed a raw page going 181k → 13k chars after cleaning (still ~3.5k tokens — hence the cap).

Ran it on "What is the ReAct prompting pattern and who introduced it?": 4 iterations, 6 tool calls (2 search, 3 fetch, 1 write), **$0.0184**, producing an accurate cited report. The key observation: input tokens climbed 1106 → 7384 across turns because the conversation only accumulates — the fetched pages are what spike it. Committed as two commits (feat + docs) and pushed.

---

## Track the reports, don't ignore them

**User:**
> don't ignore the reports, push them also

**Assistant:**
Reversed the earlier decision to gitignore `phase-3/reports/`. Dropped the ignore rule, checked in the sample report, and updated both READMEs from "gitignored" to "checked in as sample output". Committed + pushed. Heads-up given: every future run now writes a `.md` there that shows in `git status`.

---

## Phase 3 Exercise 6 — evaluating the agent (phase finale)

**User:**
> yes and explain and show me the what, why and how of evals clearly

**Assistant:**
Taught evals first: an eval is a repeatable, scored test suite for non-deterministic output. The Phase 3 twist vs Phase 1/2 — an agent is judged on its **trajectory** (the tool-call sequence), not just its final output, because that's where agent-specific failures hide (hallucinated citations, wrong tool order, runaway loops, silent non-completion). And since agents are non-deterministic, one good run proves nothing — you measure across a set.

Built `phase-3/evals/eval_research.py` scoring five dimensions, cheap-deterministic first, LLM-judge last:
1. completed · 2. trajectory_ok (search→fetch→write, under budget) · 3. citations_grounded (every cited URL was actually fetched — the hallucination catch) · 4. contains_expected (known fact present) · 5. answers_question (Sonnet 1-5).

This required a small but important refactor: `run_agent` now RETURNS its trajectory dict (tools_called, fetched_urls, report_content, cost) and takes a `quiet` flag — "an agent you can't inspect, you can't test." The grounded check is only possible because of it.

Ran it: Haiku agent, Sonnet judge, 3 questions → **3/3 passed, avg answers 4.7/5, $0.0545**. Noted the honest caveat: a clean pass is not a victory — a load-bearing eval should occasionally bite, so the next step is adversarial cases. Updated all the progress markers (Phase 3 → ✅ 6/6 complete, Phase 4 → next).

---

## Where we stand

```
phase-1/   ✅ done    — LLM mental model (4 scripts + structural eval)
phase-2/   ✅ done    — RAG primitives (5 scripts + LLM-as-judge eval)
phase-3/   ✅ done    — agents from scratch (6 of 6 deliverables shipped)
phase-4/   🔜 next   — frameworks and patterns
phase-5/   ⏳ later  — production-grade
phase-6/   ⏳ later  — frontiers
```

**Concepts internalized:** 24 (8 Phase 1 + 8 Phase 2 + 8 Phase 3 — the agent loop through ReAct, self-critique, real tools, and agent evaluation)

**Ship deliverables built:** 5
- Phase 1: structured-output quiz CLI
- Phase 2: vector-search RAG chatbot
- Phase 2: cached-context RAG chatbot
- Phase 3: research agent (web_search + fetch_url + write_file → cited report)
- Phase 3: agent eval (5-dimension trajectory + output scoring)

**Phase 3 exercises shipped:** 6 of 6 ✅
1. `01_agent_loop_minimal.py` — the bare loop
2. `02_agent_loop_robust.py` — 3 tools, error recovery, cost tracking, `--trace`
3. `03_agent_loop_react.py` — ReAct (Thought → Action → Observation)
4. `04_self_critique.py` — generate → critique → revise (Reflexion)
5. `05_research_agent.py` — the ship: real tools → cited markdown report
6. `evals/eval_research.py` — eval on trajectory + grounded citations + judge

**War stories survived:** 8
1. Max plan ≠ API credits
2. `max_tokens=1500` truncated hard-topic JSON silently
3. Eval scoreboard inflated 20/20 = 100% via 0/0 accounting
4. PyTorch dropped Intel Mac wheels
5. ONNX runtime also dropped Intel Mac wheels (pinned <1.20)
6. `load_dotenv()` doesn't override empty shell env vars
7. Synthesis needs its own iteration (the Q5 lesson)
8. Agents are non-deterministic — same query gave a 1-iteration and a 2-iteration trace on different runs (why a one-off trace proves nothing)

**Repo:** https://github.com/imranbhat/agentic-ai (private). ~30 commits on main, in sync with remote.

---

## Notes on what made this work pedagogically

A few patterns from this conversation that mattered:

1. **Build → break → fix → learn.** Every gotcha was hit in real code, not described abstractly. The `max_tokens` truncation, the dotenv override, the eval scoreboard lie — they all happened to us.

2. **Inspectable artifacts.** `chunks.jsonl` being human-readable let me make a mistake (wrong chunk IDs) that the data could correct. A binary vector store would have hidden it.

3. **Forced precision via quizzing.** The 6-question agent-loop quiz surfaced exactly which mechanics were solid vs fuzzy. The wrong answer on Q5 (synthesis iteration) led directly to a demo that drove the lesson home.

4. **One README per phase + a project-wide CLAUDE.md.** Kept the docs in sync with reality without ever having to do a "documentation update" pass at the end.

5. **Per-file pedagogical responsibility.** `00_count_tokens.py` taught tokenization. `01_stream_hello.py` taught the bare API. Each file had one concept it owned.

6. **Cost visibility from day one.** Every cost line printed during a run made the economics tactile. $0.0022 per agent run is invisible until you see it.

7. **Anthropic-first, drift labeled.** When we used fastembed instead of Voyage (Anthropic's recommended), we said so explicitly. No quiet drift.

8. **Diff-based exercises.** Exercises 03 (ReAct) and 04 (self-critique) were each built as a *tight diff* over the previous file — same loop, minimal change — so the new lesson is isolated and visible. The takeaway lands harder when you can see exactly what moved: ReAct is "only the system prompt + display changed," and self-critique is "only the tool changed, from a Python function to another LLM call." The loop skeleton never moves.

9. **Make the system return data, not just print.** The Phase 3 eval was only possible because `run_agent` was refactored to *return its trajectory* (tools called, URLs fetched, the report) instead of only printing to the console. "An agent you can't inspect, you can't test" — testability is a design property you build in, and the grounded-citations check (real vs hallucinated sources) is invisible without it.

10. **Eval the process, not just the output.** Phase 1/2 evals scored a single artifact. An agent eval scores the *trajectory* — did it use tools in a sane order, stay in budget, cite only what it fetched. The most valuable check (grounded citations) is one you can't get by reading the final report; you need the sequence of actions.

That's the project so far.

---

# Phase 4 — Frameworks and patterns (in progress)

**Goal:** know which framework to reach for and why — and *feel* what a framework adds and hides versus the loop we hand-wrote in Phase 3.

**Confirmed 9-exercise plan:**
1. `01_sdk_hello.py` — Claude Agent SDK hello-world ✅
2. `02_research_agent_sdk.py` — port the Phase 3 research agent to the SDK (the ship)
3. `03_sdk_vs_scratch.md` — the comparison: LOC, robustness, behavior
4–8. The five *Building Effective Agents* patterns (prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer) — built in **plain Anthropic API** on purpose, because they're workflows and a framework would hide the orchestration they teach.
9. `09_langgraph_research_agent.py` — the same agent a third way, on LangGraph, for a true 3-way comparison.

Two decisions confirmed up front: patterns in raw API (not the SDK), and LangGraph included in Phase 4 (not deferred).

## Exercise 01 — the SDK hello-world

The whole file is one `query()` call with **no `while` loop** — that absence is the lesson. What changed from Phases 1–3:

- **Async-first.** `async for message in query(...)` + `asyncio.run`, not the synchronous `response = client.messages.create(...)`.
- **Typed messages.** You consume `AssistantMessage` (with `TextBlock`s) then a `ResultMessage`, not raw `response.content`.
- **Cost computed for you.** `ResultMessage.total_cost_usd` / `usage` / `num_turns` arrive filled in — no hand-rolled `PRICES` table.

**The turn-one surprise:** asked to "say hello," the agent replied *"Ready to continue your learn-ai project…"* — even though the system prompt only said "concise teaching assistant." The Agent SDK is **project-aware by default** (it's Claude Code under the hood, so it loads the cwd and `CLAUDE.md`). The raw API sees only your `messages`; the SDK quietly sees the whole repo. That convenience is also a cost: the Haiku hello-world ran **$0.003–0.013** (variable, cache read vs. write) vs. a fraction of a cent in Phase 1.

**War stories (new):**
9. The SDK is a heavy install — one `uv add` pulled **17 packages (~66 MiB)** because it bundles a Node-based Claude Code CLI. (Phase 3's agent was ~200 lines on `anthropic` + `httpx`.)
10. A throwaway probe that iterated `query()` but only inspected the `ResultMessage` intermittently raised `Claude Code returned an error result: success` and reported $0 cost. Consuming the *full* message stream (as the shipped script does) is stable. Lesson: don't drain only the final frame.

## Exercise 02 — the ship: port the research agent to the SDK

A *faithful port* of `phase-3/05_research_agent.py`: same three tools (web_search via ddgs, fetch_url with the 6,000-char cap, write_file), same system prompt, same cited-markdown output. The only thing deleted is the hand-written `while` loop — the SDK runs it.

The tools are now registered as one in-process MCP server (`@tool` + `create_sdk_mcp_server`), addressed as `mcp__research__<tool>`. Faithful-port options, each a deliberate choice:
- `tools=[]` — no built-in Bash/Read/Edit; only our three exist, like Phase 3.
- `setting_sources=[]` — isolation; do NOT load `CLAUDE.md`. The deliberate opposite of Ex 01's project-awareness — here we want a clean agent that sees only the question.
- `system_prompt=<string>` — replaces the Claude Code preset with our research prompt.
- `max_turns=15` — the SDK's built-in version of Phase 3's hand-written loop guard.
- `permission_mode="bypassPermissions"` — non-interactive (write_file touches disk).

**Same behavior, measured.** On the exact Phase 3 question ("What is the ReAct prompting pattern and who introduced it?"):
```
search → fetch ×3 (in parallel) → write_file → 2-sentence summary
6 turns • ~21 s • $0.0194        (Phase 3 hand-rolled: 4 iters / 6 tool calls / $0.0184)
```
Near-identical cost and the same trajectory. The framework didn't make the agent cheaper or smarter — it made *us* write less code. The report (`phase-4/reports/react_prompting_pattern.md`) is correctly cited: Yao et al. 2022, Google Brain, right paper and authors.

**The keeper lesson:** what a framework can't do for you is the tools. Tool *design* — bounded output, sanitized paths, useful return strings — is yours in every framework. The loop was the disposable part; tool design is the durable Phase 3 skill.

**War stories (new):**
11. Blocking `ddgs`/`httpx` inside an `async def` tool blocks the event loop. Fine for a single-user script; a production port would use `httpx.AsyncClient` + a thread for ddgs. Surfaced the shortcut in a comment, didn't hide it.
12. `python3` is the system interpreter and can't see the uv venv (`ModuleNotFoundError: claude_agent_sdk`) — inspect SDK objects with `uv run python -c ...`.

## Exercise 03 — the comparison (hand-rolled vs SDK)

No new code — the roadmap's actual ask, written up in `phase-4/03_sdk_vs_scratch.md`: the two research agents weighed on **lines of code, robustness, and behavior**, with measured numbers.

**Lines of code** (AST line classifier): Phase 3 hand-rolled = 384 total / ~250 code; SDK port = 241 total / ~133 code. ~47% fewer code lines — but the honest framing is sharper: the ~150 lines of *loop plumbing* (the for loop, tool dispatch, tool_result assembly, PRICES table + token math, trace/summary helpers) collapsed to ~40, while the three tools — the part a framework *can't* write for you — stayed the same size in both.

**Dependencies:** Phase 3 = `anthropic` + `httpx` + `bs4` + `ddgs`. Phase 4 = all that + `claude-agent-sdk` (17 packages, ~66 MiB, plus a Node runtime) to run three Python functions in a loop.

**Behavior** (same ReAct question): same trajectory (search → fetch ×3 → write → summary), $0.0184 vs $0.0194. The framework changed the *developer's* experience, not the *agent's*.

**The verdict:** the framework saved code, not cost or quality. Hand-roll while the loop is the thing you're learning or must tightly control; reach for the SDK once the loop is settled and you'd rather not maintain retries/budgets/permissions/MCP yourself. You can only judge that trade *because* you wrote the loop by hand first — which is why Phase 3 came before Phase 4. Block A (Claude Agent SDK) complete; next is Block B, the five Building Effective Agents patterns in plain Anthropic API.
