"""
Phase 1 — Eval scaffold.

The point: practice eval-driven development from your very first project.
A 20-row eval set early is worth more than 200 rows of clever prompts.

This is a *structural* eval — does the output have the right shape and
basic sanity properties? It does NOT judge correctness of answers (that's
LLM-as-judge territory, Phase 2 territory). Start simple.

Run:
    uv run phase-1/evals/eval_quiz.py
"""
import json
import sys
import time
from pathlib import Path

# Make sibling module importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table

from importlib import import_module
quiz_cli = import_module("02_quiz_cli")  # filename starts with a digit

console = Console()
TOPICS_FILE = Path(__file__).parent / "topics.jsonl"


CHECK_NAMES = (
    "right_question_count",
    "all_have_answers",
    "all_have_explanations",
    "answers_differ_from_questions",
    "questions_unique",
)


def check(quiz, expected_n: int) -> dict[str, bool]:
    """Each check returns a bool. True = pass."""
    qs = quiz.questions
    return {
        "right_question_count": len(qs) == expected_n,
        "all_have_answers": all(q.answer.strip() for q in qs),
        "all_have_explanations": all(q.explanation.strip() for q in qs),
        "answers_differ_from_questions": all(
            q.answer.strip().lower() != q.question.strip().lower() for q in qs
        ),
        "questions_unique": len({q.question for q in qs}) == len(qs),
    }


def main():
    rows = [json.loads(l) for l in TOPICS_FILE.read_text().splitlines() if l.strip()]

    table = Table(title="Phase 1 — Quiz CLI Eval")
    table.add_column("Topic", style="cyan", max_width=30)
    table.add_column("Latency")
    table.add_column("Checks")
    table.add_column("Pass")

    total_pass = 0
    total_checks = 0
    runs_ok = 0
    runs_errored = 0

    for row in rows:
        t0 = time.time()
        try:
            quiz = quiz_cli.make_quiz(
                row["topic"], n=row["expected_n"], difficulty=row["difficulty"]
            )
        except Exception as e:
            # An errored run counts as ALL checks failing — not as a skip.
            # Otherwise the headline score silently inflates.
            runs_errored += 1
            total_checks += len(CHECK_NAMES)
            table.add_row(row["topic"], "—", f"[red]ERROR: {e}[/]", f"0/{len(CHECK_NAMES)}")
            continue

        runs_ok += 1
        latency = f"{time.time() - t0:.1f}s"

        results = check(quiz, row["expected_n"])
        passed = sum(results.values())
        total = len(results)
        total_pass += passed
        total_checks += total

        details = "\n".join(
            f"{'✓' if v else '✗'} {k}" for k, v in results.items()
        )
        table.add_row(row["topic"], latency, details, f"{passed}/{total}")

    console.print(table)
    pct = (total_pass / total_checks * 100) if total_checks else 0
    color = "green" if pct == 100 else "yellow" if pct >= 80 else "red"
    console.print(
        f"\n[bold {color}]Overall: {total_pass}/{total_checks} checks "
        f"({pct:.0f}%)[/]  "
        f"[dim]| runs ok: {runs_ok}  errored: {runs_errored}[/]"
    )


if __name__ == "__main__":
    main()
