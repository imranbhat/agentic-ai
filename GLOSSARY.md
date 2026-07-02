# Glossary — every term used so far, in plain English

A "look it up fast" reference. Phase READMEs explain the same things with more depth and context — this one is just for "wait, what does X mean again?"

---

## Core LLM mechanics

| Term | Plain English |
|---|---|
| **LLM** (Large Language Model) | A program that predicts what text comes next. Trained on huge amounts of text. Claude, GPT, Gemini are LLMs. |
| **Token** | A small chunk of text the model reads or writes — roughly 4 characters of English. You're billed per token. |
| **Prompt** | The text you send to the model. The "question" or instruction. |
| **Message** | A prompt with a role tag. Format: `{"role": "user", "content": "..."}`. |
| **Role** | Who's speaking: `user` (you), `assistant` (the model), or `system` (background instructions). |
| **System prompt** | Instructions that frame the conversation. Often "You are a helpful assistant…" — sets the model's behavior. |
| **API** | The web address where you send your request. Anthropic's API lives at `api.anthropic.com`. |
| **SDK** | A library (e.g. the `anthropic` Python package) that wraps API calls so you don't write raw HTTP. |
| **Streaming** | The server sends tokens as it generates them. Like watching a video stream vs waiting for a full download. |
| **`max_tokens`** | A cap on how much the model is allowed to write back. If hit mid-response, the answer is truncated. |
| **Context window** | The total tokens (input + output) the model can handle in one call. Claude Haiku 4.5 = 200,000 tokens. |
| **Temperature** | A knob that controls randomness. 0 = always pick the most likely token. 1 = more variety. We've used the default (~0.7). |
| **`stop_reason`** | Why the model stopped writing — `end_turn` (finished naturally), `max_tokens` (hit the cap), `tool_use` (called a tool). |
| **`usage`** | The receipt — `input_tokens` you sent, `output_tokens` it wrote back. Determines cost. |

## Shaping the model's output

| Term | Plain English |
|---|---|
| **Structured output** | Getting the model to return JSON instead of prose, so your code can parse it. |
| **JSON schema** | A description of what your JSON should look like — field names, types, what's required. |
| **Tool use** | Telling the model "here are functions you can 'call' — describe what you'd pass to them." The model returns a function name + arguments. |
| **Real tool** (Mode A) | Your code actually runs the function and feeds results back to the model. The basis of agents. |
| **Fake tool** (Mode B) | You don't run anything. You just keep what the model "passed in" — a trick to force structured output. |
| **`tool_choice`** | A flag that *forces* the model to call a specific tool. Most reliable way to get JSON. |
| **Tool call** | The model's response when it picks a tool — contains the tool name + filled-in arguments. |

## Quality assurance

| Term | Plain English |
|---|---|
| **Eval** | A test suite for AI. A set of inputs + checks. Tells you if a prompt change made things better or worse. |
| **Structural check** | A cheap, deterministic check on output shape (e.g. "did it return 5 items?"). Doesn't judge correctness. |
| **LLM-as-judge** | Using one LLM call to grade another's answer for *meaning* (not just shape). Slower and pricier than structural. |
| **Pydantic** | A Python library that validates dictionaries against typed schemas. Catches malformed JSON loudly. |
| **Validation** | Checking that data matches the shape you expect, before downstream code uses it. |

## Search by meaning (Phase 2)

| Term | Plain English |
|---|---|
| **Embedding** | A list of numbers (a "vector") representing a piece of text's meaning. Same meaning → similar numbers. |
| **Vector** | Just a list of numbers. In our case, 384 of them per text. |
| **Dimension** | How many numbers are in the vector. BGE-small produces 384-dim vectors. |
| **Cosine similarity** | A number between -1 and 1 telling you how similar two vectors are. 1 = identical meaning, 0 = unrelated. |
| **Dot product** | Math operation that, when vectors are unit-length, equals cosine similarity. Faster to compute. |
| **Normalization** (L2 / unit length) | Scaling each vector to length 1. After this, dot product = cosine similarity. |
| **Top-K retrieval** | "Give me the K most similar items." K is usually 3–10. |
| **Chunking** | Splitting a long document into smaller passages before embedding. Each passage becomes one vector. |
| **Vector index** | A bunch of embeddings stored together so you can search them quickly. |
| **RAG** (Retrieval-Augmented Generation) | Find relevant chunks first, then put them in the prompt so the model can answer using *your* data. |

