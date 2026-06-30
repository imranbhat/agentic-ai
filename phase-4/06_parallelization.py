"""
Phase 4, Exercise 06 — PARALLELIZATION (the third Building Effective Agents pattern).

The first pattern that is NOT sequential. Chaining (04) and routing (05) ran one
call at a time. Parallelization fans out MULTIPLE calls at once, then aggregates.
Still a workflow, still plain `anthropic` — but now async (`asyncio.gather`).

Two flavors, both in this file (pick with --mode):

  vote     ── same prompt, run N times in parallel, then MAJORITY-aggregate.
              Buys RELIABILITY: one call is a coin-flip on a borderline input;
              N independent votes + majority cuts the variance.

                 input ─┬─▶ classify ─┐
                        ├─▶ classify ─┤
                        ├─▶ classify ─┼─▶ tally → majority label
                        ├─▶ classify ─┤
                        └─▶ classify ─┘   (all 5 at once)

  section  ── split a task into INDEPENDENT subtasks, run them at once, stitch.
              Buys LATENCY: the subtasks have no data dependency, so running
              them in series just wastes wall-clock.

                 topic ─┬─▶ headline ─┐
                        ├─▶ bullets  ─┼─▶ stitch into one blurb
                        └─▶ tagline  ─┘   (all 3 at once)

What parallelization changes — and what it does NOT
---------------------------------------------------
It changes LATENCY: N concurrent calls finish in roughly ONE call's wall-clock,
not N×. (For voting it also buys reliability.) It does NOT reduce cost: you make
N calls, so you pay N× the tokens of a single call, every time. Prove it yourself
with --sequential: the SAME N calls run one-after-another — identical token cost,
but the wall-clock balloons. Latency is the only thing the `gather` removed.

Why async here (and not in 04/05): concurrency needs it. `asyncio.gather` runs
many `await`ed calls on one thread while each waits on the network. We use
`AsyncAnthropic` so the calls actually overlap instead of blocking each other.

Run:
    uv run phase-4/06_parallelization.py "The cinematography was stunning but the plot dragged and I nearly left. I'd still maybe watch the sequel."
    uv run phase-4/06_parallelization.py "...same review..." --sequential   # same cost, watch wall-clock balloon
    uv run phase-4/06_parallelization.py "a password manager for families" --mode section
    uv run phase-4/06_parallelization.py "...review..." -n 7                 # more votes = steadier, pricier
"""
import argparse
import asyncio
import os
import time
from collections import Counter

from anthropic import AsyncAnthropic
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
# A small async runner: takes a list of coroutine FACTORIES (callables that
# return a fresh coroutine) and runs them either concurrently or in series.
# Same calls, same cost — only the wall-clock differs. That contrast IS the
# lesson, so it lives in one switchable place.
# ===========================================================================
async def run_calls(factories: list, sequential: bool) -> list:
    if sequential:
        # One after another: each await blocks until its call returns.
        return [await make() for make in factories]
    # All at once: gather schedules them together; total time ≈ the slowest one.
    return await asyncio.gather(*[make() for make in factories])


# ===========================================================================
# MODE: vote — same prompt N times, majority wins.
# ===========================================================================
VOTE_TOOL = {
    "name": "submit_label",
    "description": "Submit the sentiment label for the review.",
    "input_schema": {
        "type": "object",
        # Binary on purpose: forcing a side is what makes a borderline review
        # split the vote, which is exactly the variance we want to see.
        "properties": {"label": {"type": "string", "enum": ["positive", "negative"]}},
        "required": ["label"],
    },
}


async def classify_once(client: AsyncAnthropic, review: str, model: str) -> tuple[str, float]:
    """One sentiment vote. Forced tool use => a clean label, not prose."""
    resp = await client.messages.create(
        model=model, max_tokens=64,
        system="Classify the review's overall sentiment as positive or negative. Pick the stronger side.",
        tools=[VOTE_TOOL],
        tool_choice={"type": "tool", "name": "submit_label"},
        messages=[{"role": "user", "content": review}],
    )
    tool_use = next(b for b in resp.content if b.type == "tool_use")
    return tool_use.input["label"], _cost(model, resp.usage.input_tokens, resp.usage.output_tokens)


