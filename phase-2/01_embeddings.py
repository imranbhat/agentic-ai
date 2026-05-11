"""
Phase 2, Exercise 1 — Embeddings and similarity.

An EMBEDDING is a fixed-size list of numbers (a vector) that represents the
*meaning* of a piece of text. Two texts with similar meaning produce similar
vectors, even if they share no words.

Why this matters: it's the foundation of every "search by meaning" system.
RAG, semantic search, recommendations — all the same trick:
    embed everything → embed your query → find the closest vectors.

We use fastembed (ONNX runtime, free, local, no API key, no PyTorch). The
concepts are identical with Voyage (Anthropic's recommended cloud provider),
OpenAI embeddings, or Cohere — only the import line changes. Provider swap is
a Phase 5 concern.

First run downloads the model (~130MB to ~/.cache/fastembed). Subsequent
runs are instant.

Run:
    uv run phase-2/01_embeddings.py
"""
import numpy as np
from fastembed import TextEmbedding
from rich.console import Console
from rich.table import Table

console = Console()

# BGE small is a 2024 model, 384-dim output, fast on CPU, English-tuned.
# For multilingual try BAAI/bge-m3. For higher quality at higher cost,
# Voyage's voyage-3 is the current best for Anthropic-native stacks.
MODEL_NAME = "BAAI/bge-small-en-v1.5"

console.print(f"[dim]Loading {MODEL_NAME} (first run downloads weights ~130MB)...[/]")
model = TextEmbedding(model_name=MODEL_NAME)


def embed(texts: list[str]) -> np.ndarray:
    """Embed a list of texts, return an (N, dim) array of unit vectors.

    fastembed's `embed` returns a generator of numpy arrays. We stack them
    and normalize so cosine similarity = dot product (cheap to compute).
    """
    vecs = np.array(list(model.embed(texts)))
    # L2-normalize each row so dot products are cosine similarities
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / np.clip(norms, 1e-12, None)


# A handful of texts designed to reveal what the embedding "knows."
texts = [
    "I love dogs",
    "I adore puppies",                       # same meaning, different words
    "I love cats",                           # related but different animal
    "Python is a great programming language",
    "I enjoy writing code",                  # related to programming
    "The bank approved my loan",             # bank = financial
    "We sat on the river bank at sunset",    # bank = geography
    "My on that talks about LLMs abd Vectors",
    "Fake tools as a structuring trick",
]

embeddings = embed(texts)

# ---- 1. What does an embedding look like? ---------------------------------
console.rule("[bold cyan]1. Each embedding is a vector[/]")
console.print(f"Number of texts:        {len(texts)}")
console.print(f"Embedding dimensions:   {embeddings.shape[1]}")
console.print(f"Vector type:            {type(embeddings).__name__}, dtype={embeddings.dtype}")
console.print(f"\n[dim]First 8 values of embedding[0]:[/]")
console.print(f"  {np.array2string(embeddings[0][:8], precision=4)}")
console.print(
    f"\n[dim]Each text becomes a {embeddings.shape[1]}-dim vector. All {len(texts)} "
    f"vectors live in the SAME space — that's what makes them comparable. "
    f"The numbers are not human-readable; meaning is encoded in the geometry.[/]"
)

# ---- 2. Cosine similarity --------------------------------------------------
console.rule("[bold cyan]2. Cosine similarity[/]")
console.print(
    "Range: -1 (opposite) → 0 (unrelated) → 1 (identical).\n"
    "Real-world: [green]>0.7 = very similar[/], [yellow]0.4-0.7 = related[/], "
    "[red]<0.3 = unrelated[/].\n"
    "Because vectors are normalized, similarity = dot product (very fast).\n"
)

sim = embeddings @ embeddings.T  # NxN matrix of all pairs

table = Table(show_header=True, header_style="bold")
table.add_column("", style="dim cyan", max_width=32)
for i in range(len(texts)):
    table.add_column(f"#{i}", justify="right")
for i, t in enumerate(texts):
    row = [f"#{i} {t[:28]}"]
    for j in range(len(texts)):
        s = sim[i][j]
        if i == j:
            cell = f"[dim]{s:.2f}[/]"
        elif s > 0.7:
            cell = f"[bold green]{s:.2f}[/]"
        elif s > 0.4:
            cell = f"[yellow]{s:.2f}[/]"
        else:
            cell = f"[red]{s:.2f}[/]"
        row.append(cell)
    table.add_row(*row)
console.print(table)

# ---- 3. What you should notice --------------------------------------------
console.rule("[bold cyan]3. What to notice[/]")
console.print(
    "[dim]• #0 'I love dogs' ≈ #1 'I adore puppies' — different words, same meaning. [bold]Models 'understand' synonyms.[/bold]\n"
    "• #3 'Python is a great programming language' ≈ #4 'I enjoy writing code' — semantic match without word overlap.\n"
    "• #5 'bank approved my loan' vs #6 'sat on the river bank' — model distinguishes the two senses of 'bank'.\n"
    "• Diagonal is 1.00 — every vector is identical to itself.\n"
    "• Try editing the texts list and rerun. Build intuition for what the model sees.[/]"
)

# ---- 4. Top-K retrieval (preview of next exercise) -------------------------
console.rule("[bold cyan]4. Preview: top-K retrieval[/]")
query = "I'm a software engineer who likes pets"
q_emb = embed([query])[0]

# Score every text against the query. argsort gives indices, [::-1] for descending.
scores = embeddings @ q_emb
top_k = np.argsort(scores)[::-1][:3]

console.print(f"Query: [bold]{query!r}[/]\n")
console.print("Top 3 most similar texts from our list:")
for rank, idx in enumerate(top_k, 1):
    console.print(f"  {rank}. [{scores[idx]:.3f}] {texts[idx]}")

console.print(
    "\n[dim]This is the core of RAG. Your 'corpus' is just a bunch of text chunks. "
    "You embed all of them once. At query time you embed the question and pick the "
    "highest-scoring chunks. That's it. No magic. The next file does it for real "
    "across your own markdown files.[/]"
)