## Agents (Phase 3)

| Term | Plain English |
|---|---|
| **Agent** | An LLM call wrapped in a loop. The model is given tools and decides which to call, over and over, until it's done. |
| **Agent loop** | The cycle: model → tool call → run the tool → feed result back → model → … → finished. The whole of Phase 3 is this loop. |
| **Iteration** | One trip around the agent loop — one model call plus the tools it triggered. We cap them so a buggy agent can't loop forever. |
| **`tool_use`** | Two meanings: a `stop_reason` ("I want to call a tool, keep looping") and a content block holding the tool name + arguments. |
| **`tool_result`** | The block you send *back* carrying a tool's output, so the model can see what happened. Always tagged with the matching `tool_use_id`. |
| **`tool_use_id`** | The ID that links a tool result to the exact tool call it answers. Mismatch it and the API errors. |
| **Parallel tool use** | The model asking for several tools in one turn (e.g. fetch 3 URLs at once) instead of one at a time. |
| **Stateless** | The model remembers nothing between calls. Your code re-sends the *entire* conversation every turn — which is why input tokens grow each iteration. |
| **Max-iteration guard** | A hard cap on loop turns. A non-terminating agent is a real failure mode; always bound it. |
| **ReAct** (Reason + Act) | A prompt pattern: make the model write a "Thought" before each "Action", then see the "Observation". It's a convention, not an API feature. |
| **Thought / Action / Observation** | ReAct's three beats — the reasoning, the tool call, and the tool's result. Just labels the prompt asks for. |
| **Self-critique** (Reflexion) | Generate a draft → a critic call grades it → revise → repeat until it passes. The "tool" is another LLM call. |
| **Generator / Critic** | The two roles in self-critique: one writes, one grades. The seed of multi-agent systems. |
| **Workflow vs agent** | A *workflow* is a fixed chain of steps you hardcode. An *agent* lets the model decide the steps. Many "agents" should have been workflows. |
| **Trajectory** | The sequence of actions an agent actually took (search → fetch → write). Agent evals score the trajectory, not just the final output. |
| **Grounded / groundedness** | Whether the agent's cited sources are ones it *actually read*. An ungrounded citation = an invented source. |
| **Hallucinated source** | A citation the model made up — a URL it never fetched. The #1 thing the research-agent eval catches. |
| **Guardrail** | A cheap check that runs on *every live query* (e.g. "do the cited URLs resolve?"). Different from an eval, which runs in development. |

## Frameworks (Phase 4)

