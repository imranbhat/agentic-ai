"""
Phase 4, Exercise 09 — THE RESEARCH AGENT, A THIRD WAY: on LangGraph.

This is the phase finale and a 3-WAY COMPARISON. You have now built the exact
same research agent three times:

  1. Phase 3 (05_research_agent.py) — a hand-written `while` loop. You own everything.
  2. Phase 4 (02_research_agent_sdk.py) — the Claude Agent SDK. The loop is HIDDEN.
  3. Phase 4 (this file) — LangGraph. The loop is an EXPLICIT GRAPH you construct.

That middle-ground is LangGraph's whole pitch. The SDK hid the loop; the raw
`while` loop was invisible structure in your head. LangGraph makes the control
flow a FIRST-CLASS OBJECT: nodes (steps) and edges (transitions) you declare,
compile, and can inspect, checkpoint, stream, and resume.

The graph we build (the Phase 3 loop, drawn as data)
----------------------------------------------------

        START ─▶ (agent) ──tools_condition──▶ (tools) ─┐
                    ▲            │                       │
                    │           └── no tool calls ─▶ END │
                    └───────────────────────────────────┘

- Node "agent": one ChatAnthropic call (tools bound). Emits text and/or tool calls.
- Node "tools": a ToolNode that runs whichever tools the agent asked for.
- Conditional edge `tools_condition`: last message has tool calls → "tools", else → END.
- Back edge tools → agent: feed results in, loop again.

Compare that to Phase 3: `for iteration in range(max): call; if end_turn: break;
run tools; append`. IDENTICAL logic — but here it's a declared graph, not a `for`.
The `recursion_limit` config is LangGraph's version of Phase 3's max-iterations guard.

Anthropic-first note (a deliberate exception)
---------------------------------------------
LangGraph is **provider-agnostic** — this is the one place in the whole repo we
lead with a non-Anthropic framework, on purpose: the roadmap says "learn another
for breadth." We still run *Claude* underneath, wired via `langchain-anthropic`'s
`ChatAnthropic`. New deps (flagged per our rule): `langgraph` + `langchain-anthropic`
pulled ~18 packages (langchain-core, langgraph-checkpoint/prebuilt, langsmith, …).
That weight buys the explicit-graph machinery; whether it's worth it vs the SDK is
exactly what Exercise 03's "what does the framework add?" question asks — now with
a third data point.

The tools are UNCHANGED from Phase 3 — same web_search / fetch_url / write_file,
same 6,000-char cap, same path sanitization. Tool DESIGN is yours in every
framework; only the loop wiring changes. That's the durable lesson, three times over.

Run:
    uv run phase-4/09_langgraph_research_agent.py "What is the ReAct prompting pattern and who introduced it?"
    uv run phase-4/09_langgraph_research_agent.py "Compare RAG vs fine-tuning for keeping an LLM current" --model claude-sonnet-4-6
    # reports are written to phase-4/reports/ (checked in as sample output)
"""
import argparse
import os

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from dotenv import load_dotenv
from rich.console import Console

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv(override=True)
console = Console()

PRICES = {
    "claude-haiku-4-5":  (0.80,  4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-8":   (15.00, 75.00),
}
FETCH_CHAR_CAP = 6000
SEARCH_MAX_RESULTS = 5
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")


# ===========================================================================
# 1. The three tools — copied from Phase 3, now decorated with @tool so
# LangChain generates the schema from the type hints + docstring (like the
# SDK's @tool did in Ex 02). The BODIES are identical to Phase 3.
# ===========================================================================
@tool
def web_search(query: str) -> str:
    """Search the web and return the top results as a numbered list with title, URL, and a
    short snippet. Use this FIRST to discover sources. Refine the query if results are weak."""
    results = DDGS().text(query, max_results=SEARCH_MAX_RESULTS)
    if not results:
        return f"No results for {query!r}."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}\n    url: {r['href']}\n    {r['body'][:200]}")
    return "\n".join(lines)


