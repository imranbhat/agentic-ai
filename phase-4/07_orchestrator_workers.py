"""
Phase 4, Exercise 07 — ORCHESTRATOR-WORKERS (the fourth Building Effective Agents pattern).

A central ORCHESTRATOR LLM looks at a task, DYNAMICALLY decides how to break it
into subtasks, dispatches each to a WORKER call (in parallel — this builds on
Ex 06), then a SYNTHESIZER combines the results into one output.

    topic ─▶ ORCHESTRATOR ─▶ plan = [sub₁, sub₂, sub₃, …]   (the model invents these)
                                │
                   ┌───────────┼───────────┐
                   ▼           ▼           ▼
                worker₁     worker₂     worker₃     (run at once, asyncio.gather)
                   │           │           │
                   └───────────┼───────────┘
                               ▼
                         SYNTHESIZER ─▶ final briefing

The ONE thing that separates this from Ex 06 (sectioning)
---------------------------------------------------------
In Ex 06 the subtasks were FIXED IN YOUR CODE — `headline, features, tagline`,
the same three every run. Here the subtasks are **decided by the model at
runtime**: ask for a briefing on "remote work" and it plans different sections
than for "the James Webb telescope." That dynamic decomposition is the whole
pattern. You own the *shape* (plan → work → synthesize); the model fills in
*what* the work actually is.

"Is this still a workflow, or an agent?" — the key question this raises
----------------------------------------------------------------------
It's still a WORKFLOW. The control flow is fixed and you wrote it: exactly one
plan call, then one parallel batch of workers, then exactly one synthesis —
no loop, no "do I need more?" decision. The model chooses the CONTENT of the
steps (which subtasks), not the STRUCTURE (how many phases, whether to repeat).
The moment you let the orchestrator loop — "look at the draft, decide if it
needs another round of workers, repeat until satisfied" — the MODEL owns the
control flow and you've crossed into an AGENT (Phase 3's while-loop). This
exercise deliberately stops just short of that line.

Builds on Ex 06: the workers are a parallel fan-out (`asyncio.gather`). The new
part is that a model call PRODUCED the list being fanned out.

Run:
    uv run phase-4/07_orchestrator_workers.py "the impact of remote work on companies"
    uv run phase-4/07_orchestrator_workers.py "how the James Webb Space Telescope sees the early universe"
    uv run phase-4/07_orchestrator_workers.py "a topic" --synth-model claude-sonnet-4-6   # stronger editor at the join
"""
import argparse
import asyncio
import os

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
# ① ORCHESTRATOR — one model call that PLANS the subtasks. Forced tool use so
# the plan comes back as structured data we can fan out over, not prose.
# ===========================================================================
PLAN_TOOL = {
    "name": "submit_plan",
    "description": "Submit the list of subtopics that together cover the briefing.",
    "input_schema": {
        "type": "object",
        "properties": {
            "subtasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Short section title."},
                        "focus": {"type": "string", "description": "One clause: what this section should cover."},
                    },
                    "required": ["title", "focus"],
                },
            },
        },
        "required": ["subtasks"],
    },
}


async def orchestrate(client: AsyncAnthropic, topic: str, model: str) -> tuple[list[dict], float]:
    resp = await client.messages.create(
        model=model, max_tokens=512,
        system=(
            "You are a planning orchestrator. Given a topic, break it into 3-4 focused, "
            "NON-OVERLAPPING subtopics that together make a complete, balanced briefing. "
            "Choose subtopics that genuinely fit THIS topic — do not use a generic template."
        ),
        tools=[PLAN_TOOL],
        tool_choice={"type": "tool", "name": "submit_plan"},
        messages=[{"role": "user", "content": f"Topic: {topic}"}],
    )
    tool_use = next(b for b in resp.content if b.type == "tool_use")
    return tool_use.input["subtasks"], _cost(model, resp.usage.input_tokens, resp.usage.output_tokens)


