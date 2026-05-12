"""
Phase 3, Exercise 2 — A robust agent loop.

Takes Exercise 1's minimal loop and adds what production agents actually need:

1. MORE TOOLS — calculator, get_current_time, word_count. The model has
   to PICK which tool to call when. Tool selection is the real intelligence;
   running them is just plumbing.

2. A SYSTEM PROMPT — shape the agent's behavior. The same guardrail slot
   we used in Phase 2's RAG chatbot, now applied to an agent.

3. ERROR RECOVERY — try `calculator("10/0")` and watch the model:
   - see ERROR: ZeroDivisionError in the tool result
   - recognize the failure
   - explain the limitation to the user instead of crashing

4. COST TRACKING — agents make MANY model calls. Print per-iteration
   tokens + running dollar total so you can feel what loops cost.

5. CONVERSATION DUMP — `--trace` shows the full messages list at the end.
   This is the single best debugging tool for agents that go sideways.

6. UNKNOWN-TOOL GUARD — if the model hallucinates a tool name (it happens),
   return ERROR: unknown tool to the model instead of crashing on KeyError.

Run:
    uv run phase-3/02_agent_loop_robust.py "What's 2+2*3 and how many words in 'the quick brown fox'?"
    uv run phase-3/02_agent_loop_robust.py "What is 10 divided by 0?"        # error recovery
    uv run phase-3/02_agent_loop_robust.py "What time is it?"                # one tool
    uv run phase-3/02_agent_loop_robust.py "Hello!"                          # no tools needed
    uv run phase-3/02_agent_loop_robust.py "compute (2+3)*(4+5)" --trace     # see the conversation
"""
import argparse
import datetime
import json
import os
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(override=True)
console = Console()

# Per-1M-token base prices for cost tracking.
PRICES = {
    "claude-haiku-4-5":  (0.80,  4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7":   (15.00, 75.00),
}


# ===========================================================================
# 1. The real Python functions
# ===========================================================================
def calculator(expression: str) -> float:
    """Evaluate a math expression. Restricted to numbers and + - * / ( ).

    We sandbox by:
      a) whitelisting characters (no letters, no underscores, no quotes)
      b) calling eval() with empty globals so no built-ins are reachable
    Still don't trust this in production — use a real expression parser.
    """
    allowed = set("0123456789+-*/.() ")
    if not all(c in allowed for c in expression):
        raise ValueError(f"expression contains disallowed characters: {expression!r}")
    return eval(expression, {"__builtins__": {}}, {})


def get_current_time() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def word_count(text: str) -> int:
    """Count whitespace-separated tokens."""
    return len(text.split())


TOOLS_BY_NAME = {
    "calculator": calculator,
    "get_current_time": get_current_time,
    "word_count": word_count,
}


# ===========================================================================
# 2. Tool descriptions for the model
# ===========================================================================
# Take these descriptions seriously — they're the model's only documentation
# for when to use what. Vague descriptions cause the model to pick wrong tools
# (or call tools when prose would do).
TOOL_DEFINITIONS = [
    {
        "name": "calculator",
        "description": (
            "Evaluate an arithmetic expression and return the numeric result. "
            "Supports +, -, *, /, parentheses, and decimal numbers. "
            "Use this whenever the user asks for a calculation — do not compute mentally."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression, e.g. '2+2*3' or '(10-5)/2'",
                },
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_current_time",
        "description": (
            "Return the current UTC time in ISO 8601 format. Takes no arguments. "
            "Use this when the user asks about the current time or date."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "word_count",
        "description": (
            "Return the number of whitespace-separated words in a string. "
            "Use this when the user asks how many words are in some text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text whose words to count."},
            },
            "required": ["text"],
        },
    },
]


# ===========================================================================
# 3. System prompt — the agent's persona and rules
# ===========================================================================
SYSTEM_PROMPT = """You are a precise tool-using assistant.

Rules:
- Use a tool whenever it gives a more accurate answer than guessing.
- If a tool returns an ERROR, read it carefully. Try a different approach OR
  explain the limitation to the user. Never silently retry the same call.
- After getting tool results, synthesize them into a concise final answer.
- Don't call tools when prose suffices (e.g. greetings, simple facts you know)."""


