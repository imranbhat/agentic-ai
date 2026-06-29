"""
Phase 4, Exercise 01 — Claude Agent SDK hello-world.

Phase 3 taught you that an agent is "an LLM call wrapped in a while loop" — and
you wrote that loop by hand five times. Phase 4 asks: now that you've FELT the
loop, what does a framework buy you? This is the first taste.

The whole file is one `query()` call. There is NO while loop here — and that's
the point. In Phase 1 you wrote `client.messages.create(...)` and read
`response.content` yourself. In Phase 3 you wrote the loop, appended tool
results, tracked tokens, summed cost. The Agent SDK hides all of that behind a
single async generator.

What's genuinely different from Phase 1-3
-----------------------------------------
1. It's ASYNC. Phases 1-3 were synchronous (`response = client.messages...`).
   The SDK is async-first: `async for message in query(...)`. You drive it with
   asyncio.run(). This is the first structural change a framework imposes on you.

2. It streams MESSAGES, not tokens or raw blocks. Each item from `query()` is a
   typed object: an `AssistantMessage` (whose `.content` is a list of `TextBlock`
   / `ToolUseBlock` / ...), then a final `ResultMessage`. You pattern-match on
   the type instead of poking at `response.content[0].text`.

3. Cost is computed FOR you. In Phase 3 you kept a PRICES table and multiplied
   tokens by hand every iteration. Here the `ResultMessage` arrives with
   `total_cost_usd`, `usage`, `num_turns`, and `duration_ms` already filled in.
   The framework did the bookkeeping.

The cost of all that: `pip install claude-agent-sdk` pulled in 17 packages
(~66 MiB) and the SDK shells out to a bundled Node-based Claude Code CLI under
the hood. Your Phase 3 agent was ~200 lines and `anthropic` + `httpx`. That
trade — convenience for weight — is exactly what Exercise 03 will measure.

Run:
    uv run phase-4/01_sdk_hello.py
    uv run phase-4/01_sdk_hello.py "Explain what an agent loop is in two sentences."
"""
import argparse
import asyncio
import os

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(override=True)
console = Console()

# Why Haiku: the house rule for this learning repo. Cheap, fast, plenty capable
# for a hello-world. Sonnet/Opus would be the upgrade once a task needs deeper
# reasoning — a one-word change to this string (the SDK takes a plain model id).
DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")


async def run(question: str, model: str) -> None:
    # ClaudeAgentOptions is the SDK's single config object — the rough equivalent
    # of the kwargs you passed to client.messages.create() (model, system), but
    # it ALSO carries the knobs a whole agent needs: allowed_tools, mcp_servers,
    # permission_mode, hooks, cwd. We use only the two simplest here. No tools,
    # so this is a pure one-shot reply — the SDK still runs its loop, it just
    # never needs a second turn.
    options = ClaudeAgentOptions(
        model=model,
        system_prompt="You are a concise teaching assistant. Answer in plain English.",
    )

    console.print(f"[bold]Question:[/] {question}")
    console.print(f"[dim]model={model}  (via Claude Agent SDK)[/]\n")

    # The loop you DON'T see: `query()` is an async generator. Internally the SDK
    # is doing model -> (tool? -> result ->)* -> done, exactly like your Phase 3
    # while loop. You just iterate the messages it yields. We pattern-match on
    # the typed message objects instead of indexing response.content.
    async for message in query(prompt=question, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    console.print(f"[green]💬 {block.text.strip()}[/]")

        elif isinstance(message, ResultMessage):
            # This is the payoff: the framework already tallied everything you
            # tracked by hand in Phase 3. No PRICES table, no token math.
            cost = message.total_cost_usd or 0.0
            console.rule("[bold green]✓ Done[/]")
            console.print(
                f"[dim]turns={message.num_turns}  "
                f"duration={message.duration_ms} ms  "
                f"cost=${cost:.4f}[/]"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Claude Agent SDK hello-world.")
    parser.add_argument(
        "question",
        nargs="*",
        default=["In two sentences, what is an AI agent?"],
        help="The question to ask (defaults to a question about agents).",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    question = " ".join(args.question) if args.question else "In two sentences, what is an AI agent?"
    # asyncio.run is the bridge from sync CLI land into the SDK's async world.
    asyncio.run(run(question, args.model))


if __name__ == "__main__":
    main()
