"""
Phase 2, Exercise 6 — LLM-as-judge eval for the RAG chatbot.

Why this exists: in Phase 1 we did STRUCTURAL evals (did the JSON have the
right shape?). That's cheap and deterministic, but it can't tell you whether
an answer is actually CORRECT. RAG outputs are prose — to grade prose, you
need a judge with reading comprehension. That judge is another LLM call.

What this file evaluates, separately:

1. RETRIEVAL (deterministic): did the top-K chunks contain at least one
   from the expected source file? This is recall@K — pure Python check,
   no LLM, no cost.

2. GENERATION (LLM-as-judge): does the model's answer match the reference?
   We force Sonnet to call a `submit_grade` tool (Phase 1's trick) to get
   structured 1-5 scores across correctness/completeness/groundedness.

3. REFUSAL (deterministic): for out-of-corpus questions, did the model
   actually refuse? Substring match against known refusal phrases.

A good eval reports each dimension separately. Same as Phase 1's gotcha:
a single headline number lies. Retrieval failing and generation failing are
two different bugs requiring two different fixes.

Run:
    uv run phase-2/evals/eval_rag.py
"""
import json
import os
import sys
import time
from importlib import import_module
from pathlib import Path

# Make sibling phase-2 modules importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anthropic import Anthropic
from dotenv import load_dotenv
from fastembed import TextEmbedding
from rich.console import Console
from rich.table import Table

load_dotenv(override=True)
console = Console()

# Filename starts with a digit, so we can't do `import 04_rag_chat` directly.
rag = import_module("04_rag_chat")

EVAL_SET = Path(__file__).parent / "eval_set.jsonl"
K = 4

# Use a STRONGER model as the judge than the one being graded.
# This reduces self-grading bias (Haiku grading Haiku tends to be lenient).
JUDGE_MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# The judge — forced tool use gives structured grades
# ---------------------------------------------------------------------------
JUDGE_TOOL = {
    "name": "submit_grade",
    "description": "Submit a structured grade for an RAG-generated answer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "correctness": {
                "type": "integer",
                "description": "1-5: factual accuracy vs the reference. 1=wrong, 3=partial, 5=fully correct.",
            },
            "completeness": {
                "type": "integer",
                "description": "1-5: coverage of the reference's key points. 1=missing major info, 5=covers all.",
            },
            "groundedness": {
                "type": "integer",
                "description": "1-5: does the answer cite passages [N] and stay anchored to them. 1=ungrounded, 5=well-cited.",
            },
            "reasoning": {
                "type": "string",
                "description": "1-2 sentences explaining the scores.",
            },
        },
        "required": ["correctness", "completeness", "groundedness", "reasoning"],
    },
}

JUDGE_SYSTEM = """You are a strict grader for a RAG (retrieval-augmented generation) system.

You receive:
- A question
- A reference (gold-standard) answer
- The model's generated answer

Grade three dimensions on a 1-5 scale. Be honest. A 5 means truly excellent;
3 means partial; 1 means wrong or empty. ALWAYS call the submit_grade tool —
never respond in prose."""


def grade_answer(client, question: str, reference: str, answer: str) -> dict:
    """Return a dict of {correctness, completeness, groundedness, reasoning}."""
    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=512,
        system=JUDGE_SYSTEM,
        tools=[JUDGE_TOOL],
        tool_choice={"type": "tool", "name": "submit_grade"},
        messages=[{
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Reference answer:\n{reference}\n\n"
                f"Model's answer:\n{answer}"
            ),
        }],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError("Judge did not call submit_grade — check tool_choice.")


# ---------------------------------------------------------------------------
# Refusal check (deterministic — no LLM call needed)
# ---------------------------------------------------------------------------
REFUSAL_MARKERS = (
    "doesn't cover",
    "don't cover",
    "do not cover",
    "not in the context",
    "outside the context",
    "no information",
    "cannot find",
    "context does not contain",
    "the passages do not",
    "the passages don't",
)


def is_refusal(answer: str) -> bool:
    a = answer.lower()
    return any(m in a for m in REFUSAL_MARKERS)


