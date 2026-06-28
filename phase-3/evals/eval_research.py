"""
Phase 3 eval — does the research agent actually work, or did it get lucky once?

This is the LAST Phase 3 deliverable. Exercises 1-5 BUILT the agent; this one
MEASURES it. The lesson: an agent is judged on its TRAJECTORY (the sequence of
tool calls), not just its final text. So we score five dimensions, cheap
deterministic ones first, the expensive LLM-judge last:

  1. completed          (deterministic)  did it actually write a report?
  2. trajectory_ok      (deterministic)  search → fetch → write, under budget?
  3. citations_grounded (deterministic)  is every cited URL one it ACTUALLY
                                         fetched? (catches hallucinated sources)
  4. contains_expected  (deterministic)  does the report mention a known fact?
  5. answers_question   (LLM-as-judge)   Sonnet grades the report 1-5.

Why deterministic-first: those checks are free and catch the dumb, common agent
failures (never wrote a file; cited a URL it never read; looped 14 times). You
only spend judge tokens on reports that already passed the cheap gates.

Why this differs from the Phase 1 and 2 evals: those scored a single OUTPUT.
Here dimensions 2 and 3 score the PROCESS — the tool-call sequence — which is
the thing that makes an agent an agent. A report can read perfectly and still
be a failure if its citations are invented.

Run:
    uv run phase-3/evals/eval_research.py
    uv run phase-3/evals/eval_research.py --model claude-sonnet-4-6   # stronger agent
"""
import argparse
import importlib.util
import json
import os
import re

from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv(override=True)
console = Console()

HERE = os.path.dirname(__file__)
EVAL_SET = os.path.join(HERE, "eval_set.jsonl")
AGENT_FILE = os.path.join(HERE, "..", "05_research_agent.py")

ITER_BUDGET = 8          # a sane research run shouldn't need more than this
JUDGE_PASS = 4           # answers_question passes at 4/5 or better


# ---------------------------------------------------------------------------
# Import run_agent from 05_research_agent.py. The filename starts with a digit,
# so a normal `import` is impossible — load it by path with importlib.
# ---------------------------------------------------------------------------
def _load_agent():
    spec = importlib.util.spec_from_file_location("research_agent", AGENT_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Deterministic scorers — free, run first
# ---------------------------------------------------------------------------
def _norm_url(u: str) -> str:
    """Normalize for comparison: drop scheme, trailing slash, trailing punctuation."""
    u = re.sub(r"^https?://", "", u.strip())
    return u.rstrip("/.,);]")


def cited_urls(report: str) -> list[str]:
    """Pull URLs out of the report's '## Sources' section (or the whole report)."""
    idx = report.lower().rfind("## sources")
    section = report[idx:] if idx != -1 else report
    return re.findall(r"https?://[^\s\)\]]+", section)


def score_trajectory(tools: list[str], iterations: int) -> tuple[bool, str]:
    """search BEFORE fetch BEFORE write, and within the iteration budget."""
    def first(name):
        return tools.index(name) if name in tools else 10**9
    ordered = first("web_search") < first("fetch_url") < first("write_file")
    in_budget = iterations <= ITER_BUDGET
    note = f"order={'ok' if ordered else 'BAD'}, iters={iterations}/{ITER_BUDGET}"
    return (ordered and in_budget), note


def score_grounded(report: str, fetched: list[str]) -> tuple[bool, str]:
    """Every cited URL must correspond to a URL the agent actually fetched."""
    cited = cited_urls(report)
    if not cited:
        return False, "no citations found"
    fetched_norm = [_norm_url(f) for f in fetched]
    grounded = 0
    for c in cited:
        cn = _norm_url(c)
        if any(cn == fn or cn in fn or fn in cn for fn in fetched_norm):
            grounded += 1
    return grounded == len(cited), f"{grounded}/{len(cited)} cited URLs were fetched"


# ---------------------------------------------------------------------------
# LLM-as-judge — expensive, runs last (only the semantic question)
# ---------------------------------------------------------------------------
JUDGE_TOOL = [{
    "name": "submit_grade",
    "description": "Grade how well the report answers the question.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 1, "maximum": 5,
                      "description": "1=ignores the question, 5=fully and accurately answers it."},
            "reason": {"type": "string", "description": "One sentence."},
        },
        "required": ["score", "reason"],
    },
}]


