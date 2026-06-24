"""
Phase 3, Exercise 4 — The self-critique loop (a.k.a. Reflexion).

Exercises 1-3 wired the model to EXTERNAL tools (Python functions). This one
wires the model to ITSELF. The loop is:

    GENERATE a draft
      → CRITIQUE it (a second model call grading against a rubric)
        → if the critic says "revise", REGENERATE using the feedback
          → critique again ... until ACCEPT or we hit max rounds.

Why this is the same idea as before, and why it's different
-----------------------------------------------------------
SAME: it's still "model → result → model → ..." in a while-loop. Exit on a
stop condition. Cap the iterations. You already know this shape.

DIFFERENT: the "tool" that produces the result is no longer `calculator()`.
It's a whole second LLM call — the CRITIC — playing a different role. The
agent is now improving its OWN output instead of fetching facts. This is the
seed of multi-agent systems: a generator agent and a critic agent passing
work back and forth. In Phase 4 you'll do this with a framework; here you
see there's no magic — it's two prompts and a loop.

Two roles, two prompts
----------------------
- GENERATOR: writes the answer. On revision rounds it's handed the previous
  draft plus the critique and told to address every point.
- CRITIC: grades the draft. Uses FORCED TOOL USE (Phase 1's trick) so its
  verdict comes back as reliable JSON — a score, a list of concrete issues,
  and an accept/revise verdict. We don't parse prose; we read fields.

The critic is where the leverage is. A vague rubric gives lazy "looks good!"
critiques and the loop accepts junk on round 1. A sharp, demanding rubric
forces real revisions. Tune the CRITIC_SYSTEM prompt and watch round count move.

Run:
    uv run phase-3/04_self_critique.py "Explain recursion to a 10-year-old"
    uv run phase-3/04_self_critique.py "Write a 4-line poem about gradient descent"
    uv run phase-3/04_self_critique.py "Summarize why RAG beats fine-tuning for fresh data" --max-rounds 4
    uv run phase-3/04_self_critique.py "Explain TCP handshake" --critic-model claude-sonnet-4-6
    uv run phase-3/04_self_critique.py "Explain recursion to a 10-year-old" --show-drafts
"""
import argparse
import json
import os
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

load_dotenv(override=True)
console = Console()

PRICES = {
    "claude-haiku-4-5":  (0.80,  4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7":   (15.00, 75.00),
    "claude-opus-4-8":   (15.00, 75.00),
}


# ===========================================================================
# 1. The two roles, as system prompts
# ===========================================================================
GENERATOR_SYSTEM = """You are a clear, concise writer. Answer the user's request directly and well.

When you are given a PREVIOUS DRAFT and CRITIQUE, produce a NEW draft that
fixes every issue raised. Do not defend the old draft or explain your changes
— just return the improved version. Keep what worked; repair what didn't."""

# The critic is demanding ON PURPOSE. A polite critic accepts round-1 drafts
# and the loop teaches you nothing. We want it to find real, specific problems.
CRITIC_SYSTEM = """You are a ruthless but fair editor. You grade a draft against the user's original request.

Hold a high bar. A draft only earns "accept" if it genuinely needs no further
work: it fully answers the request, is accurate, is appropriately concise, and
has no weak spots a good editor would flag. "Pretty good" is NOT accept — that
is "revise" with specific notes.

Your issues must be CONCRETE and ACTIONABLE — name the exact sentence or gap,
not "could be clearer". You MUST call the `submit_critique` tool to report your
verdict. Do not reply in prose."""

# Forced-output schema for the critic (Phase 1 concept: tool use as structured output).
CRITIC_TOOL = [{
    "name": "submit_critique",
    "description": "Report your structured judgment of the draft.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {
                "type": "integer",
                "description": "Quality from 1 (unusable) to 10 (publishable as-is).",
                "minimum": 1,
                "maximum": 10,
            },
            "issues": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Concrete, actionable problems. Empty list only if flawless.",
            },
            "verdict": {
                "type": "string",
                "enum": ["accept", "revise"],
                "description": "'accept' only if no further work is warranted.",
            },
        },
        "required": ["score", "issues", "verdict"],
    },
}]


# ===========================================================================
# 2. The two calls
# ===========================================================================
def generate(client, model, task, prev_draft=None, critique=None) -> tuple[str, Any]:
    """Produce a draft. On revision rounds, fold in the prior draft + critique."""
    if prev_draft is None:
        user_content = task
    else:
        # Why: handing the model its own prior work plus targeted feedback is
        # what makes round N+1 better than round N. The critique is the signal.
        issues = "\n".join(f"  - {i}" for i in critique["issues"])
        user_content = (
            f"ORIGINAL REQUEST:\n{task}\n\n"
            f"PREVIOUS DRAFT:\n{prev_draft}\n\n"
            f"CRITIQUE (score {critique['score']}/10) — fix all of these:\n{issues}\n\n"
            f"Return the improved draft only."
        )
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=GENERATOR_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    return text, resp.usage


