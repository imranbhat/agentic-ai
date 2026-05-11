"""
Phase 2, Exercise 5 — Prompt caching: ~90% cheaper on repeat queries.

A DIFFERENT take on RAG. Our corpus is small (81 chunks ≈ 9k tokens). It
fits in Claude's 200k context with room to spare. So instead of running
vector search every query, we can do something stranger and arguably
better for tiny corpora:

   STUFF THE ENTIRE CORPUS INTO THE PROMPT, mark it as cacheable, and
   let the model do the "retrieval" itself by reading.

That's the whole pattern. No embeddings at query time, no top-K — just
the corpus + your question.

Why this works at small scale:

    system + entire corpus  ─ CACHED ─→  paid 1.25× ONCE, then 0.1× per hit
    question (varies)       ─────────→  paid normally

Cache lifetime: 5 minutes (ephemeral). Cache write is slightly more
expensive than a normal call (1.25× input cost). Cache read is dirt cheap
(0.1× input cost). After two queries against the same cached prefix,
you're already net cheaper than no caching at all.

When to use which pattern:

    Corpus ≤ ~50k tokens   → THIS file: stuff it all + cache
    Corpus > ~50k tokens   → 04_rag_chat.py: vector search first

For 90% of internal-docs-style RAG, the cached-context pattern is plenty.

Run:
    uv run phase-2/05_with_caching.py "what is forced tool use?"
    uv run phase-2/05_with_caching.py     # interactive — feel cache hits
"""
import argparse
import json
import os
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(override=True)
console = Console()

INDEX_DIR = Path(__file__).parent / "index"
CHUNKS_FILE = INDEX_DIR / "chunks.jsonl"

# Per-million-token base prices. Cache write is 1.25×, cache read is 0.1×.
PRICES = {
    "claude-haiku-4-5":  (0.80, 4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7":   (15.00, 75.00),
}
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER  = 0.10

SYSTEM_PROMPT = """You answer questions using ONLY the passages provided in <corpus>.

Rules:
- Cite the passage id (e.g., [id=42]) for every factual claim.
- If the corpus doesn't contain the answer, say "The corpus doesn't cover this".
- Be concise. Synthesize across passages — don't quote heavily."""


# ---------------------------------------------------------------------------
# Corpus formatting — the entire indexed corpus as a single text blob
# ---------------------------------------------------------------------------
def load_corpus_as_text() -> str:
    """Format all chunks as one big text blob with passage ids."""
    if not CHUNKS_FILE.exists():
        console.print(
            "[red]chunks.jsonl not found.[/]  Run "
            "[bold]uv run phase-2/02_build_index.py[/] first."
        )
        raise SystemExit(1)
    chunks = [
        json.loads(line)
        for line in CHUNKS_FILE.read_text().splitlines()
        if line.strip()
    ]
    passages = [
        f'<passage id="{c["id"]}" source="{c["file"]}">\n{c["text"]}\n</passage>'
        for c in chunks
    ]
    return "<corpus>\n" + "\n\n".join(passages) + "\n</corpus>"


# ---------------------------------------------------------------------------
# Cost reporter — the actual reason this file exists
# ---------------------------------------------------------------------------
def print_cost(usage, model: str, idx: int) -> None:
    """Break down regular / cache-write / cache-read tokens and show savings."""
    base_in, base_out = PRICES.get(model, (0.0, 0.0))

    regular_in  = usage.input_tokens
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read  = getattr(usage, "cache_read_input_tokens", 0) or 0
    out_tokens  = usage.output_tokens

    actual = (
        regular_in  * base_in / 1_000_000
        + cache_write * base_in * CACHE_WRITE_MULTIPLIER / 1_000_000
        + cache_read  * base_in * CACHE_READ_MULTIPLIER  / 1_000_000
        + out_tokens * base_out / 1_000_000
    )
    # What it WOULD have cost without caching at all
    uncached = (
        (regular_in + cache_write + cache_read) * base_in / 1_000_000
        + out_tokens * base_out / 1_000_000
    )
    saved_pct = (1 - actual / uncached) * 100 if uncached > 0 else 0
    hit = "HIT" if cache_read > 0 else "MISS"
    color = "green" if cache_read > 0 else "yellow"

    console.print(
        f"[dim]query #{idx}  cache: [{color}]{hit}[/]  "
        f"in_regular={regular_in}  cache_write={cache_write}  "
        f"cache_read={cache_read}  out={out_tokens}[/]"
    )
    console.print(
        f"[bold]cost: ${actual:.4f}[/]   "
        f"[dim](uncached would be ${uncached:.4f}, "
        f"saved [green]{saved_pct:.0f}%[/dim])"
    )


# ---------------------------------------------------------------------------
# One query against the cached corpus
# ---------------------------------------------------------------------------
def ask(client: Anthropic, corpus_blob: str, question: str, model: str):
    """Send a query with the corpus marked cacheable.

    The `cache_control` marker on the corpus block tells Anthropic to cache
    everything up to and including that block. Subsequent calls with the SAME
    prefix get a cache hit — billed at 1/10th the normal input rate.
    """
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=[
            {"type": "text", "text": SYSTEM_PROMPT},
            {
                "type": "text",
                "text": corpus_blob,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[{"role": "user", "content": question}],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    return text, response.usage


# ---------------------------------------------------------------------------
# Interactive REPL — caching only earns its keep across multiple queries
# ---------------------------------------------------------------------------
def interactive(client, corpus_blob, model):
    console.print(
        f"[bold cyan]cached-context chat[/]  model={model}\n"
        "[dim]First query writes the cache. Subsequent queries hit it (5-min TTL).\n"
        "Ctrl+D or 'quit' to exit.[/]\n"
    )
    idx = 0
    while True:
        try:
            q = input("[?] ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if q.lower() in {"quit", "exit"}:
            return
        if not q:
            continue
        idx += 1
        console.rule(f"[bold cyan]Q{idx}: {q}[/]")
        answer, usage = ask(client, corpus_blob, q, model)
        print(answer)
        print()
        print_cost(usage, model, idx)
        print()


def main():
    parser = argparse.ArgumentParser(description="RAG via cached full-corpus context.")
    parser.add_argument("question", nargs="*",
                        help="One-shot question. Omit for interactive mode.")
    parser.add_argument("--model",
                        default=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"))
    args = parser.parse_args()

    corpus_blob = load_corpus_as_text()
    approx_tokens = len(corpus_blob) // 4
    console.print(f"[dim]Corpus prepared: ~{approx_tokens:,} tokens to cache.[/]\n")

    client = Anthropic()

    if args.question:
        question = " ".join(args.question)
        console.rule(f"[bold cyan]Q1: {question}[/]")
        answer, usage = ask(client, corpus_blob, question, args.model)
        print(answer)
        print()
        print_cost(usage, args.model, 1)
        if (getattr(usage, "cache_read_input_tokens", 0) or 0) == 0:
            console.print(
                "\n[dim]Tip: this was the FIRST query, so it wrote the cache "
                "(slightly more expensive). Re-run within 5 minutes to see "
                "a cache HIT and the cost drop ~90%.[/]"
            )
    else:
        interactive(client, corpus_blob, args.model)


if __name__ == "__main__":
    main()