@tool
def fetch_url(url: str) -> str:
    """Fetch one web page and return its readable text (truncated). Use on the most promising
    URLs from web_search to read real content before writing. Fetch several sources."""
    resp = httpx.get(url, follow_redirects=True, timeout=15,
                     headers={"User-Agent": "Mozilla/5.0 (learn-ai research agent)"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    if len(text) > FETCH_CHAR_CAP:
        text = text[:FETCH_CHAR_CAP] + f"\n\n[...truncated at {FETCH_CHAR_CAP} chars...]"
    return text


@tool
def write_file(filename: str, content: str) -> str:
    """Save the final markdown report. Call once, at the end, after gathering enough info.
    Provide a short filename and the complete markdown content."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    safe = os.path.basename(filename)              # sanitize: model controls the name
    if not safe.endswith(".md"):
        safe += ".md"
    path = os.path.join(REPORTS_DIR, safe)
    with open(path, "w") as f:
        f.write(content)
    return f"Wrote {len(content)} chars to {path}"


TOOLS = [web_search, fetch_url, write_file]

SYSTEM_PROMPT = """You are a research agent. Given a question, you produce a concise, accurate, CITED markdown report.

Your workflow:
1. web_search to find sources. Refine the query if results are weak.
2. fetch_url on the 2-4 most promising results to read real content. Do not write from snippets alone.
3. Synthesize a markdown report: a # title, 2-4 sections, inline citations like [1], [2] tied to sources you
   actually fetched, and a final "## Sources" section listing each [n] with its URL.
4. write_file ONCE to save the report. Then give the user a 2-sentence summary.

Rules:
- Ground every claim in a fetched source. If sources conflict, say so.
- If a fetch returns an ERROR, try a different URL — don't keep retrying the same one.
- Be concise. Do not call write_file until you have fetched at least two sources."""


# ===========================================================================
# 2. Build the GRAPH. This is the whole exercise — the Phase 3 loop, declared
# as nodes + edges instead of written as a `while`.
# ===========================================================================
def build_graph(model: str):
    # bind_tools = "here are the tools you may call" — the LangChain equivalent
    # of Phase 3's `tools=TOOL_DEFINITIONS` on messages.create().
    llm = ChatAnthropic(model=model, max_tokens=4096).bind_tools(TOOLS)

    def agent_node(state: MessagesState) -> dict:
        # One model call. We prepend the system prompt each turn. The returned
        # AIMessage carries text and/or tool_calls; add_messages appends it.
        response = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), *state["messages"]])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)          # state = a growing list of messages
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))   # prebuilt: runs the requested tools
    graph.add_edge(START, "agent")
    # The conditional edge IS Phase 3's `if stop_reason == "tool_use"`: last
    # message has tool calls → run them; otherwise → END.
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")           # back edge: results in, loop again
    return graph.compile()


# ===========================================================================
# 3. Run it, streaming node-by-node so you SEE the graph execute.
# ===========================================================================
def run(question: str, model: str, recursion_limit: int) -> None:
    app = build_graph(model)
    in_price, out_price = PRICES.get(model, (0.0, 0.0))
    total_in = total_out = 0
    tools_called: list[str] = []

    inputs = {"messages": [HumanMessage(content=question)]}
    # recursion_limit = LangGraph's max-iteration guard (Phase 3's for-range cap).
    config = {"recursion_limit": recursion_limit}

    # stream_mode="updates" yields {node_name: {messages: [...]}} after each node
    # fires — so the alternating agent/tools rhythm is visible, like Phase 3's
    # "Iteration N" rules.
    for chunk in app.stream(inputs, config, stream_mode="updates"):
        for node, update in chunk.items():
            console.rule(f"[bold cyan]node: {node}[/]")
            for msg in update["messages"]:
                # Agent node → AIMessage (text + tool_calls). Tools node → ToolMessage.
                # `.text` is a property in langchain-core 1.x (was a method in 0.x).
                text = getattr(msg, "text", None) or str(msg.content)
                if text and text.strip():
                    prefix = "💬" if node == "agent" else "⚙ →"
                    color = "green" if node == "agent" else "blue"
                    console.print(f"[{color}]{prefix} {text.strip()[:400]}"
                                  f"{'…' if len(text.strip()) > 400 else ''}[/]")
                for tc in getattr(msg, "tool_calls", None) or []:
                    preview = {k: (v[:60] + "…" if isinstance(v, str) and len(v) > 60 else v)
                               for k, v in tc["args"].items()}
                    console.print(f"[yellow]🔧 {tc['name']}({preview})[/]")
                    tools_called.append(tc["name"])
                # usage_metadata rides on the AIMessage — LangChain tallied tokens
                # for us (like the SDK's ResultMessage; unlike Phase 3's manual math).
                usage = getattr(msg, "usage_metadata", None)
                if usage:
                    total_in += usage.get("input_tokens", 0)
                    total_out += usage.get("output_tokens", 0)

    cost = (total_in * in_price + total_out * out_price) / 1_000_000
    console.rule("[bold green]✓ graph finished[/]")
    console.print(
        f"[bold]tools:[/] {', '.join(tools_called) or 'none'}  •  "
        f"{total_in + total_out} tokens  •  [bold]${cost:.4f}[/]  (model={model})"
    )


def main():
    parser = argparse.ArgumentParser(description="Research agent on LangGraph (explicit graph): question → cited report.")
    parser.add_argument("question", nargs="+", help="The research question.")
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"))
    parser.add_argument("--recursion-limit", type=int, default=25,
                        help="LangGraph's step cap — the analogue of Phase 3's max-iterations (default 25).")
    args = parser.parse_args()

    question = " ".join(args.question)
    console.print(f"[bold]Research question:[/] {question}\n"
                  f"[dim]model={args.model}  framework=LangGraph  reports → {REPORTS_DIR}[/]\n")
    run(question, args.model, args.recursion_limit)


if __name__ == "__main__":
    main()
