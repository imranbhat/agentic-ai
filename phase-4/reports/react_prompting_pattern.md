# The ReAct Prompting Pattern

## What is ReAct?

ReAct (Reasoning + Acting) is a prompting framework that enables large language models to generate both reasoning traces and task-specific actions in an interleaved manner [1]. Unlike traditional chain-of-thought prompting, which focuses solely on reasoning, ReAct combines internal reasoning with external action, allowing LLMs to interact with external tools and environments to retrieve additional information during problem-solving [1].

The framework works through a cyclical pattern of three steps: **Thought** (reasoning about the situation), **Action** (deciding what to do), and **Observation** (processing results from the environment). This process repeats until a solution is reached, mirroring human decision-making more closely than linear prompting approaches [2].

## Who Introduced ReAct?

ReAct was introduced by **Yao et al. in 2022** [1]. The full list of authors is: Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik R. Narasimhan, and Yuan Cao. The framework was published in a paper titled "ReAct: Synergizing Reasoning and Acting in Language Models" presented at the Eleventh International Conference on Learning Representations in 2022 [2].

## Key Advantages

ReAct offers several significant improvements over earlier prompting techniques:

- **Reduced Hallucination**: By grounding responses in external data sources rather than relying solely on the model's internal knowledge [1]
- **Better Reasoning**: Generates reasoning traces that allow the model to induce, track, and update action plans and handle exceptions [1]
- **Improved Reliability**: Outperforms chain-of-thought prompting on language and decision-making tasks by combining both internal knowledge and external information [1]
- **Enhanced Interpretability**: Leads to improved human interpretability and trustworthiness of LLMs compared to black-box reasoning approaches [1]

The research showed that the best approach combines ReAct with chain-of-thought prompting to leverage both internal knowledge and external information obtained during reasoning [1].

## Sources

[1] https://www.promptingguide.ai/techniques/react

[2] https://sebgnotes.com/blog/2025-01-01-react-prompting/
