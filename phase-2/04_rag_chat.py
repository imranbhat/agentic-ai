"""
Phase 2, SHIP DELIVERABLE — RAG chatbot over your own markdown.

Combines everything from Phase 1 and Phase 2 so far:

    question → embed (Phase 2)
            → top-K chunks (Phase 2)
            → stuff into a prompt (Phase 1 prompt engineering)
            → stream from Claude (Phase 1 streaming)
            → cited, grounded answer

New ideas in this file (everything else is recombination):

1. CONTEXT FORMATTING. Anthropic recommends XML tags for delimiting
   passages — clearer than free text concatenation, harder for the model
   to confuse with the question. We wrap each chunk in <passage id="N">.

2. SYSTEM PROMPT AS RAG GUARDRAIL. The system prompt is where you tell
   the model: answer from the passages only, cite [1]/[2] for every
   claim, say "not in the context" rather than guessing. This is the
   single biggest knob for hallucination prevention in RAG.

3. SHOW-YOUR-WORK UI. Before generating, we print which chunks were
   retrieved. The user can verify that the right passages are being
   used. This is what makes RAG debuggable.

Run:
    uv run phase-2/04_rag_chat.py "what is forced tool use?"
    uv run phase-2/04_rag_chat.py "how does our chunker fail?" --k 5
    uv run phase-2/04_rag_chat.py            # interactive REPL mode
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from anthropic import Anthropic
from dotenv import load_dotenv
from fastembed import TextEmbedding
from rich.console import Console

load_dotenv(override=True)  # Why: shell may have ANTHROPIC_API_KEY="" set; .env wins.
console = Console()

INDEX_DIR = Path(__file__).parent / "index"
EMBEDDINGS_FILE = INDEX_DIR / "embeddings.npy"
CHUNKS_FILE = INDEX_DIR / "chunks.jsonl"
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# Per-1M-token prices for cost estimation. Update from console.anthropic.com.
PRICES = {
    "claude-haiku-4-5":  (0.80,  4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7":   (15.00, 75.00),
}

# The single most important prompt in this file. Read it carefully.
SYSTEM_PROMPT = """You are a precise assistant that answers questions using ONLY the passages provided inside <context>.

Rules:
- Cite the passage number(s) in brackets like [1] or [2,3] for every factual claim.
- If the passages do not contain the answer, say "The context doesn't cover this" — do NOT guess from general knowledge.
- Synthesize across passages in your own words; quote sparingly.
- Match the user's level of detail. Be concise unless they ask for depth.
- If the passages contradict each other, surface the disagreement instead of picking one silently."""


# ---------------------------------------------------------------------------
# Index loading + retrieval (lifted from Exercise 3)
# ---------------------------------------------------------------------------
def load_index() -> tuple[np.ndarray, list[dict]]:
    if not EMBEDDINGS_FILE.exists():
        console.print(
            "[red]Index not found.[/]  Run "
            "[bold]uv run phase-2/02_build_index.py[/] first."
        )
        sys.exit(1)
    embeddings = np.load(EMBEDDINGS_FILE)
    chunks = [
        json.loads(line)
        for line in CHUNKS_FILE.read_text().splitlines()
        if line.strip()
    ]
    return embeddings, chunks


def retrieve(query: str, k: int, embeddings: np.ndarray,
             chunks: list[dict], embed_model: TextEmbedding) -> list[tuple[dict, float]]:
    """Return the top-K (chunk, score) pairs for `query`."""
    q_vec = np.array(list(embed_model.embed([query])))[0]
    q_vec = q_vec / max(np.linalg.norm(q_vec), 1e-12)
    scores = embeddings @ q_vec
    top_idx = np.argsort(scores)[::-1][:k]
    return [(chunks[i], float(scores[i])) for i in top_idx]


# ---------------------------------------------------------------------------
# Prompt construction — XML-tagged passages for clarity
# ---------------------------------------------------------------------------
def build_user_message(query: str, retrieved: list[tuple[dict, float]]) -> str:
    """Stitch retrieved chunks into a <context> block + the question."""
    passages = []
    for i, (chunk, _score) in enumerate(retrieved, 1):
        passages.append(
            f'<passage id="{i}" source="{chunk["file"]}">\n'
            f'{chunk["text"]}\n'
            f'</passage>'
        )
    context = "\n\n".join(passages)
    return f"<context>\n{context}\n</context>\n\nQuestion: {query}"


# ---------------------------------------------------------------------------
# Pretty-print the retrieved chunks (the "show your work" UI)
# ---------------------------------------------------------------------------
def print_retrieved(retrieved: list[tuple[dict, float]]) -> None:
    console.rule(f"[dim]retrieved {len(retrieved)} passages[/]")
    for i, (chunk, score) in enumerate(retrieved, 1):
        color = "green" if score > 0.5 else "yellow" if score > 0.35 else "red"
        preview = chunk["text"][:110].replace("\n", " ")
        console.print(
            f"  [bold]\\[{i}][/]  [{color}]{score:.3f}[/]  "
            f"[dim]{chunk['file']} chunk_{chunk['chunk_index']}:[/] {preview}…"
        )


# ---------------------------------------------------------------------------
# Single query → answer
# ---------------------------------------------------------------------------
def answer_one(query: str, args, embeddings, chunks, embed_model, client):
    retrieved = retrieve(query, args.k, embeddings, chunks, embed_model)
    print_retrieved(retrieved)

    if args.show_context:
        console.rule("[dim]full user message sent to Claude[/]")
        console.print(build_user_message(query, retrieved))

    console.rule("[bold cyan]Answer[/]")
    with client.messages.stream(
        model=args.model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message(query, retrieved)}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
        final = stream.get_final_message()

    print()
    # Cost line — useful to internalize how cheap RAG is at Haiku prices
    in_price, out_price = PRICES.get(args.model, (0.0, 0.0))
    cost = (final.usage.input_tokens * in_price
            + final.usage.output_tokens * out_price) / 1_000_000
    console.print(
        f"\n[dim]model={args.model}  "
        f"in={final.usage.input_tokens}  "
        f"out={final.usage.output_tokens}  "
        f"stop={final.stop_reason}  "
        f"cost≈${cost:.4f}[/]"
    )


# ---------------------------------------------------------------------------
# Interactive REPL — load model once, query forever
# ---------------------------------------------------------------------------
def interactive(args, embeddings, chunks, embed_model, client):
    console.print(
        "[bold cyan]RAG chat[/] — ask a question about your markdown notes.\n"
        "[dim]Ctrl+D or 'quit' to exit. Empty input to skip.[/]\n"
    )
    while True:
        try:
            query = input("[?] ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if query.lower() in {"quit", "exit"}:
            return
        if not query:
            continue
        answer_one(query, args, embeddings, chunks, embed_model, client)
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="RAG chatbot over your markdown index.")
    parser.add_argument("question", nargs="*",
                        help="A one-shot question. Omit for interactive REPL.")
    parser.add_argument("--k", type=int, default=4,
                        help="Number of chunks to retrieve (default 4)")
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"),
                        help="Claude model to use")
    parser.add_argument("--show-context", action="store_true",
                        help="Print the full user message sent to Claude")
    args = parser.parse_args()

    # Load everything ONCE — costly resources reused across queries
    embeddings, chunks = load_index()
    embed_model = TextEmbedding(model_name=EMBED_MODEL_NAME)
    client = Anthropic()

    if args.question:
        answer_one(" ".join(args.question), args, embeddings, chunks, embed_model, client)
    else:
        interactive(args, embeddings, chunks, embed_model, client)


if __name__ == "__main__":
    main()
