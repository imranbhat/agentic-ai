"""
Phase 2, Exercise 2 — Build a vector index over your own markdown files.

Three big ideas in this file:

1. CHUNKING. You can't embed an entire 10,000-word document — long passages
   blur into mush in vector space. You split it into smaller pieces (chunks).
   Chunking strategy is one of the biggest levers in RAG quality.

2. METADATA. A vector alone is useless. You also need to know which file
   it came from, where in the file, and the original text. The index is
   really TWO things: an array of vectors AND a parallel list of metadata.

3. ON-DISK FORMAT. We use numpy for the vectors (fast load, compact) and
   JSONL for metadata (one chunk per line, human-inspectable with `head`,
   `jq`, etc.). Real systems graduate to a vector DB (Chroma, pgvector,
   Pinecone) but starting with raw files makes the mechanics visible.

Run:
    uv run phase-2/02_build_index.py             # build (no-op if exists)
    uv run phase-2/02_build_index.py --rebuild   # force rebuild
"""
import argparse
import json
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from rich.console import Console
from rich.table import Table

console = Console()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = Path(__file__).parent / "index"
EMBEDDINGS_FILE = INDEX_DIR / "embeddings.npy"
CHUNKS_FILE = INDEX_DIR / "chunks.jsonl"

MODEL_NAME = "BAAI/bge-small-en-v1.5"

# Why these sizes?
#   target ~500 chars  ≈ ~125 tokens — small enough to be precise,
#                                      large enough to carry a real idea.
#   max ~1500 chars    — catches long paragraphs without splitting mid-sentence.
# Production RAG often uses 200–800 tokens per chunk. Worth experimenting.
TARGET_CHUNK_SIZE = 500
MAX_CHUNK_SIZE = 1500