| Term | Plain English |
|---|---|
| **Agent framework** | A library that runs the agent loop *for* you, so you don't hand-write the `while` loop you built in Phase 3. Trades control for convenience. |
| **Claude Agent SDK** | Anthropic's agent framework (the `claude-agent-sdk` Python package). It wraps the Claude Code harness — bundles a Node CLI, is MCP-first, and ships built-in tools, hooks, and permission controls. The Phase 4 default. |
| **`query()`** | The SDK's entry point. An *async generator*: you `async for message in query(...)` and it yields the conversation's messages as the agent runs the loop internally. |
| **`ClaudeAgentOptions`** | The SDK's single config object — `model`, `system_prompt`, `allowed_tools`, `mcp_servers`, `permission_mode`, `cwd`, `hooks`. The agent-shaped successor to `messages.create()`'s kwargs. |
| **Async generator** | A function you iterate with `async for`, producing values lazily over time. The SDK uses one so it can stream messages as the agent works. Forces `async`/`await` + `asyncio.run`. |
| **`AssistantMessage` / `ResultMessage`** | Typed message objects the SDK yields instead of raw `response.content`. `AssistantMessage.content` holds `TextBlock`/`ToolUseBlock`; `ResultMessage` carries `total_cost_usd`, `usage`, `num_turns`, `duration_ms`. |
| **MCP (Model Context Protocol)** | An open standard for how an LLM app talks to a tool provider — "USB-C for AI tools." Defines one uniform format for advertising tools, calling them, and returning results. Solves the M×N integration problem (M apps × N tools → M+N). |
| **MCP client / host vs server** | Two roles. The **client/host** is the LLM app — it discovers tools, hands them to the model, and routes calls. The **server** owns and runs the tools. In Exercise 02 the SDK was the client; our three functions were the server. |
| **In-process MCP server** | How the SDK turns *your* Python functions into agent tools — define with `@tool`, group with `create_sdk_mcp_server`, reference as `mcp__<server>__<tool>`. "In-process" = runs inside your script, no subprocess or network: the MCP *shape* without the MCP *cost*. |
| **Phase 3 (no MCP) vs SDK (MCP)** | Phase 3 passed raw tool-schema dicts inline and *your loop* dispatched calls directly (`fn(**input)`). The SDK is MCP-first: the only way to give it your functions is as a server, and *it* dispatches the calls over MCP. Same effect, standardized interface. |
| **Project-aware (by default)** | The Agent SDK auto-loads the working directory and `CLAUDE.md`, so the agent "knows" the repo it runs in — unlike the raw API, where the model sees only your `messages`. Convenient, but adds input cost. |
| **Building Effective Agents (BEA)** | Anthropic's canonical primer that splits LLM apps into *workflows* (deterministic chains) and *agents* (LLM-driven loops), and names five patterns: prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer. |
| **Prompt chaining** | BEA pattern #1: a fixed sequence of LLM calls you wire in code, each feeding the next, with a *gate* between them. A workflow — *you* own the control flow, not the model. (Phase 4, Ex 04.) |
| **Gate** | A cheap check *between* chain steps that decides whether the chain continues — often pure Python, no LLM. It's what makes a chain a chain rather than "calling the model twice"; it stops a bad step before the next paid one runs. |
| **Routing** | BEA pattern #2: a *branch*. A cheap **classifier** inspects the input and dispatches it to exactly one specialized handler. Chaining is a sequence ("and then"); routing is a switch ("which one?"). (Phase 4, Ex 05.) |
| **Classifier** | The cheap LLM call that labels an input so a router can branch (here Haiku + forced tool use → `{category, reason}`). Its cost is a flat per-request *tax*: routing only pays off when the handlers differ enough in cost/quality to justify it. |
| **Cost/quality routing** | Using a router to send easy inputs to a cheap model, hard ones to a strong model, and out-of-scope ones to a $0 non-LLM path — instead of forcing one model on every input. The main reason routing earns its place. |
| **Parallelization** | BEA pattern #3: fan out several LLM calls *concurrently*, then aggregate. The first non-sequential pattern. Changes *latency* (N calls in ≈ one call's time), not cost (you still pay N×). (Phase 4, Ex 06.) |
| **Voting (aggregation)** | A parallelization flavor: run the *same* prompt N times and take the majority. Reduces variance on uncertain judgments — but only when the calls actually disagree; on a task the model already nails, it's N× cost for nothing. |
| **Sectioning** | A parallelization flavor: split a task into *independent* subtasks, run them at once, stitch the pieces. The win is latency — there's no data dependency, so serializing would just waste wall-clock. |
| **`asyncio.gather` / `AsyncAnthropic`** | Python's async machinery. `AsyncAnthropic` makes API calls awaitable so they overlap on the network; `asyncio.gather(*coros)` runs many at once and returns when all finish (≈ the slowest one's time). |
| **Orchestrator-workers** | BEA pattern #4: a central *orchestrator* model plans subtasks, *worker* calls do them (usually in parallel), a *synthesizer* combines the results. Builds on parallelization, but a model call produces the list being fanned out. (Phase 4, Ex 07.) |
| **Dynamic decomposition** | The defining trait of orchestrator-workers: the subtasks are chosen by the model at runtime and differ per input — unlike *sectioning*, where you hardcode the same subtasks every run. You own the *shape* (plan→work→synthesize); the model owns the *content* (which subtasks). |
| **Workflow↔agent boundary** | The line orchestrator-workers sits right against. It stays a *workflow* because *you* fixed the control flow (one plan, one worker batch, one synthesis). Let the orchestrator *loop* on "is it done yet?" and the *model* owns control flow → it's now an *agent* (Phase 3's while-loop). |
| **Evaluator-optimizer** | BEA pattern #5: two fixed roles in a loop — a *generator* drafts, an *evaluator* grades it and lists issues, the generator revises with that feedback until accepted or a round cap. It's Phase 3's self-critique (Reflexion), named as a pattern. (Phase 4, Ex 08.) |
| **Asymmetric critic** | Using a *stronger* model as the evaluator than as the generator (e.g. Haiku writes, Sonnet grades). A lenient/weak evaluator rubber-stamps round 1 and the loop teaches nothing; the stronger grader forces real iteration. The evaluator sets the quality ceiling. |
| **A loop ≠ an agent** | Evaluator-optimizer *loops* but is still a *workflow*: you fixed the cycle and the exit (`accept` or max rounds), and your `if` owns the branch — the evaluator just fills a graded slot. An *agent* has an open action space (the model chooses the next action), not a predefined cycle. |
| **LangGraph** | A provider-agnostic agent framework that models control flow as an explicit *graph* (`StateGraph` of nodes + edges you declare and compile). Its pitch vs the Claude Agent SDK: the loop is inspectable, checkpointable, and resumable rather than hidden. The one non-Anthropic-first framework in this repo (learned for breadth). (Phase 4, Ex 09.) |
| **Node / edge / conditional edge** | LangGraph's primitives. A *node* is a step (a function — an LLM call, or a `ToolNode`); an *edge* is a fixed transition between nodes; a *conditional edge* (e.g. `tools_condition`) branches on the current state. Together they express the Phase 3 while-loop as a diagram. |
| **`bind_tools` / `ToolNode` / `recursion_limit`** | LangChain/LangGraph tool wiring. `ChatAnthropic.bind_tools([...])` advertises tools to the model (like Phase 3's `tools=`); `ToolNode` runs the calls the model asked for; `recursion_limit` caps graph steps (LangGraph's max-iterations guard). |
| **`langchain-anthropic` / `ChatAnthropic`** | The adapter that lets a provider-agnostic framework (LangChain/LangGraph) call Claude. `ChatAnthropic(model=...)` is the LangChain wrapper around Anthropic's API — how Ex 09 runs Claude *inside* LangGraph. |

