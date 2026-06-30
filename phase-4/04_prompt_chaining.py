"""
Phase 4, Exercise 04 — PROMPT CHAINING (the first Building Effective Agents pattern).

This is a *workflow*, not an agent. There is no while-loop and no tool use. A
chain is a FIXED sequence of LLM calls, decided by YOU in Python, where each
step's output feeds the next — with a programmatic GATE between steps.

    topic ──▶ ① draft blurb ──▶ ②  GATE  ──▶ ③ translate ──▶ done
                  (LLM)        (pure Python)     (LLM)
                                   │
                                   └─ fails ──▶ STOP (skip the paid step ③)

Why this is "plain anthropic", not the Claude Agent SDK
-------------------------------------------------------
The phase plan builds 04–08 on the raw API on purpose. These five patterns are
*orchestration logic* — `if`/`for`/function calls around `messages.create()`.
A framework would run that control flow for you and hide the very thing the
exercise teaches. The whole point of Building Effective Agents: "most things
people call an agent should have been a workflow," and a workflow is just code.

The one idea: the GATE is what makes this a chain
-------------------------------------------------
Calling the model twice in a row is not prompt chaining. The gate is the
difference. A gate is a cheap check BETWEEN steps that decides whether the chain
may continue. Here it is pure Python (no LLM) — which is itself a lesson: not
every step needs a model, and catching a bad draft with `len(text.split())`
costs nothing and saves you the price of step ③.

What the gate does NOT do here: loop its feedback back into step ① to make the
draft better. That generate→critique→retry loop is a different pattern —
evaluator-optimizer, Exercise 08. Here the gate's only job is to STOP a bad
draft from flowing downstream. Keeping the two separate is the point.

When to reach for prompt chaining (from the BEA article)
--------------------------------------------------------
When a task cleanly decomposes into fixed subtasks, and trading a little latency
(more sequential calls) for higher accuracy on each step is worth it. Classic
examples: outline → check outline → write doc; generate copy → verify → translate.
When NOT to: if one call does the job, chaining just adds cost and latency.

Run:
    uv run phase-4/04_prompt_chaining.py "a CLI tool that turns git history into a changelog"
    uv run phase-4/04_prompt_chaining.py "a budgeting app for freelancers" --lang Spanish
    uv run phase-4/04_prompt_chaining.py "a note-taking app" --max-words 10   # watch the GATE bite, step ③ skipped
"""
import argparse
import os

from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(override=True)
console = Console()

