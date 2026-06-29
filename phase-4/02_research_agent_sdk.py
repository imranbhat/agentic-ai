"""
Phase 4, Exercise 02 — THE SHIP: the Phase 3 research agent, rebuilt on the SDK.

This is the Phase 4 deliverable. It is a *faithful port* of
`phase-3/05_research_agent.py`: the SAME three tools (web_search via ddgs,
fetch_url with the 6,000-char cap, write_file), the SAME system prompt, the
SAME kind of output (a cited markdown report). One thing is deleted: the
hand-written agent loop. The Claude Agent SDK runs it instead.

Put the two files side by side and the diff IS the lesson of Phase 4:

  Phase 3 (05_research_agent.py)          Phase 4 (this file)
  ----------------------------------      ----------------------------------
  ~200 lines, you own the loop            the loop is gone — query() runs it
  for iteration in range(max_iter):       max_turns=15  (a config field)
    response = client.messages.create     async for message in query(...)
    append assistant content              the SDK appends for you
    run each tool, build tool_result      the SDK calls your @tool + feeds back
    append user tool_results              "
    if stop_reason == end_turn: break     the SDK decides when it's done
  PRICES table + manual token math        ResultMessage.total_cost_usd
  unknown-tool guard, error round-trip    the SDK handles tool dispatch

What you STILL write (the part a framework can't do for you): the three tools
themselves. Tool *design* — bounded output, sanitized paths, useful return
strings — is yours regardless of framework. That's the durable Phase 3 skill.

Faithful-port options (each is a deliberate choice, see comments below):
  tools=[]                 -> NO built-in tools. Only our three exist, like Phase 3.
  setting_sources=[]       -> isolation: do NOT load CLAUDE.md. (Exercise 01 left
                              this default and the agent became repo-aware — here
                              we want a clean agent that sees only the question.)
  system_prompt=<string>   -> replaces the Claude Code preset with OUR prompt.
  max_turns=15             -> the SDK's built-in version of Phase 3's loop guard.
  permission_mode=bypass   -> run non-interactively (our tools write files).

Run:
    uv run phase-4/02_research_agent_sdk.py "What is the ReAct prompting pattern and who introduced it?"
    uv run phase-4/02_research_agent_sdk.py "Compare RAG vs fine-tuning for keeping an LLM current" --model claude-sonnet-4-6
    # reports are written to phase-4/reports/ (checked in as sample output)
"""
import argparse
import asyncio
import os

import httpx
from bs4 import BeautifulSoup
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
    tool,
)
from ddgs import DDGS
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(override=True)
console = Console()

# Identical knobs to Phase 3 — the port has to be apples-to-apples.
FETCH_CHAR_CAP = 6000
SEARCH_MAX_RESULTS = 5
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")