# ===========================================================================
# 4. The agent loop — same skeleton as Exercise 1, more instrumentation
# ===========================================================================
def run_agent(question: str, model: str, max_iterations: int, trace: bool) -> None:
    client = Anthropic()
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]

    # Running tallies
    total_in_tokens = 0
    total_out_tokens = 0
    tools_called: list[str] = []

    for iteration in range(1, max_iterations + 1):
        console.rule(f"[bold cyan]Iteration {iteration}[/]")

        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Show what the model produced this turn
        for block in response.content:
            if block.type == "text":
                console.print(f"[green]💬 model:[/] {block.text}")
            elif block.type == "tool_use":
                console.print(f"[yellow]🔧 wants:[/] {block.name}({json.dumps(block.input)})")
                tools_called.append(block.name)

        # Per-iteration cost line
        in_t, out_t = response.usage.input_tokens, response.usage.output_tokens
        total_in_tokens += in_t
        total_out_tokens += out_t
        in_price, out_price = PRICES.get(model, (0.0, 0.0))
        iter_cost = (in_t * in_price + out_t * out_price) / 1_000_000
        running_cost = (total_in_tokens * in_price + total_out_tokens * out_price) / 1_000_000
        console.print(
            f"[dim]   tokens: in={in_t} out={out_t}  "
            f"iter ${iter_cost:.4f}  running ${running_cost:.4f}[/]"
        )

        # ---- Exit on end_turn ----
        if response.stop_reason == "end_turn":
            console.rule("[bold green]✓ Finished[/]")
            _print_summary(iteration, tools_called, total_in_tokens, total_out_tokens, model)
            if trace:
                _print_trace(messages)
            return

        # ---- Otherwise: append assistant, run tools, append results ----
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            fn = TOOLS_BY_NAME.get(block.name)
            if fn is None:
                # Model hallucinated a tool name — return error so it can recover
                content = f"ERROR: unknown tool {block.name!r}. Available: {list(TOOLS_BY_NAME)}"
                console.print(f"[red]⚠  unknown tool:[/] {block.name}")
            else:
                try:
                    result = fn(**block.input)
                    content = str(result)
                    console.print(f"[blue]⚙  → {result}[/]")
                except Exception as e:
                    # Round-trip the error to the model so it can recover
                    content = f"ERROR: {type(e).__name__}: {e}"
                    console.print(f"[red]⚠  failed:[/] {content}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            })
        messages.append({"role": "user", "content": tool_results})

    # ---- Fell through the for-loop → hit the cap ----
    console.rule(f"[bold red]✗ Hit max_iterations ({max_iterations})[/]")
    _print_summary(max_iterations, tools_called, total_in_tokens, total_out_tokens, model)
    if trace:
        _print_trace(messages)
    console.print(
        "[dim]Loop didn't terminate. Common causes: tool descriptions unclear, "
        "tools return ambiguous results, or the task genuinely needs more iters. "
        "Raise --max-iterations or improve the tools.[/]"
    )


# ===========================================================================
# Helpers
# ===========================================================================
def _print_summary(iters, tools_called, in_t, out_t, model):
    in_price, out_price = PRICES.get(model, (0.0, 0.0))
    cost = (in_t * in_price + out_t * out_price) / 1_000_000
    distinct = sorted(set(tools_called))
    console.print(
        f"\n[bold]Summary:[/]  {iters} iteration(s)  •  "
        f"{len(tools_called)} tool call(s) ({', '.join(distinct) or 'none'})  •  "
        f"{in_t + out_t} tokens  •  [bold]${cost:.4f}[/]"
    )


def _print_trace(messages):
    """Dump the entire messages list — what the model saw on its last turn."""
    console.rule("[dim]conversation trace[/]")
    for i, msg in enumerate(messages):
        content = msg["content"]
        if isinstance(content, str):
            console.print(f"  [bold]{i:2d}[/] [{msg['role']:9s}] {content[:120]}")
        else:
            # Content blocks (assistant tool_use, or tool_result list)
            for j, block in enumerate(content):
                # Anthropic SDK objects expose .type, .text, .name, etc.
                bt = getattr(block, "type", None) or block.get("type")
                if bt == "text":
                    txt = (getattr(block, "text", None) or block.get("text", ""))[:80]
                    console.print(f"  [bold]{i:2d}[/].{j} [{msg['role']:9s}] text: {txt}")
                elif bt == "tool_use":
                    name = getattr(block, "name", None) or block.get("name")
                    inp = getattr(block, "input", None) or block.get("input")
                    console.print(f"  [bold]{i:2d}[/].{j} [{msg['role']:9s}] tool_use: {name}({json.dumps(inp)})")
                elif bt == "tool_result":
                    tuid = (getattr(block, "tool_use_id", None) or block.get("tool_use_id", ""))[-8:]
                    out = str(getattr(block, "content", None) or block.get("content", ""))[:80]
                    console.print(f"  [bold]{i:2d}[/].{j} [{msg['role']:9s}] tool_result(...{tuid}): {out}")


# ===========================================================================
# CLI
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(description="Robust agent loop with multiple tools.")
    parser.add_argument("question", nargs="+", help="The question to answer")
    parser.add_argument("--max-iterations", type=int, default=10)
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"))
    parser.add_argument("--trace", action="store_true",
                        help="Dump the full messages list at the end (great for debugging)")
    args = parser.parse_args()

    question = " ".join(args.question)
    console.print(
        f"[bold]Question:[/] {question}\n"
        f"[dim]model={args.model}  max_iterations={args.max_iterations}[/]\n"
    )
    run_agent(question, args.model, args.max_iterations, args.trace)


if __name__ == "__main__":
    main()
