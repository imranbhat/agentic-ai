"""
Phase 3, Exercise 5 — THE SHIP: a research agent in pure Python.

This is the Phase 3 deliverable from the roadmap. Same agent loop you built
in Exercises 1-4 — model → tool → result → model → ... → done — but now the
tools touch the REAL WORLD: the live web and your filesystem.

Input:  a question.
Output: a cited markdown report written to phase-3/reports/.

Three tools (all client-side — OUR code runs them, which is the Phase 3 lesson):

  web_search(query)        DuckDuckGo via `ddgs`. No API key. Returns a
                           numbered list of {title, url, snippet}.
  fetch_url(url)           httpx + BeautifulSoup. Strips HTML to plain text
                           and TRUNCATES — unbounded tool output is how you
                           blow your context window and your budget.
  write_file(name, text)   Saves the final report under phase-3/reports/.
                           Path-sanitized so the model can't escape the dir.

What's genuinely new vs Exercises 1-4
-------------------------------------
1. REAL side effects. Exercises 1-4 used pure functions (math, time). Here a
   tool hits the network (slow, flaky, may fail) and another writes a file
   (irreversible-ish). Tool DESIGN starts to matter: bounded output, graceful
   errors, sanitized inputs.

2. MULTI-STEP autonomy. One question becomes: search → pick sources → fetch
   several → synthesize → write. The model sequences this itself. You just
   supply the tools and the loop.

3. The loop is UNCHANGED. Copy it from Exercise 2 almost verbatim. That's the
   payoff of building from scratch: the ship is the same five lines plus three
   real tools.

Why DuckDuckGo (a non-Anthropic dependency — flagged per our Anthropic-first
rule): it needs no API key, so this runs for you immediately. Production agents
swap in Tavily/Brave/Exa for quality — that's a one-function change to
`web_search` and nothing else.

Run:
    uv run phase-3/05_research_agent.py "What is the ReAct prompting pattern and who introduced it?"
    uv run phase-3/05_research_agent.py "Compare RAG vs fine-tuning for keeping an LLM current" --model claude-sonnet-4-6
    uv run phase-3/05_research_agent.py "How does prompt caching cut cost on Anthropic?" --trace
"""
import argparse
import json
import os
import re
from typing import Any

import httpx
from anthropic import Anthropic
from bs4 import BeautifulSoup
from ddgs import DDGS
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(override=True)
console = Console()

PRICES = {
    "claude-haiku-4-5":  (0.80,  4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7":   (15.00, 75.00),
    "claude-opus-4-8":   (15.00, 75.00),
}

# Tool-output caps. The model only ever sees what a tool returns, and every
# returned character becomes an input token on EVERY subsequent iteration
# (the conversation only grows). Bounding tool output is the single biggest
# lever on a research agent's cost and on staying inside the context window.
FETCH_CHAR_CAP = 6000        # ~1,500 tokens per fetched page
SEARCH_MAX_RESULTS = 5
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")


# ===========================================================================
# 1. The three real tools
# ===========================================================================
def web_search(query: str) -> str:
    """Search the web (DuckDuckGo). Return a numbered list the model can read."""
    results = DDGS().text(query, max_results=SEARCH_MAX_RESULTS)
    if not results:
        return f"No results for {query!r}."
    lines = []
    for i, r in enumerate(results, 1):
        # Why we hand back the URL explicitly: the model needs it both to
        # decide what to fetch next AND to cite sources in the final report.
        lines.append(f"[{i}] {r['title']}\n    url: {r['href']}\n    {r['body'][:200]}")
    return "\n".join(lines)


def fetch_url(url: str) -> str:
    """Fetch a page and return cleaned, TRUNCATED plain text."""
    resp = httpx.get(
        url, follow_redirects=True, timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (learn-ai research agent)"},
    )
    resp.raise_for_status()  # turn 4xx/5xx into an exception the loop reports as ERROR

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())

    if len(text) > FETCH_CHAR_CAP:
        # Tell the model we truncated — otherwise it may assume it saw the
        # whole page and miss that the tail exists.
        text = text[:FETCH_CHAR_CAP] + f"\n\n[...truncated at {FETCH_CHAR_CAP} chars...]"
    return text


def write_file(filename: str, content: str) -> str:
    """Write the report under phase-3/reports/. Path-sanitized."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    # Why basename(): the model controls `filename`. Stripping any directory
    # part stops it writing outside reports/ (e.g. "../../etc/foo"). Cheap
    # sandbox; a real system would do more.
    safe = os.path.basename(filename)
    if not safe.endswith(".md"):
        safe += ".md"
    path = os.path.join(REPORTS_DIR, safe)
    with open(path, "w") as f:
        f.write(content)
    return f"Wrote {len(content)} chars to {path}"


TOOLS_BY_NAME = {
    "web_search": web_search,
    "fetch_url": fetch_url,
    "write_file": write_file,
}

TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": (
            "Search the web and return the top results as a numbered list with "
            "title, URL, and a short snippet. Use this FIRST to discover sources. "
            "Call it again with refined queries if the first results are weak."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": (
            "Fetch one web page and return its readable text (truncated). Use this "
            "on the most promising URLs from web_search to read the actual content "
            "before writing. Fetch several sources so the report is well-grounded."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The full URL to fetch."},
            },
            "required": ["url"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Save the final markdown report. Call this exactly once, at the end, "
            "after you have gathered enough information. Provide a short filename "
            "and the complete markdown content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Short name, e.g. 'react-pattern.md'."},
                "content": {"type": "string", "description": "The full markdown report."},
            },
            "required": ["filename", "content"],
        },
    },
]


# ===========================================================================
# 2. System prompt — the research workflow, as rules
# ===========================================================================
SYSTEM_PROMPT = """You are a research agent. Given a question, you produce a concise, accurate, CITED markdown report.

