"""
Phase 4, Exercise 05 — ROUTING (the second Building Effective Agents pattern).

Still a *workflow*, still plain `anthropic` (no framework, no agent loop). Where
Exercise 04 ran steps in SEQUENCE, routing makes a BRANCH:

    input ──▶ classifier ──▶ ┌─ simple    → Haiku  handler (terse)
                 (LLM)       ├─ reasoning → Sonnet handler (thorough)
                             └─ refuse    → canned message (NO LLM, $0)

The crisp contrast with prompt chaining (Ex 04)
-----------------------------------------------
- Chaining: every step runs, in order. step① → step② → step③.
- Routing:  a classifier inspects the input and EXACTLY ONE handler runs.
A chain is "and then, and then." A router is "which one?"

The production payoff: cost/quality routing
-------------------------------------------
A single do-everything prompt forces ONE model on EVERY input — so you either
overpay (Sonnet on "capital of France?") or underperform (Haiku on a hard proof).
Routing breaks that bind: a CHEAP classifier (Haiku) decides, then you spend
expensively ONLY where it helps. You separate "what kind of question is this?"
from "answer it," and optimize each independently — including the model.

Two lessons that echo earlier exercises
---------------------------------------
1. The classifier uses FORCED TOOL USE (Phase 1's `tool_choice`) so the category
   comes back as reliable JSON — `{category, reason}` — never prose you parse.
2. The `refuse` route runs NO LLM at all — a canned string. Just like Ex 04's
   pure-Python gate: not every branch needs a model. Routing to a non-LLM path
   (a refusal, a cache hit, a human handoff) is a first-class option.

Note on models: the `reasoning` route defaults to **Sonnet** — a more expensive
*Claude*, not a drift to another provider. Spending more there is the whole
point of the pattern; the classifier and the simple route stay on cheap Haiku.

Run:
    uv run phase-4/05_routing.py "What is the capital of France?"                         # → simple  (Haiku)
    uv run phase-4/05_routing.py "Prove that the square root of 2 is irrational."          # → reasoning (Sonnet)
    uv run phase-4/05_routing.py "Which blood pressure medication should I take?"          # → refuse  (no LLM, $0)
"""
import argparse
import json
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
# Step ① — the CLASSIFIER. A cheap Haiku call that returns a category as
# reliable JSON via forced tool use (never prose we'd have to parse).
# ===========================================================================
CATEGORIES = {
    "simple":    "A factual or definitional question with a short, low-stakes answer.",
    "reasoning": "Needs multi-step reasoning, analysis, math, proof, code, or comparison.",
    "refuse":    "Personal medical, legal, or financial advice, or anything unsafe / out of scope.",
}

CLASSIFY_TOOL = {
    "name": "classify",
    "description": "Assign the user's question to exactly one category.",
    "input_schema": {
        "type": "object",
        "properties": {
            # enum constrains the model to our three labels — no surprise strings.
            "category": {"type": "string", "enum": list(CATEGORIES)},
            "reason": {"type": "string", "description": "One short clause: why this category."},
        },
        "required": ["category", "reason"],
    },
}


def classify(client: Anthropic, question: str, model: str) -> tuple[str, str, float]:
    """Return (category, reason, cost). Forced tool use => structured, not prose."""
    rubric = "\n".join(f"- {name}: {desc}" for name, desc in CATEGORIES.items())
    resp = client.messages.create(
        model=model,
        max_tokens=256,
        system=(
            "You are a routing classifier. Read the user's question and pick the one "
            "best category. Categories:\n" + rubric
        ),
        tools=[CLASSIFY_TOOL],
        # Why force the tool: guarantees the model calls `classify` instead of
        # chatting. The answer is structured JSON we can branch on directly.
        tool_choice={"type": "tool", "name": "classify"},
        messages=[{"role": "user", "content": question}],
    )
    tool_use = next(b for b in resp.content if b.type == "tool_use")
    cost = _cost(model, resp.usage.input_tokens, resp.usage.output_tokens)
    return tool_use.input["category"], tool_use.input["reason"], cost


