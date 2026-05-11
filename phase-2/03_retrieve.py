"""
Phase 2, Exercise 3 — Top-K retrieval over your index.

Loads the index built by 02_build_index.py, embeds your query, and returns
the K chunks most similar to it by cosine similarity.

Three new ideas (everything else is from Exercises 1 and 2):

1. PERSISTENCE PAYOFF. We embedded all 81 chunks once. Every query reuses
   them — the per-query cost is one small embed call plus a dot product
   over a (81, 384) matrix. This is why RAG scales: indexing is one-time
   and slow; querying is forever and instant.

2. RANKING. `embeddings @ query_vec` gives all 81 similarities at once
   in a single numpy op. argsort returns the rank order; [::-1] reverses
   to descending; [:k] takes the top K. Three operations, one line.

3. INTERPRETING SCORES. Cosine similarity > 0.5 is usually relevant,
   > 0.7 is a strong match, > 0.85 means near-duplicate (the chunk almost
   restates the query). These thresholds are corpus-dependent — calibrate
   against your own data and own eval set.

Run:
    uv run phase-2/03_retrieve.py "what is tool_choice?"
    uv run phase-2/03_retrieve.py "how do embeddings work?" --k 3
    uv run phase-2/03_retrieve.py "RAG" --full --show-bottom
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from rich.console import Console
from rich.panel import Panel

console = Console()

INDEX_DIR = Path(__file__).parent / "index"
EMBEDDINGS_FILE = INDEX_DIR / "embeddings.npy"
CHUNKS_FILE = INDEX_DIR / "chunks.jsonl"
MODEL_NAME = "BAAI/bge-small-en-v1.5"


def load_index() -> tuple[np.ndarray, list[dict]]:
    """Load embeddings + parallel chunk metadata from disk."""
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
    assert len(embeddings) == len(chunks), \
        f"index corrupt: {len(embeddings)} vectors but {len(chunks)} chunks"
    return embeddings, chunks


def embed_query(query: str, model: TextEmbedding) -> np.ndarray:
    """Embed a single query and unit-normalize. Returns a 1-D array of dim 384."""
    vec = np.array(list(model.embed([query])))[0]
    return vec / max(np.linalg.norm(vec), 1e-12)


def main():
    parser = argparse.ArgumentParser(
        description="Top-K retrieval over the markdown index."
    )
    parser.add_argument("query", nargs="+", help="The search query")
    parser.add_argument("--k", type=int, default=5, help="Top-K (default 5)")
    parser.add_argument("--full", action="store_true",
                        help="Show full chunk text instead of a preview")
    parser.add_argument("--show-bottom", action="store_true",
                        help="Also show the bottom 3 — chunks the retriever rejected")
    args = parser.parse_args()

    query = " ".join(args.query)

    # 1. Load the pre-built index (one-time cost — could even be cached).
    embeddings, chunks = load_index()

    # 2. Embed the query (one tiny model call).
    model = TextEmbedding(model_name=MODEL_NAME)
    q_vec = embed_query(query, model)

    # 3. Score every chunk against the query in one matrix op.
    # Because both `embeddings` and q_vec are unit-normalized, dot product
    # IS cosine similarity. No special function needed.
    scores = embeddings @ q_vec                # shape (N,) — one score per chunk

    # 4. Rank and take top K. argsort returns indices ascending; reverse for descending.
    top_indices = np.argsort(scores)[::-1][:args.k]

    # ---- Render results --------------------------------------------------
    console.rule(f"[bold cyan]Top {args.k} for:[/] [bold]{query!r}[/]")
    for rank, idx in enumerate(top_indices, 1):
        chunk = chunks[idx]
        score = float(scores[idx])
        color = "green" if score > 0.5 else "yellow" if score > 0.35 else "red"
        if args.full:
            text = chunk["text"]
        else:
            text = chunk["text"][:280].replace("\n", " ")
            if len(chunk["text"]) > 280:
                text += "…"
        console.print(Panel.fit(
            f"[bold]#{rank}[/]  [{color}]score={score:.3f}[/]  "
            f"[dim]{chunk['file']} chunk_{chunk['chunk_index']} "
            f"(id={chunk['id']}, {chunk['n_chars']} chars)[/]\n\n"
            f"{text}",
            border_style=color,
        ))

    # ---- Optional: show what was REJECTED for contrast -------------------
    if args.show_bottom:
        console.rule("[dim]Bottom 3 — what the retriever rejected[/]")
        bottom = np.argsort(scores)[:3]
        for rank, idx in enumerate(bottom, 1):
            chunk = chunks[idx]
            preview = chunk["text"][:80].replace("\n", " ")
            console.print(
                f"  [dim]#{rank}  score={float(scores[idx]):.3f}  "
                f"{chunk['file']} chunk_{chunk['chunk_index']}: {preview}…[/]"
            )

    # ---- Score interpretation cheat-sheet --------------------------------
    console.rule("[dim]score interpretation[/]")
    console.print(
        "[dim]> 0.5   usually relevant       > 0.7   strong match\n"
        "> 0.85  near-duplicate of query  < 0.3   probably irrelevant\n"
        "These thresholds are corpus-dependent — calibrate on your own data.[/]"
    )


if __name__ == "__main__":
    main()