# ---------------------------------------------------------------------------
# 1. Discover .md files
# ---------------------------------------------------------------------------
def find_markdown_files(root: Path) -> list[Path]:
    """Find all .md files under `root`, skipping ignored directories."""
    skip = {".git", ".venv", "node_modules", "__pycache__", ".uv", "index"}
    files = []
    for path in root.rglob("*.md"):
        if any(part in skip for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


# ---------------------------------------------------------------------------
# 2. Chunk markdown
# ---------------------------------------------------------------------------
def chunk_markdown(text: str, target: int = TARGET_CHUNK_SIZE) -> list[str]:
    """Split markdown into chunks at paragraph boundaries.

    Strategy: greedy pack paragraphs until adding the next one would exceed
    `target`, then start a new chunk. Single oversized paragraphs stay whole
    (we don't split mid-sentence in this iteration — would need a sentence
    splitter for that).

    This is the simplest chunker that works. Smarter alternatives:
      - Markdown-structure-aware (split at # headings, keep code blocks whole)
      - Semantic chunking (embed sentences, split where similarity drops)
      - Recursive character splitting (LangChain's default)
    Save those for later experimentation.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for p in paragraphs:
        # Start a new chunk if adding this paragraph would push us past target
        # (but never produce an empty chunk — always carry at least one paragraph).
        if current and current_len + len(p) > target:
            chunks.append("\n\n".join(current))
            current = [p]
            current_len = len(p)
        else:
            current.append(p)
            current_len += len(p) + 2  # +2 accounts for the "\n\n" separator
    if current:
        chunks.append("\n\n".join(current))
    return chunks


# ---------------------------------------------------------------------------
# 3. Embed
# ---------------------------------------------------------------------------
def embed(texts: list[str], model: TextEmbedding) -> np.ndarray:
    """Embed a list of texts; return a unit-normalized (N, dim) array.

    Unit-normalization means dot product = cosine similarity later — a small
    optimization that matters at scale.
    """
    vecs = np.array(list(model.embed(texts)))
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / np.clip(norms, 1e-12, None)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Chunk + embed all .md files in the project, save the index to disk."
    )
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT,
                        help="Project root to scan (default: project root)")
    parser.add_argument("--rebuild", action="store_true",
                        help="Force rebuild even if the index exists")
    args = parser.parse_args()

    # Skip if already built — chunking + embedding takes ~30s for our corpus.
    if EMBEDDINGS_FILE.exists() and not args.rebuild:
        emb = np.load(EMBEDDINGS_FILE)
        with open(CHUNKS_FILE) as f:
            n_chunks = sum(1 for _ in f)
        console.print(
            f"[yellow]Index already exists at {INDEX_DIR.relative_to(PROJECT_ROOT)}/[/]\n"
            f"  {n_chunks} chunks, embeddings shape: {emb.shape}\n"
            f"  Use --rebuild to recreate."
        )
        return

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    # ---- 1. Discover ------------------------------------------------------
    console.rule("[bold cyan]1. Discover[/]")
    files = find_markdown_files(args.root)
    if not files:
        console.print("[red]No .md files found. Nothing to index.[/]")
        return
    console.print(f"Found [bold]{len(files)}[/] markdown files:")
    for f in files:
        size_kb = f.stat().st_size / 1024
        rel = str(f.relative_to(args.root))
        console.print(f"  [dim]{rel:<40}[/] {size_kb:>5.1f} KB")

    # ---- 2. Chunk ---------------------------------------------------------
    console.rule("[bold cyan]2. Chunk[/]")
    chunks: list[dict] = []
    for f in files:
        text = f.read_text()
        for i, chunk_text in enumerate(chunk_markdown(text)):
            chunks.append({
                "id": len(chunks),
                "file": str(f.relative_to(args.root)),
                "chunk_index": i,
                "n_chars": len(chunk_text),
                "text": chunk_text,
            })

    sizes = np.array([c["n_chars"] for c in chunks])
    console.print(
        f"Produced [bold]{len(chunks)}[/] chunks across {len(files)} files.\n"
        f"  size (chars): min={sizes.min()}  median={int(np.median(sizes))}  max={sizes.max()}\n"
        f"  size (~tokens): min={sizes.min() // 4}  median={int(np.median(sizes)) // 4}  "
        f"max={sizes.max() // 4}"
    )

    # ---- 3. Embed ---------------------------------------------------------
    console.rule("[bold cyan]3. Embed[/]")
    console.print(f"Loading {MODEL_NAME}...")
    model = TextEmbedding(model_name=MODEL_NAME)

    console.print(f"Embedding {len(chunks)} chunks...")
    embeddings = embed([c["text"] for c in chunks], model)
    console.print(
        f"Embedded shape: {embeddings.shape}  "
        f"(memory: {embeddings.nbytes / 1024:.1f} KB)"
    )

    # ---- 4. Save to disk --------------------------------------------------
    console.rule("[bold cyan]4. Save[/]")
    np.save(EMBEDDINGS_FILE, embeddings)
    with open(CHUNKS_FILE, "w") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + "\n")
    console.print(
        f"[green]✓[/] Saved embeddings → "
        f"{EMBEDDINGS_FILE.relative_to(PROJECT_ROOT)}\n"
        f"[green]✓[/] Saved metadata   → "
        f"{CHUNKS_FILE.relative_to(PROJECT_ROOT)}"
    )

    # ---- 5. Peek ----------------------------------------------------------
    console.rule("[bold cyan]5. Peek at the index[/]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("id", justify="right")
    table.add_column("file", style="dim")
    table.add_column("chunk", justify="right")
    table.add_column("chars", justify="right")
    table.add_column("preview", max_width=55)
    for c in chunks[:8]:
        preview = c["text"][:55].replace("\n", " ⏎ ")
        if len(c["text"]) > 55:
            preview += "…"
        table.add_row(str(c["id"]), c["file"], str(c["chunk_index"]),
                      str(c["n_chars"]), preview)
    console.print(table)
    if len(chunks) > 8:
        console.print(f"[dim]…{len(chunks) - 8} more chunks. "
                      f"Inspect with: head {CHUNKS_FILE.relative_to(PROJECT_ROOT)}[/]")

    console.print(
        f"\n[dim]Next: run [bold]phase-2/03_retrieve.py 'your question'[/] (coming up) "
        f"to query this index with semantic search.[/]"
    )


if __name__ == "__main__":
    main()
