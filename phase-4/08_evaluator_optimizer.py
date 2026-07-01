"""
Phase 4, Exercise 08 — EVALUATOR-OPTIMIZER (the fifth and final BEA pattern).

Two fixed roles in a loop:

    GENERATOR (optimizer) writes a draft ─▶ EVALUATOR grades it + lists issues
              ▲                                          │
              │                                  verdict == "revise"?
              └──────── revise with feedback ◀───────────┘
                              (until "accept" or max rounds)

The loop is back — but this is still a WORKFLOW
-----------------------------------------------
Ex 07 stopped one step short of a loop. This exercise adds it back, which forces
the question the whole phase has been circling: if it LOOPS, isn't it an agent?
No. It's a workflow, and this is the subtlest case of the distinction, so read
carefully:

- The two ROLES are fixed (you wrote generator + evaluator).
- The CYCLE is fixed (generate → evaluate → maybe revise, in that order).
- The EXIT is fixed by your code: `verdict == "accept"` OR `round == max`.

The evaluator is an LLM, and its verdict GATES the loop — so an LLM's output now
influences control flow. That's why this sits closest to the agent line. But the
model still only FILLS A FIXED SLOT ("grade this draft against these criteria").
It does not choose what to do next from an open set of actions; your code does,
by checking the verdict. An AGENT (Phase 3) has an open action space — the model
decides which tool to call, when, and whether to continue, with no predefined
cycle. Here the cycle is predefined; the model just supplies a graded signal.

Two callbacks this pattern ties together
----------------------------------------
- Phase 3, Ex 04 (self-critique / Reflexion): this IS that loop, now named as a
  BEA pattern. Generator + evaluator are two "agents" passing work back and forth
  — the seed of multi-agent, with no framework: two prompts and a `while`.
- Phase 4, Ex 04 (the gate): there the gate was pure PYTHON and just STOPPED the
  chain. Here the gate is an LLM (because "is this clear and jargon-free?" needs
  judgment, not `len()`), and instead of stopping it feeds specific issues back
  so the next draft can fix them. Evaluator-optimizer = a gate that grades and loops.

When it earns its keep (from the BEA article)
---------------------------------------------
When you have CLEAR evaluation criteria AND iterative refinement measurably helps
— literary translation, complex search/writing, code that must meet a spec. It
roughly doubles-to-N×'s cost (every round is generate + evaluate), so it's wasted
on tasks with nothing to improve. Match the pattern to the task.

Run:
    uv run phase-4/08_evaluator_optimizer.py "Explain what a database index is to a non-technical manager, under 80 words."
    uv run phase-4/08_evaluator_optimizer.py "Write a 4-line poem about gradient descent" --show-drafts
    uv run phase-4/08_evaluator_optimizer.py "Explain TCP's 3-way handshake simply" --evaluator-model claude-sonnet-4-6
"""
import argparse
import os

from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(override=True)
console = Console()

PRICES = {
    "claude-haiku-4-5":  (0.80,  4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-8":   (15.00, 75.00),
}


def _cost(model: str, in_t: int, out_t: int) -> float:
    in_price, out_price = PRICES.get(model, (0.0, 0.0))
    return (in_t * in_price + out_t * out_price) / 1_000_000


# ===========================================================================
# GENERATOR (the optimizer). Round 1 has no feedback; later rounds get the
# evaluator's concrete issues and must address every one.
# ===========================================================================
def generate(client: Anthropic, model: str, task: str,
             prev_draft: str | None, issues: list[str] | None) -> tuple[str, float]:
    system = (
        "You are a careful writer. Produce the best possible response to the task. "
        "If given evaluator feedback, address EVERY point in your revision — do not "
        "ignore any. Output only the response itself."
    )
    if prev_draft is None:
        user = task
    else:
        feedback = "\n".join(f"- {i}" for i in issues)
        user = (
            f"Task: {task}\n\nYour previous draft:\n{prev_draft}\n\n"
            f"The evaluator found these issues — fix all of them:\n{feedback}\n\n"
            f"Produce an improved version."
        )
    resp = client.messages.create(
        model=model, max_tokens=1024, system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text, _cost(model, resp.usage.input_tokens, resp.usage.output_tokens)


# ===========================================================================
# EVALUATOR. Forced tool use => a structured verdict we can branch on, never
# prose. Deliberately DEMANDING — a polite evaluator accepts round 1 and the
# loop teaches nothing (the Phase 3 lesson: the critic is where the leverage is).
# ===========================================================================
EVAL_TOOL = {
    "name": "submit_evaluation",
    "description": "Grade the draft against the task's criteria.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "description": "1 (poor) to 10 (excellent)."},
            "issues": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific, actionable problems. Empty only if truly excellent.",
            },
            "verdict": {"type": "string", "enum": ["accept", "revise"]},
        },
        "required": ["score", "issues", "verdict"],
    },
}