# ===========================================================================
# 1. The three real tools — same logic as Phase 3, now wrapped as @tool.
#
# The @tool decorator turns a plain async function into an MCP tool. The shape
# is fixed: it receives `args` (a dict of the inputs) and must return
# {"content": [{"type": "text", "text": <string the model sees>}]}. That return
# string is exactly what we returned from the Phase 3 tools — the model still
# only ever sees a string, so all the Phase 3 design lessons carry over.
#
# Caveat we're choosing to live with: ddgs and httpx are *synchronous*, so
# calling them inside an `async def` blocks the event loop for the duration of
# the call. Fine for a single-user teaching script (nothing else is running),
# but a production port would use httpx.AsyncClient and run ddgs in a thread.
# Surfacing the shortcut instead of hiding it.
# ===========================================================================
@tool(
    "web_search",
    "Search the web and return the top results as a numbered list with title, "
    "URL, and a short snippet. Use this FIRST to discover sources. Call it again "
    "with refined queries if the first results are weak.",
    {"query": str},
)
async def web_search(args):
    results = DDGS().text(args["query"], max_results=SEARCH_MAX_RESULTS)
    if not results:
        text = f"No results for {args['query']!r}."
    else:
        lines = []
        for i, r in enumerate(results, 1):
            # Hand back the URL explicitly — the model needs it both to decide
            # what to fetch next AND to cite sources in the final report.
            lines.append(f"[{i}] {r['title']}\n    url: {r['href']}\n    {r['body'][:200]}")
        text = "\n".join(lines)
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "fetch_url",
    "Fetch one web page and return its readable text (truncated). Use this on "
    "the most promising URLs from web_search to read the actual content before "
    "writing. Fetch several sources so the report is well-grounded.",
    {"url": str},
)
async def fetch_url(args):
    resp = httpx.get(
        args["url"], follow_redirects=True, timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (learn-ai research agent)"},
    )
    resp.raise_for_status()  # 4xx/5xx -> exception; the SDK relays it to the model as an error

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())

    if len(text) > FETCH_CHAR_CAP:
        # Tell the model we truncated — bounded tool output is the #1 cost lever,
        # and the model should know a tail exists that it didn't see.
        text = text[:FETCH_CHAR_CAP] + f"\n\n[...truncated at {FETCH_CHAR_CAP} chars...]"
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "write_file",
    "Save the final markdown report. Call this exactly once, at the end, after "
    "you have gathered enough information. Provide a short filename and the "
    "complete markdown content.",
    {"filename": str, "content": str},
)
async def write_file(args):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    # basename(): the model controls the filename; strip any directory part so it
    # can't write outside reports/ (e.g. "../../etc/foo"). Cheap sandbox.
    safe = os.path.basename(args["filename"])
    if not safe.endswith(".md"):
        safe += ".md"
    path = os.path.join(REPORTS_DIR, safe)
    with open(path, "w") as f:
        f.write(args["content"])
    return {"content": [{"type": "text", "text": f"Wrote {len(args['content'])} chars to {path}"}]}


# ===========================================================================
# 2. System prompt — copied verbatim from Phase 3. The agent's behavior should
#    come from the SAME instructions, so the comparison isolates the framework.
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
# 3. Run the agent — and notice there is NO loop here. query() is the loop.
# ===========================================================================
async def run_agent(question: str, model: str, max_turns: int) -> None:
    # Register our three tools as one in-process MCP server. "research" is the
    # server name; tools are then addressed as mcp__research__<toolname>.
    server = create_sdk_mcp_server(name="research", version="1.0.0",
                                   tools=[web_search, fetch_url, write_file])

    options = ClaudeAgentOptions(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"research": server},
        allowed_tools=[
            "mcp__research__web_search",
            "mcp__research__fetch_url",
            "mcp__research__write_file",
        ],
        tools=[],                       # no built-in Bash/Read/Edit/etc — only our three
        setting_sources=[],             # isolation: don't load CLAUDE.md / project settings
        permission_mode="bypassPermissions",
        max_turns=max_turns,            # the SDK's built-in loop guard (Phase 3 did this by hand)
    )

    console.print(f"[bold]Research question:[/] {question}")
    console.print(f"[dim]model={model}  max_turns={max_turns}  reports → {REPORTS_DIR}  (via Claude Agent SDK)[/]\n")

    # The same model -> tool -> result -> model cycle as Phase 3, but the SDK
    # drives it. We only WATCH the messages stream past and render them.
    async for message in query(prompt=question, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    if block.text.strip():
                        console.print(f"[green]💬 {block.text.strip()}[/]")
                elif isinstance(block, ToolUseBlock):
                    # Compact preview — write_file's content can be huge.
                    preview = {k: (v[:60] + "…" if isinstance(v, str) and len(v) > 60 else v)
                               for k, v in (block.input or {}).items()}
                    console.print(f"[yellow]🔧 {block.name}({preview})[/]")

        elif isinstance(message, ResultMessage):
            cost = message.total_cost_usd or 0.0
            console.rule("[bold green]✓ Finished[/]")
            console.print(
                f"[bold]Summary:[/]  {message.num_turns} turn(s)  •  "
                f"{message.duration_ms} ms  •  [bold]${cost:.4f}[/]"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Research agent on the Claude Agent SDK: question → cited report.")
    parser.add_argument("question", nargs="+", help="The research question.")
    parser.add_argument("--max-turns", type=int, default=15,
                        help="SDK loop guard (search+fetch+write needs headroom; default 15).")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    question = " ".join(args.question)
    asyncio.run(run_agent(question, args.model, args.max_turns))


if __name__ == "__main__":
    main()
