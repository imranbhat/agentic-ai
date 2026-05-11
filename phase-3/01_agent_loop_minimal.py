"""
Phase 3, Exercise 1 — The minimal agent loop.

An agent is a `while` loop wrapped around `client.messages.create`:

    while True:
        response = model.create(messages=conversation, tools=...)
        if response.stop_reason == "end_turn":
            break                            # model is done, exit
        # otherwise stop_reason was "tool_use"
        run each requested tool, append results to conversation
        # next iteration sees the results and decides what to do next

That's it. The whole "what is an agent?" mystery is six lines of control flow.

To see this clearly, we define two trivial tools (add, multiply) and ask
a question that requires CHAINING them. The model will:
    iter 1 → call add(3,5) and add(7,2)
    iter 2 → see both results, call multiply(8,9)
    iter 3 → see the result, reply with text → end_turn

Run:
    uv run phase-3/01_agent_loop_minimal.py
    uv run phase-3/01_agent_loop_minimal.py "What is 17 squared minus 9?"
"""
import json
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(override=True)  # .env beats empty shell vars (Phase 1 gotcha #4)
console = Console()


# ===========================================================================
# 1. The actual Python functions — the things our agent can "do"
# ===========================================================================
def add(a: float, b: float) -> float:
    return a + b


def multiply(a: float, b: float) -> float:
    return a * b


# Lookup table: tool name (as the model knows it) → Python callable.
# When the model says "call multiply", we look it up here.
TOOLS_BY_NAME = {
    "add": add,
    "multiply": multiply,
}


# ===========================================================================
# 2. The tool DESCRIPTIONS the model sees — JSON schemas + plain English
# ===========================================================================
# Treat the description like a docstring for a colleague who's never seen
# your codebase. The model reads these to decide WHICH tool to call WHEN.
# Vague descriptions → wrong tool calls. The description is the API contract.
TOOL_DEFINITIONS = [
    {
        "name": "add",
        "description": "Add two numbers and return their sum.",
        "input_schema": {
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
    },
    {
        "name": "multiply",
        "description": "Multiply two numbers and return their product.",
        "input_schema": {
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
    },
]


# ===========================================================================
# 3. The agent loop
# ===========================================================================
def run_agent(question: str, max_iterations: int = 10) -> None:
    client = Anthropic()
    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

    # Conversation history. The model sees this entire list every iteration.
    # That's how it "remembers" what it's already done. There is no other
    # memory — agents are stateless apart from this growing list.
    messages: list[dict] = [{"role": "user", "content": question}]

    for iteration in range(1, max_iterations + 1):
        console.rule(f"[bold cyan]Iteration {iteration}[/]")

        # ----- The single model call that powers the agent -----
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Show what the model produced this turn (text + any tool_use blocks)
        for block in response.content:
            if block.type == "text":
                console.print(f"[green]💬 model says:[/] {block.text}")
            elif block.type == "tool_use":
                args = json.dumps(block.input)
                console.print(f"[yellow]🔧 wants to call:[/] {block.name}({args})")

        # ----- Exit condition: model is done -----
        if response.stop_reason == "end_turn":
            console.print(f"\n[bold green]✓ Agent finished after {iteration} iteration(s).[/]")
            return

        # ----- Otherwise stop_reason MUST be 'tool_use' — run the tools -----
        # Step A: append the assistant's message (with its tool_use blocks) to history.
        # This is REQUIRED — the API needs to see the request before the result.
        messages.append({"role": "assistant", "content": response.content})

        # Step B: execute each tool the model asked for, collect results.
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            fn = TOOLS_BY_NAME[block.name]
            try:
                result = fn(**block.input)
                content = str(result)
                console.print(f"[blue]⚙  ran {block.name}({json.dumps(block.input)}) →[/] {result}")
            except Exception as e:
                # Critical: send errors BACK to the model. It can recover from
                # a bad call if it sees the error; it can't recover from silence.
                content = f"ERROR: {type(e).__name__}: {e}"
                console.print(f"[red]⚠  {block.name} failed:[/] {e}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,    # ties result to the specific call
                "content": content,
            })

        # Step C: append all tool results as a single user message.
        # Note: tool results are 'user' role even though no human is involved —
        # that's just the API's protocol convention.
        messages.append({"role": "user", "content": tool_results})

    # If we fell out of the for-loop without returning, we hit the cap.
    # Agents that don't terminate are the #1 production bug. Always cap.
    console.print(f"\n[bold red]✗ Hit max_iterations ({max_iterations}) — aborting.[/]")
    console.print("[dim]The model kept asking for tools. Likely a loop or bad tool design.[/]")


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "What is (3 + 5) multiplied by (7 + 2)?"
    console.print(f"[bold]Question:[/] {question}\n")
    run_agent(question)