def judge_answer(client, judge_model, question, report) -> dict:
    resp = client.messages.create(
        model=judge_model,
        max_tokens=512,
        system="You are a strict grader. Judge ONLY whether the report answers the question, accurately and on-topic.",
        tools=JUDGE_TOOL,
        tool_choice={"type": "tool", "name": "submit_grade"},
        messages=[{"role": "user", "content": f"QUESTION:\n{question}\n\nREPORT:\n{report}"}],
    )
    return next(b for b in resp.content if b.type == "tool_use").input


# ---------------------------------------------------------------------------
# The harness
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Eval the Phase 3 research agent.")
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"),
                        help="The agent (generator) model.")
    parser.add_argument("--judge-model", default="claude-sonnet-4-6",
                        help="The LLM-as-judge model (stronger than the agent on purpose).")
    args = parser.parse_args()

    agent = _load_agent()
    client = Anthropic()

    with open(EVAL_SET) as f:
        cases = [json.loads(line) for line in f if line.strip()]

    console.print(f"[bold]Phase 3 eval[/] — {len(cases)} questions  •  "
                  f"agent={args.model}  judge={args.judge_model}\n")

    rows = []
    total_cost = 0.0
    for i, case in enumerate(cases, 1):
        q = case["question"]
        console.print(f"[dim]({i}/{len(cases)}) running agent on:[/] {q}")

        # Run the agent SILENTLY and score the trajectory it returns.
        run = agent.run_agent(q, args.model, max_iterations=ITER_BUDGET + 4,
                              max_tokens=4096, trace=False, quiet=True)
        total_cost += run["cost"]
        report = run["report_content"] or ""

        completed = run["completed"] and bool(report)
        traj_ok, traj_note = score_trajectory(run["tools_called"], run["iterations"])
        grounded_ok, grounded_note = (score_grounded(report, run["fetched_urls"])
                                      if report else (False, "no report"))
        expected_ok = any(kw.lower() in report.lower() for kw in case["must_include"])

        # LLM-judge only if there's a report to grade.
        if report:
            grade = judge_answer(client, args.judge_model, q, report)
            judge_score, judge_reason = grade["score"], grade["reason"]
        else:
            judge_score, judge_reason = 0, "no report to grade"

        passed = completed and traj_ok and grounded_ok and expected_ok and judge_score >= JUDGE_PASS
        rows.append({
            "q": q, "completed": completed, "traj_ok": traj_ok, "traj_note": traj_note,
            "grounded_ok": grounded_ok, "grounded_note": grounded_note,
            "expected_ok": expected_ok, "judge_score": judge_score, "judge_reason": judge_reason,
            "passed": passed, "cost": run["cost"], "iters": run["iterations"],
        })
        console.print(f"   [dim]→ {'PASS' if passed else 'FAIL'}  ({traj_note}; {grounded_note}; "
                      f"judge {judge_score}/5)  ${run['cost']:.4f}[/]\n")

    _scoreboard(rows, total_cost)


def _scoreboard(rows, total_cost):
    def mark(b): return "[green]✓[/]" if b else "[red]✗[/]"

    table = Table(title="Phase 3 — Research Agent Eval", show_lines=True)
    table.add_column("#", justify="right")
    table.add_column("Question", max_width=34)
    table.add_column("done", justify="center")
    table.add_column("traj", justify="center")
    table.add_column("grounded", justify="center")
    table.add_column("fact", justify="center")
    table.add_column("answers", justify="center")
    table.add_column("PASS", justify="center")

    for i, r in enumerate(rows, 1):
        table.add_row(
            str(i), r["q"],
            mark(r["completed"]), mark(r["traj_ok"]),
            f"{mark(r['grounded_ok'])} {r['grounded_note'].split(' ')[0]}",
            mark(r["expected_ok"]),
            f"{r['judge_score']}/5",
            "[bold green]PASS[/]" if r["passed"] else "[bold red]FAIL[/]",
        )
    console.print(table)

    n = len(rows)
    passes = sum(r["passed"] for r in rows)
    avg_judge = sum(r["judge_score"] for r in rows) / n if n else 0
    console.print(
        f"\n[bold]Overall:[/] {passes}/{n} passed  •  "
        f"avg answers score {avg_judge:.1f}/5  •  "
        f"total cost [bold]${total_cost:.4f}[/]"
    )
    # Surface the judge's reasons for any failures — the diagnostic.
    for i, r in enumerate(rows, 1):
        if not r["passed"]:
            console.print(f"[yellow]  ✗ Q{i} why:[/] {r['traj_note']}; {r['grounded_note']}; "
                          f"judge {r['judge_score']}/5 — {r['judge_reason']}")


if __name__ == "__main__":
    main()