# ---------------------------------------------------------------------------
# Run RAG for one query — returns (answer_text, retrieved_chunks)
# ---------------------------------------------------------------------------
def run_rag(query: str, k: int, embeddings, chunks, embed_model, client, model: str):
    retrieved = rag.retrieve(query, k, embeddings, chunks, embed_model)
    user_msg = rag.build_user_message(query, retrieved)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=rag.SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    return text, retrieved


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    rows = [json.loads(l) for l in EVAL_SET.read_text().splitlines() if l.strip()]
    rag_model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

    console.print(f"[bold]Eval set:[/]   {len(rows)} questions  ({sum(1 for r in rows if r['type']=='in_corpus')} in-corpus, {sum(1 for r in rows if r['type']=='out_of_corpus')} refusal)")
    console.print(f"[bold]RAG model:[/]  {rag_model}")
    console.print(f"[bold]Judge:[/]     {JUDGE_MODEL}")
    console.print()

    # Load once, reuse across all eval rows
    embeddings, chunks = rag.load_index()
    embed_model = TextEmbedding(model_name=rag.EMBED_MODEL_NAME)
    client = Anthropic()

    table = Table(show_header=True, header_style="bold")
    table.add_column("#", justify="right")
    table.add_column("Question", max_width=42)
    table.add_column("R@K", justify="center")
    table.add_column("Gen", justify="center")
    table.add_column("Reasoning / Answer", max_width=50)

    retrieval_passes = 0
    retrieval_total = 0
    gen_scores: list[float] = []
    refusal_passes = 0
    refusal_total = 0
    errored = 0

    for row in rows:
        q = row["question"]
        try:
            answer, retrieved = run_rag(q, K, embeddings, chunks, embed_model, client, rag_model)
        except Exception as e:
            errored += 1
            table.add_row(str(row["id"]), q, "[red]ERR[/]", "[red]ERR[/]", str(e)[:50])
            continue

        if row["type"] == "in_corpus":
            # Retrieval check
            retrieved_files = [c[0]["file"] for c in retrieved]
            r_ok = row["expected_source"] in retrieved_files
            retrieval_total += 1
            retrieval_passes += int(r_ok)
            r_cell = "[green]✓[/]" if r_ok else "[red]✗[/]"

            # Generation check (LLM-as-judge)
            grade = grade_answer(client, q, row["reference_answer"], answer)
            avg = (grade["correctness"] + grade["completeness"] + grade["groundedness"]) / 3
            gen_scores.append(avg)
            color = "green" if avg >= 4 else "yellow" if avg >= 3 else "red"
            gen_cell = f"[{color}]{avg:.1f}[/]"
            reasoning = grade["reasoning"]

        else:  # out_of_corpus → expect refusal
            refused = is_refusal(answer)
            refusal_total += 1
            refusal_passes += int(refused)
            r_cell = "[dim]n/a[/]"
            gen_cell = "[green]refused[/]" if refused else "[red]answered![/]"
            reasoning = answer[:90].replace("\n", " ")

        # Truncate long reasoning for the table
        if len(reasoning) > 90:
            reasoning = reasoning[:87] + "…"
        table.add_row(str(row["id"]), q, r_cell, gen_cell, reasoning)

    console.print(table)

    # ---- Honest summary (Phase 1's gotcha #2: don't let the score lie) ----
    console.rule("[bold cyan]Summary[/]")

    if retrieval_total:
        pct = retrieval_passes / retrieval_total * 100
        color = "green" if pct >= 80 else "yellow" if pct >= 60 else "red"
        console.print(
            f"[bold]Retrieval@{K}:[/]   "
            f"[{color}]{retrieval_passes}/{retrieval_total} passed[/] ({pct:.0f}%)  "
            f"[dim]— did the right file end up in top-{K}?[/]"
        )

    if gen_scores:
        avg_gen = sum(gen_scores) / len(gen_scores)
        color = "green" if avg_gen >= 4 else "yellow" if avg_gen >= 3 else "red"
        console.print(
            f"[bold]Generation:[/]   "
            f"[{color}]average {avg_gen:.2f}/5[/] across {len(gen_scores)} answers  "
            f"[dim]— LLM-as-judge across correctness/completeness/groundedness[/]"
        )

    if refusal_total:
        pct = refusal_passes / refusal_total * 100
        color = "green" if pct == 100 else "yellow" if pct >= 50 else "red"
        console.print(
            f"[bold]Refusal:[/]      "
            f"[{color}]{refusal_passes}/{refusal_total} correctly refused[/] ({pct:.0f}%)  "
            f"[dim]— did the model honor the guardrail for out-of-corpus questions?[/]"
        )

    if errored:
        console.print(f"[bold red]Errored:[/]     {errored} row(s) failed to run")

    console.print(
        f"\n[dim]Note: this eval makes ~{len(rows)*2} API calls. At Haiku+Sonnet mix, "
        f"a full run costs ~$0.02-0.05. Cheap enough to run on every prompt change.[/]"
    )


if __name__ == "__main__":
    main()