# ===========================================================================
# Step ② — the HANDLERS. One specialized path per category. Each LLM route
# carries its OWN system prompt AND its own model. The `refuse` route is just
# Python — no model call.
# ===========================================================================
# (model, system_prompt) per LLM route. This table IS the cost/quality policy:
# the cheap model handles the easy bucket, the strong model the hard one.
ROUTES = {
    "simple": (
        "claude-haiku-4-5",
        "Answer in 1-2 sentences. Be direct and factual. No preamble.",
    ),
    "reasoning": (
        "claude-sonnet-4-6",
        "Think carefully and show your reasoning step by step, then give a clear "
        "final answer. Accuracy and rigor matter more than brevity.",
    ),
}

REFUSAL = (
    "I can't help with personal medical, legal, or financial decisions — that's "
    "outside what this assistant is for. Please consult a qualified professional."
)


def handle(client: Anthropic, category: str, question: str,
           model_override: dict) -> tuple[str, str, float]:
    """Dispatch to the chosen handler. Returns (answer, model_used, cost)."""
    if category == "refuse":
        # The short-circuit route: no LLM, no cost. Mirrors Ex 04's pure-Python
        # gate — routing to a non-LLM path is a first-class outcome.
        return REFUSAL, "(none — canned refusal)", 0.0

    default_model, system = ROUTES[category]
    model = model_override.get(category, default_model)
    resp = client.messages.create(
        model=model, max_tokens=1024, system=system,
        messages=[{"role": "user", "content": question}],
    )
    answer = "".join(b.text for b in resp.content if b.type == "text").strip()
    return answer, model, _cost(model, resp.usage.input_tokens, resp.usage.output_tokens)


# ===========================================================================
# The router itself — classify, then branch. Read top to bottom: this is the
# whole pattern (one classifier call + a dispatch).
# ===========================================================================
def run_router(question: str, classifier_model: str, model_override: dict) -> None:
    client = Anthropic()

    # --- Step ① : classify (cheap) --------------------------------------
    console.rule("[bold cyan]① classify[/]")
    category, reason, c_cost = classify(client, question, classifier_model)
    console.print(f"[bold]→ {category}[/]  [dim]({reason})[/]")
    console.print(f"[dim]   classifier={classifier_model} • ${c_cost:.4f}[/]")

    # --- Step ② : branch to exactly one handler -------------------------
    console.rule(f"[bold cyan]② handle as '{category}'[/]")
    answer, model_used, h_cost = handle(client, category, question, model_override)
    console.print(answer)

    total = c_cost + h_cost
    console.rule("[bold green]✓ done[/]")
    console.print(
        f"[bold]route:[/] {category}  •  [bold]handler model:[/] {model_used}  •  "
        f"classifier ${c_cost:.4f} + handler ${h_cost:.4f} = [bold]${total:.4f}[/]"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Routing: a classifier dispatches input to a specialized handler (a workflow)."
    )
    parser.add_argument("question", nargs="+", help="The question to route.")
    parser.add_argument("--classifier-model", default="claude-haiku-4-5",
                        help="Model for the cheap classification step (default Haiku).")
    parser.add_argument("--simple-model", default=None, help="Override the 'simple' route's model.")
    parser.add_argument("--reasoning-model", default=None, help="Override the 'reasoning' route's model.")
    args = parser.parse_args()

    # Only put a key in the override dict if the user actually passed one.
    override = {k: v for k, v in
                {"simple": args.simple_model, "reasoning": args.reasoning_model}.items() if v}

    question = " ".join(args.question)
    console.print(
        f"[bold]Question:[/] {question}\n"
        f"[dim]classifier={args.classifier_model}  routes: simple→Haiku, reasoning→Sonnet, refuse→(none)[/]\n"
    )
    run_router(question, args.classifier_model, override)


if __name__ == "__main__":
    main()
