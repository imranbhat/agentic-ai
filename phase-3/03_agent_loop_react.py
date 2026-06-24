"""
Phase 3, Exercise 3 — ReAct (Reason + Act).

Same loop as Exercise 2. Same three tools. The change is the SYSTEM PROMPT:
the model is required to emit a "Thought:" before every action and before
its final answer. The reasoning becomes printable.

Why this matters
----------------
Exercises 1 and 2 treat the model as a black box: you see what it CALLED,
not WHY. With ReAct, the model narrates its own reasoning into the text
channel before it acts. You get a trail you can read, audit, and debug:

    Thought: I need two values — first the sum, then the word count.
    Action: calculator(expression="2+2*3")
    Observation: 8
    Thought: Now I count words in the phrase.
    Action: word_count(text="the quick brown fox")
    Observation: 4
    Thought: I have both. I can answer.
    Answer: 2+2*3 = 8, and the phrase has 4 words.

The LOOP is unchanged. The PROMPT and DISPLAY are what's different.
That's the lesson — most agent patterns are prompt-level, not architectural.
You can stack ReAct on top of any loop. You don't need a new framework.

ReAct comes from Yao et al. 2022 (https://arxiv.org/abs/2210.03629) —
the ancestor of modern tool-using agents.

Run:
    uv run phase-3/03_agent_loop_react.py "What's 2+2*3 and how many words in 'the quick brown fox'?"
    uv run phase-3/03_agent_loop_react.py "What time is it, and how many words are in that ISO string?"
    uv run phase-3/03_agent_loop_react.py "What is 10 divided by 0?"   # watch the thought after the ERROR
    uv run phase-3/03_agent_loop_react.py "Hello!"                      # zero-tool case — still a Thought, then Answer
"""
import argparse
import datetime
import json
import os
import re
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(override=True)
console = Console()