def evaluate(client: Anthropic, model: str, task: str, draft: str) -> tuple[dict, float]:
    resp = client.messages.create(
        model=model, max_tokens=512,
        system=(
            "You are a demanding evaluator. Grade the draft against the task's criteria. "
            "Name CONCRETE, actionable problems — not vibes. Only return verdict 'accept' if "
            "the draft genuinely meets every criterion; otherwise 'revise'. Be a tough grader: "
            "a first draft is rarely a 9 or 10."
        ),
        tools=[EVAL_TOOL],
        tool_choice={"type": "tool", "name": "submit_evaluation"},
        messages=[{"role": "user", "content": f"Task: {task}\n\nDraft to grade:\n{draft}"}],
    )
    tool_use = next(b for b in resp.content if b.type == "tool_use")
    return tool_use.input, _cost(model, resp.usage.input_tokens, resp.usage.output_tokens)


# ===========================================================================
# The loop. YOU own this control flow — the fixed cycle and the exit condition.
# The two LLMs fill fixed slots (write / grade); they don't decide the path.
# ===========================================================================
def run(task: str, model: str, eval_model: str, max_rounds: int, show_drafts: bool) -> None:
    client = Anthropic()
    total = 0.0
    draft, issues = None, None

    for rnd in range(1, max_rounds + 1):
        console.rule(f"[bold cyan]round {rnd} — generate[/]")
        draft, c_gen = generate(client, model, task, draft, issues)
        total += c_gen
        if show_drafts or rnd == 1:
            console.print(draft)
        else:
            console.print("[dim](draft hidden — pass --show-drafts to see every revision)[/]")

        console.rule(f"[bold cyan]round {rnd} — evaluate[/]")
        verdict, c_eval = evaluate(client, eval_model, task, draft)
        total += c_eval
        issues = verdict["issues"]
        mark = "[green]✓ accept[/]" if verdict["verdict"] == "accept" else "[yellow]↻ revise[/]"
        console.print(f"score [bold]{verdict['score']}/10[/]  →  {mark}")
        for i in issues:
            console.print(f"[dim]   • {i}[/]")

        # The EXIT is code, checking the evaluator's structured verdict. The model
        # supplied a signal; your `if` decides whether to loop. That's the line
        # between this (workflow) and an agent (model picks the next action itself).
        if verdict["verdict"] == "accept":
            console.rule("[bold green]✓ accepted[/]")
            break
    else:
        console.rule(f"[bold red]✗ stopped at max rounds ({max_rounds}) without 'accept'[/]")

    console.print(f"\n[bold]Final draft:[/]\n{draft}")
    console.print(f"\n[dim]rounds run: up to {max_rounds} • generator={model} • "
                  f"evaluator={eval_model} • total [bold]${total:.4f}[/][/]")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluator-optimizer: generate → evaluate → refine until accepted (a workflow)."
    )
    parser.add_argument("task", nargs="+", help="The task to optimize toward.")
    parser.add_argument("--max-rounds", type=int, default=4, help="Cap on generate/evaluate cycles (default 4).")
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"),
                        help="Generator model (default Haiku).")
    parser.add_argument("--evaluator-model", default=None,
                        help="Evaluator model. Defaults to --model; set stronger (e.g. claude-sonnet-4-6) "
                             "for the asymmetric-critic trick from Phase 3.")
    parser.add_argument("--show-drafts", action="store_true", help="Print every draft, not just round 1 + final.")
    args = parser.parse_args()

    task = " ".join(args.task)
    eval_model = args.evaluator_model or args.model
    console.print(f"[bold]Task:[/] {task}\n[dim]generator={args.model}  evaluator={eval_model}  "
                  f"max_rounds={args.max_rounds}[/]\n")
    run(task, args.model, eval_model, args.max_rounds, args.show_drafts)


if __name__ == "__main__":
    main()