## Models and providers

| Term | Plain English |
|---|---|
| **Provider** | A company that hosts LLMs you can call via API. Anthropic, OpenAI, Google, Voyage. |
| **Model** | A specific trained system. Within Claude: Haiku (fast/cheap), Sonnet (balanced), Opus (smartest). |
| **Local model** | Runs on your own computer, no internet, no per-call cost. Slower than API models. We use one for embeddings. |
| **API model** | Lives on the provider's servers. You pay per token. Faster, smarter, requires internet + key. |
| **Voyage** | Anthropic's recommended embedding provider. Cloud-based. Free tier exists; we're not using it yet. |
| **fastembed** | The local embedding library we *are* using. ONNX-based, no PyTorch, cross-platform. |

## Tooling we touched

| Term | Plain English |
|---|---|
| **uv** | A modern Python package manager. Replaces pip + virtualenv + pyenv all in one. Much faster. |
| **`pyproject.toml`** | The Python project's manifest — lists dependencies, Python version, project name. |
| **`.env`** | A file that holds secrets like API keys. Loaded into environment variables at runtime. |
| **ONNX runtime** | A library that runs ML models without needing PyTorch. Smaller, more portable. |
| **PyTorch** | A heavy ML library. Powerful but big. Recently dropped Intel Mac support — that's why we switched to ONNX. |
| **Hugging Face** | A platform for downloading ML models. The BGE embedding model lives there. |
| **httpx** | A Python HTTP client. The research agent uses it to download web pages in `fetch_url`. |
| **BeautifulSoup** | A library that parses HTML so you can strip the junk (scripts, nav) and keep the readable text. |
| **ddgs / DuckDuckGo** | The keyless web-search library the research agent uses. A non-Anthropic dependency; production would swap in Tavily/Brave/Exa. |
| **CLAUDE.md** | A project file that documents rules for AI agents working in the repo. Auto-loaded into Claude Code sessions. |
| **Hook** | A shell command Claude Code runs automatically on certain events (e.g. after a file edit). |
| **Skill** (in Claude Code) | A reusable instruction module Claude can invoke — like `/init` or `/review`. |
| **claude-agent-sdk** | The Python package for the Claude Agent SDK (Phase 4). Heavy install (~66 MiB, 17 deps) because it bundles a Node-based Claude Code CLI. |
| **Node.js** | The JavaScript runtime the bundled Claude Code CLI runs on. The Agent SDK shells out to it under the hood, which is why a Python "agent framework" needs Node present. |