PRICES = {
    "claude-haiku-4-5":  (0.80,  4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7":   (15.00, 75.00),
}


# ===========================================================================
# 1. Tools — unchanged from Exercise 2
# ===========================================================================
def calculator(expression: str) -> float:
    allowed = set("0123456789+-*/.() ")
    if not all(c in allowed for c in expression):
        raise ValueError(f"expression contains disallowed characters: {expression!r}")
    return eval(expression, {"__builtins__": {}}, {})


def get_current_time() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def word_count(text: str) -> int:
    return len(text.split())


TOOLS_BY_NAME = {
    "calculator": calculator,
    "get_current_time": get_current_time,
    "word_count": word_count,
}

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
# 2. THE CHANGE — system prompt now enforces ReAct format
# ===========================================================================
# Why: text-before-tool_use is the natural channel for "Thought." The model
# already emits text occasionally between turns; we just require it, and we
# require it to start with "Thought:" so the trace is parseable by eye.
SYSTEM_PROMPT = """You are a precise tool-using assistant that reasons step-by-step using the ReAct pattern.

Every turn you take MUST follow this format:

  1. Emit a single short "Thought:" line stating what you intend to do next and why.
  2. EITHER call exactly one tool (the Action) OR, if no more tools are needed,
     deliver the final answer prefixed with "Answer:".

After a tool returns, your next Thought should reference the Observation —
e.g. "The calculator returned 8, so now I need..." If a tool returns an
ERROR, your Thought must acknowledge it and pick a different approach (or
explain the limitation in your final Answer).

Rules:
- Never call a tool without a preceding Thought.
- Never deliver a final answer without a preceding Thought.
- Keep each Thought to one sentence. Reasoning, not narration.
- Don't call tools when prose suffices (greetings, simple facts you know) —
  but you must STILL emit a Thought explaining that choice before answering."""


# ===========================================================================
# 3. The loop — structurally identical to Exercise 2; only labels change
# ===========================================================================
def run_agent(question: str, model: str, max_iterations: int, trace: bool) -> None:
    client = Anthropic()
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]

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

        # ---- The display change: relabel text/tool_use as Thought/Action ----
        # The model emits its OWN "Thought:" / "Answer:" markers because the
        # system prompt requires them. We split on those markers and add the
        # visual styling — but we don't double-label. Splitting also handles
        # the case where the final turn contains BOTH a Thought and an Answer
        # in a single text block.
        is_final = response.stop_reason == "end_turn"
        for block in response.content:
            if block.type == "text":
                _render_react_text(block.text, default_is_answer=is_final)
            elif block.type == "tool_use":
                console.print(
                    f"[yellow]🎯 Action:[/] {block.name}({json.dumps(block.input)})"
                )
                tools_called.append(block.name)

        # Per-iteration cost line — unchanged
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

        if is_final:
            console.rule("[bold green]✓ Finished[/]")
            _print_summary(iteration, tools_called, total_in_tokens, total_out_tokens, model)
            if trace:
                _print_trace(messages)
            return

        # ---- Tool execution → results become Observations ----
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            fn = TOOLS_BY_NAME.get(block.name)
            if fn is None:
                content = f"ERROR: unknown tool {block.name!r}. Available: {list(TOOLS_BY_NAME)}"
                console.print(f"[red]👁  Observation:[/] {content}")
            else:
                try:
                    result = fn(**block.input)
                    content = str(result)
                    console.print(f"[blue]👁  Observation:[/] {result}")
                except Exception as e:
                    content = f"ERROR: {type(e).__name__}: {e}"
                    console.print(f"[red]👁  Observation:[/] {content}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            })
        messages.append({"role": "user", "content": tool_results})

    console.rule(f"[bold red]✗ Hit max_iterations ({max_iterations})[/]")
    _print_summary(max_iterations, tools_called, total_in_tokens, total_out_tokens, model)
    if trace:
        _print_trace(messages)
    console.print(
        "[dim]Loop didn't terminate. With ReAct the trace above usually tells you why — "
        "look for repeated Thoughts that don't advance, or Observations the model ignored.[/]"
    )


# ===========================================================================
# Helpers
# ===========================================================================
# Split a text block on the model's own ReAct markers and render each part.
# The system prompt requires "Thought:" before every action and "Answer:"
# before the final reply. Sometimes both appear in the same text block (final
# turn). Splitting lets us label each part visually without double-prefixing.
_MARKER_RE = re.compile(r"^(Thought|Answer):\s*", re.IGNORECASE | re.MULTILINE)


def _render_react_text(text: str, default_is_answer: bool) -> None:
    parts = _MARKER_RE.split(text)
    # re.split returns ['', 'Thought', '...', 'Answer', '...'] when leading
    # marker present; or ['leading text', 'Thought', '...', ...] if not.
    if len(parts) == 1:
        # No marker at all — model didn't follow the format. Show as-is.
        label = "💡 Answer" if default_is_answer else "💭 Thought"
        color = "bold green" if default_is_answer else "magenta"
        console.print(f"[{color}]{label}:[/] {text.strip()}")
        return
    # Pairs of (marker, body) after any leading non-marker text.
    leading, *rest = parts
    if leading.strip():
        console.print(f"[dim]{leading.strip()}[/]")
    for i in range(0, len(rest), 2):
        marker = rest[i].capitalize()
        body = rest[i + 1].strip() if i + 1 < len(rest) else ""
        if marker.lower() == "answer":
            console.print(f"[bold green]💡 Answer:[/] {body}")
        else:
            console.print(f"[magenta]💭 Thought:[/] {body}")


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
    console.rule("[dim]conversation trace[/]")
    for i, msg in enumerate(messages):
        content = msg["content"]
        if isinstance(content, str):
            console.print(f"  [bold]{i:2d}[/] [{msg['role']:9s}] {content[:120]}")
        else:
            for j, block in enumerate(content):
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


def main():
    parser = argparse.ArgumentParser(description="ReAct agent loop — Thought/Action/Observation made explicit.")
    parser.add_argument("question", nargs="+", help="The question to answer")
    parser.add_argument("--max-iterations", type=int, default=10)
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"))
    parser.add_argument("--trace", action="store_true",
                        help="Dump the full messages list at the end")
    args = parser.parse_args()

    question = " ".join(args.question)
    console.print(
        f"[bold]Question:[/] {question}\n"
        f"[dim]model={args.model}  max_iterations={args.max_iterations}[/]\n"
    )
    run_agent(question, args.model, args.max_iterations, args.trace)


if __name__ == "__main__":
    main()