Your workflow:
1. web_search to find sources. Refine the query if results are weak.
2. fetch_url on the 2-4 most promising results to read real content. Do not
   write from snippets alone — fetch and read.
3. Synthesize what you learned into a markdown report:
   - A short title (# heading).
   - 2-4 sections answering the question.
   - Inline citations like [1], [2] tied to the sources you actually fetched.
   - A final "## Sources" section listing each [n] with its URL.
4. write_file ONCE to save the report. Then give the user a 2-sentence summary.

Rules:
- Ground every claim in a fetched source. If sources conflict, say so.
- If a fetch returns an ERROR, try a different URL — don't keep retrying the same one.
- Be concise. A tight, correct report beats a long padded one.
- Do not call write_file until you have fetched at least two sources."""


# ===========================================================================
# 3. The agent loop — copied from Exercise 2, essentially unchanged
# ===========================================================================
def run_agent(question: str, model: str, max_iterations: int, max_tokens: int, trace: bool) -> None:
    client = Anthropic()
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]

    total_in_tokens = 0
    total_out_tokens = 0
    tools_called: list[str] = []

    for iteration in range(1, max_iterations + 1):
        console.rule(f"[bold cyan]Iteration {iteration}[/]")

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        for block in response.content:
            if block.type == "text":
                console.print(f"[green]💬 {block.text.strip()}[/]")
            elif block.type == "tool_use":
                # Show a compact preview — write_file's content can be huge.
                preview = {k: (v[:60] + "…" if isinstance(v, str) and len(v) > 60 else v)
                           for k, v in block.input.items()}
                console.print(f"[yellow]🔧 {block.name}({json.dumps(preview)})[/]")
                tools_called.append(block.name)

        in_t, out_t = response.usage.input_tokens, response.usage.output_tokens
        total_in_tokens += in_t
        total_out_tokens += out_t
        in_price, out_price = PRICES.get(model, (0.0, 0.0))
        running = (total_in_tokens * in_price + total_out_tokens * out_price) / 1_000_000
        console.print(f"[dim]   tokens: in={in_t} out={out_t}  running ${running:.4f}[/]")

        if response.stop_reason == "end_turn":
            console.rule("[bold green]✓ Finished[/]")
            _print_summary(iteration, tools_called, total_in_tokens, total_out_tokens, model)
            if trace:
                _print_trace(messages)
            return

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            fn = TOOLS_BY_NAME.get(block.name)
            if fn is None:
                content = f"ERROR: unknown tool {block.name!r}. Available: {list(TOOLS_BY_NAME)}"
                console.print(f"[red]⚠  unknown tool: {block.name}[/]")
            else:
                try:
                    result = fn(**block.input)
                    content = str(result)
                    # Show a short confirmation, not the whole payload.
                    console.print(f"[blue]⚙  → {content[:120].strip()}{'…' if len(content) > 120 else ''}[/]")
                except Exception as e:
                    content = f"ERROR: {type(e).__name__}: {e}"
                    console.print(f"[red]⚠  failed: {content[:120]}[/]")
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


# ===========================================================================
# Helpers — same as Exercises 2/3
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
    console.rule("[dim]conversation trace[/]")
    for i, msg in enumerate(messages):
        content = msg["content"]
        if isinstance(content, str):
            console.print(f"  [bold]{i:2d}[/] [{msg['role']:9s}] {content[:100]}")
        else:
            for j, block in enumerate(content):
                bt = getattr(block, "type", None) or block.get("type")
                if bt == "text":
                    txt = (getattr(block, "text", None) or block.get("text", ""))[:80]
                    console.print(f"  [bold]{i:2d}[/].{j} [{msg['role']:9s}] text: {txt}")
                elif bt == "tool_use":
                    name = getattr(block, "name", None) or block.get("name")
                    console.print(f"  [bold]{i:2d}[/].{j} [{msg['role']:9s}] tool_use: {name}")
                elif bt == "tool_result":
                    out = str(getattr(block, "content", None) or block.get("content", ""))[:80]
                    console.print(f"  [bold]{i:2d}[/].{j} [{msg['role']:9s}] tool_result: {out}")


def main():
    parser = argparse.ArgumentParser(description="Research agent: question → cited markdown report.")
    parser.add_argument("question", nargs="+", help="The research question.")
    parser.add_argument("--max-iterations", type=int, default=15,
                        help="Cap on loop turns (search+fetch+write needs headroom; default 15).")
    parser.add_argument("--max-tokens", type=int, default=4096,
                        help="Output cap per turn. The report is long — keep this high.")
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"))
    parser.add_argument("--trace", action="store_true", help="Dump the full messages list at the end.")
    args = parser.parse_args()

    question = " ".join(args.question)
    console.print(
        f"[bold]Research question:[/] {question}\n"
        f"[dim]model={args.model}  max_iterations={args.max_iterations}  reports → {REPORTS_DIR}[/]\n"
    )
    run_agent(question, args.model, args.max_iterations, args.max_tokens, args.trace)


if __name__ == "__main__":
    main()
