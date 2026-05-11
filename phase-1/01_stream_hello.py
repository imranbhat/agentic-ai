"""
Phase 1, Exercise 1 — A streamed Claude API call.

Goal: feel what an LLM call actually is. A POST to an HTTP endpoint that
streams tokens back. No magic. No agents yet.

Run:
    uv run phase-1/01_stream_hello.py
    uv run phase-1/01_stream_hello.py "Explain transformers in 3 sentences"
"""
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(override=True)  # Why: shell may have ANTHROPIC_API_KEY="" set; .env wins.
console = Console()

client = Anthropic()  # picks up ANTHROPIC_API_KEY from env
model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

prompt = " ".join(sys.argv[1:]) or "In 2 sentences, what is an LLM token?"

console.rule(f"[bold cyan]{model}[/]")

with client.messages.stream(
    model=model,
    max_tokens=400,
    messages=[{"role": "user", "content": prompt}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
    final = stream.get_final_message()

print()
console.rule("[dim]usage[/]")
console.print(
    f"[dim]input tokens: {final.usage.input_tokens}  "
    f"output tokens: {final.usage.output_tokens}  "
    f"stop reason: {final.stop_reason}[/]"
)