## Acronyms cheat sheet

| Acronym | Means | First-time meaning |
|---|---|---|
| **LLM** | Large Language Model | The model itself (Claude, GPT, Gemini). |
| **API** | Application Programming Interface | The HTTP endpoint your code talks to. |
| **SDK** | Software Development Kit | The library that wraps the API. |
| **JSON** | JavaScript Object Notation | The text format used for structured data. |
| **HTTP / HTTPS** | (Secure) HyperText Transfer Protocol | How browsers and APIs talk over the internet. |
| **CLI** | Command-Line Interface | A program you run from the terminal (no GUI). |
| **RAG** | Retrieval-Augmented Generation | Find relevant context, then generate. |
| **ONNX** | Open Neural Network Exchange | A model format usable without PyTorch. |
| **MCP** | Model Context Protocol | The standard for connecting agents to tools. The Claude Agent SDK is MCP-first — your Phase 4 tools register as an in-process MCP server; consuming external servers is a Phase 5 topic. |
| **ReAct** | Reason + Act | Prompt pattern: think, then act, then observe — looped. |
| **TDD** | Test-Driven Development | Write tests first, then code. |
| **CI/CD** | Continuous Integration / Continuous Deployment | Automated build & deploy pipelines. |

## Quick "which is which?"

- **Token vs character vs word** — Token is the model's unit (~4 chars), character is one letter, word is what humans count. Models think in tokens.
- **Prompt vs message vs conversation** — A *prompt* is text. A *message* is a prompt + role tag. A *conversation* is a list of messages.
- **API vs SDK** — The API is the destination. The SDK is the helper library to reach it.
- **Tool use vs structured output** — Same mechanism. Tool use *is* the API. Structured output is one thing you can do *with* it.
- **Eval vs unit test** — A unit test checks deterministic code. An eval scores LLM output, which is non-deterministic by nature.
- **Eval vs guardrail** — An eval runs in development when *your code* changes (slow, thorough, on a test set). A guardrail runs in production on *every user query* (cheap, inline).
- **Workflow vs agent** — A workflow is steps *you* hardcode. An agent lets *the model* choose the steps. Pick a workflow unless you genuinely need the model to decide.
- **Trajectory vs output** — The output is the final report. The trajectory is *how it got there* (which tools, in what order). Agent evals care about both.
- **Embedding vs prompt** — A prompt asks the model to generate. An embedding asks the model to summarize meaning into numbers. Different endpoints, different costs.
- **Local model vs API model** — Local runs on your CPU (free, slow, basic). API runs in the cloud (paid, fast, smart). For embeddings local is fine; for generation you want API.
