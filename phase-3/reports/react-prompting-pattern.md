# ReAct: The Reasoning and Acting Prompting Pattern

## Overview

ReAct (Reasoning and Acting) is a prompting paradigm for large language models (LLMs) that combines reasoning traces with task-specific actions in an interleaved manner [1]. Introduced by Yao et al. in October 2022, the framework enables LLMs to generate both verbal reasoning and actionable steps simultaneously, allowing them to interact with external environments and update their knowledge dynamically [2].

## Who Introduced ReAct

ReAct was introduced by **Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, and Yuan Cao** at Google Research, with Shunyu Yao and Yuan Cao being the lead researchers [2]. The paper was submitted on October 6, 2022, and was published at a major venue with the final camera-ready version in March 2023 [2].

## How ReAct Works

ReAct addresses a key limitation of chain-of-thought (CoT) prompting: while CoT enables reasoning traces, it lacks access to the external world and cannot update its knowledge in real-time [1]. In contrast, ReAct creates a synergy between reasoning and acting by:

1. **Generating reasoning traces** – Free-form language that helps the model induce, track, update, and adjust action plans, and handle exceptions
2. **Taking actions** – Executing task-specific actions (e.g., "search") that interface with external sources like Wikipedia, search engines, or knowledge bases
3. **Observing feedback** – Receiving information from the environment, which feeds back into subsequent reasoning steps [1]

This creates a dynamic loop where reasoning guides what actions to take, and actions retrieve external information to refine reasoning [1].

## Performance and Applications

The ReAct framework was evaluated across diverse benchmarks with strong results:

- **Question Answering (HotpotQA)**: ReAct achieved 27.4% exact match with PaLM-540B, and when combined with CoT reached 35.1%, outperforming pure reasoning or acting approaches [1]
- **Fact Verification (Fever)**: ReAct achieved 60.9% accuracy, surpassing reasoning-only methods [1]
- **Interactive Decision Making**: On ALFWorld and WebShop tasks, ReAct outperformed imitation and reinforcement learning methods by 34% and 10% respectively, using only one or two in-context examples [1]

Beyond performance, ReAct improves human interpretability and trustworthiness by generating human-like task-solving trajectories that are more transparent than methods relying solely on reasoning or acting [1].

## Sources

[1] "ReAct: Synergizing Reasoning and Acting in Language Models," Google Research Blog, November 8, 2022. https://research.google/blog/react-synergizing-reasoning-and-acting-in-language-models/

[2] Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models," arXiv:2210.03629 (cs.CL), submitted October 6, 2022. https://arxiv.org/abs/2210.03629

[3] "ReAct Prompting," Prompt Engineering Guide. https://www.promptingguide.ai/techniques/react
