# ReAct Prompting Pattern

## What is ReAct?

ReAct (Reasoning and Acting) is a prompting paradigm that enables large language models (LLMs) to generate both reasoning traces and task-specific actions in an interleaved manner [1]. Rather than treating reasoning and acting as separate processes, ReAct combines them synergistically—reasoning traces help the model induce, track, and update action plans while handling exceptions, while actions allow the model to interface with external sources such as knowledge bases or environments to gather additional information [2].

The core insight is that this tight integration of reasoning and acting creates a synergistic loop: reasoning targets what to retrieve next, while acting through external tools provides information to support further reasoning [2].

## How ReAct Works

ReAct prompts LLMs to generate verbal reasoning traces and actions through an interleaved Thought-Action-Observation (TAO) cycle [1]. In this cycle:

- **Thought**: The model generates free-form reasoning to decompose questions, extract information, perform reasoning, guide search formulation, and synthesize answers
- **Action**: The model generates domain-specific actions (such as "search" for question answering or "go to" for navigation tasks)
- **Observation**: The external environment provides feedback in response to the action [1]

This pattern addresses limitations of chain-of-thought (CoT) prompting alone, which lacks access to external information and can suffer from hallucination and error propagation. ReAct maintains dynamic reasoning to create and adjust plans while incorporating real information from external sources [2].

## Origins and Authors

ReAct was introduced by **Shunyu Yao and colleagues at Google Research** in a paper titled "ReAct: Synergizing Reasoning and Acting in Language Models" submitted in October 2022 [1]. The research team included Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, and Yuan Cao [1].

The work was officially announced on November 8, 2022, and demonstrated the framework's effectiveness across diverse benchmarks including question answering (HotpotQA), fact verification (Fever), interactive games (ALFWorld), and web navigation (WebShop) [2].

## Sources

[1] Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2022). ReAct: Synergizing Reasoning and Acting in Language Models. https://arxiv.org/abs/2210.03629

[2] Google Research. (2022). "ReAct: Synergizing Reasoning and Acting in Language Models." https://research.google/blog/react-synergizing-reasoning-and-acting-in-language-models/
