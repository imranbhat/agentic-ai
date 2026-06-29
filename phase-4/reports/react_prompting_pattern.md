# The ReAct Prompting Pattern

## What Is ReAct?

ReAct is a prompting pattern that interleaves reasoning and action—allowing language models to think about what to do, take an action (typically a tool call), observe the result, and then reason again in a cyclical loop [1]. Rather than planning an entire sequence upfront and executing it blindly, the model reasons one step ahead, acts, looks at what came back, and adjusts accordingly. This loop repeats until the task is complete [1].

The core cycle consists of three repeating steps [1]:

- **Thought**: The model reasons about the current state and decides what to do next.
- **Action**: The model calls a tool (search, read a file, run a query, hit an API).
- **Observation**: The tool returns a result, which becomes part of the next thought.

## Who Introduced It and When

ReAct was introduced by **Yao et al. at Google Brain in 2022** in the paper *"ReAct: Synergizing Reasoning and Acting in Language Models."* [2][1]. The authors were Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik R Narasimhan, and Yuan Cao, and the work was published in the Eleventh International Conference on Learning Representations in 2022 [3].

## Why ReAct Works Better Than Alternatives

The research showed that interleaving reasoning with action dramatically reduces hallucination rates on knowledge-intensive tasks compared to pure chain-of-thought reasoning or pure action without reasoning [2]. ReAct is superior in uncertain environments because it enables course-correction mid-task: if a search returns nothing useful or a tool call fails, the next reasoning step observes the failure and adjusts rather than continuing blindly down a wrong path [1].

ReAct shines for multi-hop questions, web search tasks, document retrieval, code execution, and API calls against real systems—where partial results inform the next step. It is less beneficial for tasks with no external state or verification points, such as essay writing [1].

## Impact and Modern Adoption

Since its introduction, ReAct has become the baseline pattern for agentic systems [1]. By 2026, most coding agents—including Claude Code, Cursor, and Aider—run a ReAct-style loop internally [1]. Modern agent frameworks like LangChain, LangGraph, and native tool-use APIs from Anthropic and OpenAI have made implementing ReAct loops accessible to developers [2].

## Sources

[1] https://sureprompts.com/blog/react-prompting-guide

[2] https://nesyona.com/articles/agentic-prompting

[3] https://sebgnotes.com/blog/2025-01-01-react-prompting/