# ===========================================================================
# ② WORKER — one model call per subtask, all run concurrently (Ex 06 fan-out).
# ===========================================================================
async def worker(client: AsyncAnthropic, topic: str, sub: dict, model: str) -> tuple[str, float]:
    resp = await client.messages.create(
        model=model, max_tokens=300,
        system=(
            "You are a briefing writer. Write a tight 2-3 sentence section on the given "
            "subtopic, in the context of the larger topic. Concrete and factual, no fluff. "
            "Output only the section body — no heading."
        ),
        messages=[{"role": "user",
                   "content": f"Larger topic: {topic}\nThis section — {sub['title']}: {sub['focus']}"}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text, _cost(model, resp.usage.input_tokens, resp.usage.output_tokens)


# ===========================================================================
# ③ SYNTHESIZER — one model call that stitches the worker outputs into a
# coherent whole. A natural place to spend more (Sonnet): quality matters most
# at the JOIN, where redundancy and rough transitions show up. Hence --synth-model.
# ===========================================================================
async def synthesize(client: AsyncAnthropic, topic: str, sections: list[tuple[str, str]],
                     model: str) -> tuple[str, float]:
    body = "\n\n".join(f"## {title}\n{text}" for title, text in sections)
    resp = await client.messages.create(
        model=model, max_tokens=1024,
        system=(
            "You are an editor. Combine the drafted sections into one coherent briefing: a "
            "one-sentence intro, the sections under their ## headings (lightly smoothed), and "
            "a one-sentence takeaway at the end. Remove redundancy across sections; keep it tight."
        ),
        messages=[{"role": "user", "content": f"Topic: {topic}\n\nDrafted sections:\n\n{body}"}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text, _cost(model, resp.usage.input_tokens, resp.usage.output_tokens)


# ===========================================================================
# The workflow: plan → workers (parallel) → synthesize. You wrote this shape;
# the orchestrator only fills in the subtasks. Read it top to bottom.
# ===========================================================================
async def run(topic: str, model: str, synth_model: str) -> None:
    client = AsyncAnthropic()
    total = 0.0

    # --- ① plan ----------------------------------------------------------
    console.rule("[bold cyan]① orchestrator plans the subtasks (dynamic — depends on the topic)[/]")
    subtasks, c_plan = await orchestrate(client, topic, model)
    total += c_plan
    for i, sub in enumerate(subtasks, 1):
        console.print(f"  [bold]{i}. {sub['title']}[/] — [dim]{sub['focus']}[/]")
    console.print(f"[dim]   planner={model} • {len(subtasks)} subtasks • ${c_plan:.4f}[/]")

    # --- ② workers (parallel) -------------------------------------------
    console.rule(f"[bold cyan]② {len(subtasks)} workers write their sections in parallel[/]")
    results = await asyncio.gather(*[worker(client, topic, sub, model) for sub in subtasks])
    sections = [(sub["title"], text) for sub, (text, _) in zip(subtasks, results)]
    c_workers = sum(c for _, c in results)
    total += c_workers
    for title, text in sections:
        console.print(f"\n[bold]## {title}[/]\n{text}")
    console.print(f"\n[dim]   {len(subtasks)} workers • ${c_workers:.4f}[/]")

    # --- ③ synthesize ---------------------------------------------------
    console.rule(f"[bold cyan]③ synthesizer combines them (model={synth_model})[/]")
    final, c_synth = await synthesize(client, topic, sections, synth_model)
    total += c_synth
    console.print(final)

    console.rule("[bold green]✓ done[/]")
    console.print(
        f"[bold]{len(subtasks) + 2} model calls[/] (1 plan + {len(subtasks)} workers + 1 synth)  •  "
        f"plan ${c_plan:.4f} + workers ${c_workers:.4f} + synth ${c_synth:.4f} = [bold]${total:.4f}[/]"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Orchestrator-workers: a model plans subtasks, workers do them in parallel, a synthesizer combines."
    )
    parser.add_argument("topic", nargs="+", help="The briefing topic.")
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"),
                        help="Model for the orchestrator and workers (default Haiku).")
    parser.add_argument("--synth-model", default=None,
                        help="Override the synthesizer's model (e.g. claude-sonnet-4-6 for a stronger edit).")
    args = parser.parse_args()

    topic = " ".join(args.topic)
    synth_model = args.synth_model or args.model
    console.print(f"[bold]Topic:[/] {topic}\n[dim]model={args.model}  synth={synth_model}[/]\n")
    asyncio.run(run(topic, args.model, synth_model))


if __name__ == "__main__":
    main()