async def vote_mode(review: str, n: int, model: str, sequential: bool) -> None:
    client = AsyncAnthropic()
    console.rule(f"[bold cyan]vote — {n} parallel classifications[/]" if not sequential
                 else f"[bold cyan]vote — {n} SEQUENTIAL classifications[/]")

    t0 = time.perf_counter()
    results = await run_calls([lambda: classify_once(client, review, model)] * n, sequential)
    elapsed = time.perf_counter() - t0

    labels = [label for label, _ in results]
    total_cost = sum(c for _, c in results)
    tally = Counter(labels)
    winner, count = tally.most_common(1)[0]

    # Show the distribution — the split is the whole point. A single call would
    # have returned ONE of these at random; the majority is steadier than any one.
    console.print("votes: " + "  ".join(f"[bold]{lbl}[/]×{tally[lbl]}" for lbl in tally))
    console.print(f"[bold green]→ majority: {winner}[/]  ({count}/{n})  "
                  f"[dim]confidence {count/n:.0%}[/]")
    console.rule("[bold]cost & time[/]")
    console.print(
        f"{n} calls • [bold]${total_cost:.4f}[/] ({'sequential' if sequential else 'parallel'}) • "
        f"wall-clock [bold]{elapsed:.2f}s[/]\n"
        f"[dim]Cost is N× one call either way. Run the other mode (--sequential) to see "
        f"the SAME cost with a very different wall-clock.[/]"
    )


# ===========================================================================
# MODE: section — independent subtasks, run at once, stitched together.
# ===========================================================================
async def write_section(client: AsyncAnthropic, instruction: str, topic: str,
                        model: str) -> tuple[str, float]:
    resp = await client.messages.create(
        model=model, max_tokens=256,
        system=instruction + " Output only the requested text, no preamble.",
        messages=[{"role": "user", "content": f"Product: {topic}"}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text, _cost(model, resp.usage.input_tokens, resp.usage.output_tokens)


SECTIONS = [
    ("Headline", "Write one punchy headline, 6 words max."),
    ("Features", "Write exactly 3 short feature bullets, each one line."),
    ("Tagline",  "Write one memorable tagline, under 10 words."),
]


async def section_mode(topic: str, model: str, sequential: bool) -> None:
    client = AsyncAnthropic()
    console.rule(f"[bold cyan]section — {len(SECTIONS)} independent subtasks "
                 f"{'in SERIES' if sequential else 'in parallel'}[/]")

    t0 = time.perf_counter()
    # Each subtask is a DIFFERENT prompt — distinct factories, not the same one ×N.
    factories = [lambda i=i: write_section(client, SECTIONS[i][1], topic, model)
                 for i in range(len(SECTIONS))]
    results = await run_calls(factories, sequential)
    elapsed = time.perf_counter() - t0

    total_cost = 0.0
    for (name, _), (text, cost) in zip(SECTIONS, results):
        total_cost += cost
        console.print(f"\n[bold]## {name}[/]\n{text}")

    console.rule("[bold]cost & time[/]")
    console.print(
        f"{len(SECTIONS)} subtasks • [bold]${total_cost:.4f}[/] "
        f"({'sequential' if sequential else 'parallel'}) • wall-clock [bold]{elapsed:.2f}s[/]\n"
        f"[dim]Independent subtasks → no reason to serialize. Parallel finishes in ≈ "
        f"one subtask's time; --sequential pays the same but waits for the sum.[/]"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Parallelization: fan out concurrent LLM calls, then aggregate (a workflow)."
    )
    parser.add_argument("text", nargs="+", help="Review (vote mode) or product topic (section mode).")
    parser.add_argument("--mode", choices=["vote", "section"], default="vote")
    parser.add_argument("-n", "--num", type=int, default=5, help="Votes to cast (vote mode; default 5).")
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"))
    parser.add_argument("--sequential", action="store_true",
                        help="Run the same calls one-by-one. Same cost; watch wall-clock balloon.")
    args = parser.parse_args()

    text = " ".join(args.text)
    console.print(f"[bold]{'Review' if args.mode == 'vote' else 'Topic'}:[/] {text}\n"
                  f"[dim]mode={args.mode}  model={args.model}"
                  f"{f'  n={args.num}' if args.mode == 'vote' else ''}"
                  f"  {'sequential' if args.sequential else 'parallel'}[/]\n")

    if args.mode == "vote":
        asyncio.run(vote_mode(text, args.num, args.model, args.sequential))
    else:
        asyncio.run(section_mode(text, args.model, args.sequential))


if __name__ == "__main__":
    main()
