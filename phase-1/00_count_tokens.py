"""
Phase 1, Exercise 0 — Count tokens.

The single most useful tool in your prompt-engineering toolbox. Reach for it
whenever you're estimating cost, designing prompts, or wondering why the
model's context limit feels surprisingly tight.

Uses Anthropic's free `count_tokens` endpoint — no tokens are charged.

Run:
    uv run phase-1/00_count_tokens.py "In 2 sentences, what is an LLM token?"
    uv run phase-1/00_count_tokens.py "$(cat README.md)"
    echo "anything you want" | uv run phase-1/00_count_tokens.py -

Try these to build intuition (run them and compare):
    uv run phase-1/00_count_tokens.py "token"
    uv run phase-1/00_count_tokens.py " token"           # leading space → different
    uv run phase-1/00_count_tokens.py "tokenization"     # one word, multiple tokens
    uv run phase-1/00_count_tokens.py "LLM AI API"       # acronyms split badly
    uv run phase-1/00_count_tokens.py "the the the"      # super common = cheap
"""
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv(override=True)  # Why: shell may have ANTHROPIC_API_KEY="" set; .env wins.
console = Console()

# Prices per 1M tokens (input / output). Update from console.anthropic.com/pricing.
PRICES = {
    "claude-haiku-4-5":  (0.80,  4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7":   (15.00, 75.00),
}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "-":
        text = sys.stdin.read()
    else:
        text = " ".join(sys.argv[1:])

    client = Anthropic()
    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

    resp = client.messages.count_tokens(
        model=model,
        messages=[{"role": "user", "content": text}],
    )
    tokens = resp.input_tokens
    chars = len(text)
    words = len(text.split())

    console.rule(f"[bold cyan]Token count[/]  [dim]({model})[/]")
    console.print(f"[bold]Text:[/] {text!r}\n")

    table = Table(show_header=False, box=None)
    table.add_row("Characters", f"{chars}")
    table.add_row("Words",      f"{words}")
    table.add_row("Tokens",     f"[bold cyan]{tokens}[/]")
    table.add_row("Chars/token", f"{chars / tokens:.2f}" if tokens else "—")
    table.add_row("Words/token", f"{words / tokens:.2f}" if tokens else "—")
    console.print(table)

    # Note: count_tokens reports tokens for the FULL message envelope
    # (role markers, content wrappers). The raw text alone would be a few
    # tokens fewer. The API charges you for the envelope, so this is the
    # number that matters for cost.

    console.rule("[dim]cost at this size[/]")
    cost_table = Table(show_header=True, header_style="bold")
    cost_table.add_column("Model")
    cost_table.add_column("Input cost", justify="right")
    cost_table.add_column("1M-call cost", justify="right")
    for m, (in_price, _) in PRICES.items():
        per_call = tokens / 1_000_000 * in_price
        per_million = per_call * 1_000_000
        cost_table.add_row(m, f"${per_call:.6f}", f"${per_million:,.0f}")
    console.print(cost_table)

    console.print(
        "\n[dim]Note: this counts only the input. Output tokens are charged "
        "separately at a higher rate (typically 4–5× input).[/]"
    )


if __name__ == "__main__":
    main()