def critique(client, model, task, draft) -> tuple[dict, Any]:
    """Grade a draft. tool_choice forces submit_critique, so we always get JSON."""
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=CRITIC_SYSTEM,
        tools=CRITIC_TOOL,
        # Forcing the tool guarantees structured output — no "Sure! Here's my review:" prose.
        tool_choice={"type": "tool", "name": "submit_critique"},
        messages=[{
            "role": "user",
            "content": f"ORIGINAL REQUEST:\n{task}\n\nDRAFT TO GRADE:\n{draft}",
        }],
    )
    tool_block = next(b for b in resp.content if b.type == "tool_use")
    return tool_block.input, resp.usage


# ===========================================================================
# 3. The loop
# ===========================================================================
def run(task: str, gen_model: str, critic_model: str, max_rounds: int, show_drafts: bool) -> None:
    client = Anthropic()
    cost = _Cost()

    console.print(f"[bold]Task:[/] {task}")
    console.print(
        f"[dim]generator={gen_model}  critic={critic_model}  max_rounds={max_rounds}[/]\n"
    )

    # Round 0: first draft, no critique yet.
    draft, usage = generate(client, gen_model, task)
    cost.add(gen_model, usage)
    if show_drafts:
        console.print(Panel(draft, title="draft v1", border_style="dim"))

    for rnd in range(1, max_rounds + 1):
        console.rule(f"[bold cyan]Round {rnd}[/]")

        verdict, usage = critique(client, critic_model, task, draft)
        cost.add(critic_model, usage)

        score = verdict["score"]
        bar = "█" * score + "░" * (10 - score)
        console.print(f"[bold]Critic:[/] {score}/10  [{'green' if score >= 8 else 'yellow'}]{bar}[/]")
        for issue in verdict["issues"]:
            console.print(f"  [yellow]•[/] {issue}")

        # ---- Exit condition: the critic is satisfied ----
        if verdict["verdict"] == "accept":
            console.print("[bold green]✓ Critic accepted.[/]")
            break

        # ---- Otherwise revise and loop ----
        console.print("[magenta]↻ Revising...[/]")
        draft, usage = generate(client, gen_model, task, prev_draft=draft, critique=verdict)
        cost.add(gen_model, usage)
        if show_drafts:
            console.print(Panel(draft, title=f"draft v{rnd + 1}", border_style="dim"))
    else:
        # for-else: ran out of rounds without an accept.
        console.rule("[bold red]✗ Hit max_rounds without acceptance[/]")
        console.print(
            "[dim]The critic never accepted. Either the task is genuinely hard, the "
            "critic is too strict, or the generator can't improve further. Raise "
            "--max-rounds, soften CRITIC_SYSTEM, or use a stronger --critic-model.[/]"
        )

    console.rule("[bold green]Final answer[/]")
    console.print(Panel(draft, border_style="green"))
    cost.report()


# ===========================================================================
# Cost helper — totals across BOTH models (generator + critic may differ)
# ===========================================================================
class _Cost:
    def __init__(self):
        self.calls = 0
        self.by_model: dict[str, list[int]] = {}  # model -> [in, out]

    def add(self, model: str, usage) -> None:
        self.calls += 1
        slot = self.by_model.setdefault(model, [0, 0])
        slot[0] += usage.input_tokens
        slot[1] += usage.output_tokens

    def report(self) -> None:
        total = 0.0
        parts = []
        for model, (in_t, out_t) in self.by_model.items():
            in_p, out_p = PRICES.get(model, (0.0, 0.0))
            c = (in_t * in_p + out_t * out_p) / 1_000_000
            total += c
            parts.append(f"{model}: {in_t + out_t} tok ${c:.4f}")
        console.print(
            f"\n[bold]Cost:[/]  {self.calls} model call(s)  •  "
            + "  •  ".join(parts)
            + f"  •  [bold]total ${total:.4f}[/]"
        )


def main():
    parser = argparse.ArgumentParser(description="Self-critique (Reflexion) loop: generate → critique → revise.")
    parser.add_argument("task", nargs="+", help="What you want written/explained.")
    parser.add_argument("--max-rounds", type=int, default=3,
                        help="Max critique→revise cycles before giving up (default 3).")
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"),
                        help="Generator model.")
    parser.add_argument("--critic-model", default=None,
                        help="Critic model (default: same as generator). "
                             "Try a stronger model here to grade a weaker generator.")
    parser.add_argument("--show-drafts", action="store_true",
                        help="Print every intermediate draft, not just the final one.")
    args = parser.parse_args()

    task = " ".join(args.task)
    critic_model = args.critic_model or args.model
    run(task, args.model, critic_model, args.max_rounds, args.show_drafts)


if __name__ == "__main__":
    main()