# Same price table as Phase 3 — we tally cost across EVERY call in the chain,
# because a chain's bill is the sum of its steps, not one request.
PRICES = {
    "claude-haiku-4-5":  (0.80,  4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-8":   (15.00, 75.00),
}

# Gate thresholds. Defaults chosen so a normal 2–3 sentence blurb passes; the
# CLI lets you tighten --max-words to force a failure and watch the chain stop.
MIN_WORDS = 12
MAX_WORDS = 60
# Marketing hype the gate rejects — a deterministic stand-in for a real
# brand-voice / compliance check. Cheap to run, impossible to argue with.
HYPE_WORDS = {
    "revolutionary", "game-changing", "game-changer", "cutting-edge",
    "world-class", "best-in-class", "next-generation", "disruptive",
    "synergy", "paradigm", "unparalleled", "groundbreaking",
}


# ===========================================================================
# A tiny call helper — every step in the chain goes through this so cost
# accumulates in one place. (Each call carries its own running total.)
# ===========================================================================
def call_model(client: Anthropic, model: str, system: str, user: str) -> tuple[str, float]:
    """One LLM call. Returns (text, cost_usd_for_this_call)."""
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    in_price, out_price = PRICES.get(model, (0.0, 0.0))
    cost = (resp.usage.input_tokens * in_price + resp.usage.output_tokens * out_price) / 1_000_000
    return text, cost


# ===========================================================================
# Step ① — draft. The first link: topic → short marketing blurb.
# ===========================================================================
def draft_blurb(client: Anthropic, model: str, topic: str) -> tuple[str, float]:
    system = (
        "You are a concise marketing copywriter. Write a punchy product blurb of "
        "2-3 sentences. Plain, concrete language — describe what it does and who "
        "it helps. No bullet points, no hype words, no exclamation-mark spam."
    )
    return call_model(client, model, system, f"Product idea: {topic}")


# ===========================================================================
# Step ② — the GATE. Pure Python, no LLM. Returns (passed, list_of_reasons).
# This is the load-bearing line of the whole exercise: a check BETWEEN steps
# that can abort the chain before the next paid call runs.
# ===========================================================================
def gate(blurb: str, min_words: int, max_words: int) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    n = len(blurb.split())
    if n < min_words:
        reasons.append(f"too short: {n} words (min {min_words})")
    if n > max_words:
        reasons.append(f"too long: {n} words (max {max_words})")

    # Why lowercase + strip punctuation: catch "Revolutionary," and "GAME-CHANGING"
    # too, not just the exact lowercase token.
    found = sorted({
        w for w in HYPE_WORDS
        if w in blurb.lower().replace(",", " ").replace(".", " ").replace("!", " ")
    })
    if found:
        reasons.append(f"contains hype words: {', '.join(found)}")

    return (not reasons), reasons


# ===========================================================================
# Step ③ — transform. Only runs if the gate passed.
# ===========================================================================
def translate(client: Anthropic, model: str, blurb: str, lang: str) -> tuple[str, float]:
    system = (
        f"You are a professional translator. Translate the user's marketing blurb "
        f"into {lang}. Preserve tone and meaning. Output ONLY the translation, "
        f"no preamble, no notes."
    )
    return call_model(client, model, system, blurb)


# ===========================================================================
# The chain itself — this function IS the pattern. Read it top to bottom and
# you can see the whole control flow: call, check, branch, call.
# ===========================================================================
def run_chain(topic: str, lang: str, model: str, min_words: int, max_words: int) -> None:
    client = Anthropic()
    total = 0.0

    # --- Step ① ----------------------------------------------------------
    console.rule("[bold cyan]① draft blurb[/]")
    blurb, c1 = draft_blurb(client, model, topic)
    total += c1
    console.print(blurb)
    console.print(f"[dim]   {len(blurb.split())} words • ${c1:.4f}[/]")

    # --- Step ② : the GATE ----------------------------------------------
    console.rule("[bold cyan]② gate (pure Python, no LLM)[/]")
    passed, reasons = gate(blurb, min_words, max_words)
    if not passed:
        # Fail-fast: the chain STOPS here. We never pay for step ③ on a bad
        # draft. This early-exit is exactly why the gate earns its place — it
        # protects the expensive downstream step.
        console.print("[bold red]✗ gate FAILED — chain stops here[/]")
        for r in reasons:
            console.print(f"[red]   • {r}[/]")
        console.print(f"\n[dim]Skipped step ③ (translation). Total ${total:.4f} — "
                      f"and step ③'s cost was never incurred.[/]")
        console.print("[dim]To self-correct instead of stopping, you'd loop this "
                      "feedback back into step ① — that's Exercise 08 (evaluator-optimizer).[/]")
        return
    console.print("[bold green]✓ gate PASSED[/] — draft is in range and hype-free")

    # --- Step ③ ----------------------------------------------------------
    console.rule(f"[bold cyan]③ translate → {lang}[/]")
    translated, c3 = translate(client, model, blurb, lang)
    total += c3
    console.print(translated)
    console.print(f"[dim]   ${c3:.4f}[/]")

    console.rule("[bold green]✓ chain complete[/]")
    console.print(f"[bold]2 LLM calls + 1 gate[/] • total [bold]${total:.4f}[/]  (model={model})")


def main():
    parser = argparse.ArgumentParser(
        description="Prompt chaining: draft → gate → translate (a workflow, not an agent)."
    )
    parser.add_argument("topic", nargs="+", help="The product idea to write a blurb for.")
    parser.add_argument("--lang", default="French", help="Target language for step ③ (default French).")
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"))
    parser.add_argument("--min-words", type=int, default=MIN_WORDS, help="Gate: minimum blurb length.")
    parser.add_argument("--max-words", type=int, default=MAX_WORDS,
                        help="Gate: maximum blurb length. Set low (e.g. 10) to force a gate failure.")
    args = parser.parse_args()

    topic = " ".join(args.topic)
    console.print(
        f"[bold]Topic:[/] {topic}\n"
        f"[dim]model={args.model}  lang={args.lang}  gate window={args.min_words}-{args.max_words} words[/]\n"
    )
    run_chain(topic, args.lang, args.model, args.min_words, args.max_words)


if __name__ == "__main__":
    main()
