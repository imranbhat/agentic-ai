"""
Phase 1, Ship Deliverable — Structured-output quiz CLI.

Goal: get the model to return a JSON object that conforms to a schema you
defined. This is the single most important LLM primitive after streaming —
you'll use it everywhere (tool calling, agents, structured extraction).

Pattern used: tool use with `tool_choice` forcing a specific tool.
The model "calls" our tool and the input it produces IS the structured output.

Run:
    uv run phase-1/02_quiz_cli.py "the Krebs cycle"
    uv run phase-1/02_quiz_cli.py "Roman aqueducts" --n 3
"""
import argparse
import json
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from rich.console import Console
from rich.panel import Panel

load_dotenv()
console = Console()


# ---- Schema (Pydantic, mirrored to JSON Schema for the API) ----------------

class QuizQuestion(BaseModel):
    question: str = Field(..., description="The question text.")
    answer: str = Field(..., description="The correct answer, concise.")
    explanation: str = Field(..., description="One-sentence why-this-is-the-answer.")


class Quiz(BaseModel):
    topic: str
    difficulty: str = Field(..., description="One of: easy, medium, hard.")
    questions: list[QuizQuestion]


QUIZ_TOOL = {
    "name": "submit_quiz",
    "description": "Submit a structured quiz on the requested topic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "difficulty": {
                "type": "string",
                "enum": ["easy", "medium", "hard"],
            },
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "answer": {"type": "string"},
                        "explanation": {"type": "string"},
                    },
                    "required": ["question", "answer", "explanation"],
                },
            },
        },
        "required": ["topic", "difficulty", "questions"],
    },
}


# ---- The call --------------------------------------------------------------

def make_quiz(topic: str, n: int = 5, difficulty: str = "medium") -> Quiz:
    client = Anthropic()
    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

    response = client.messages.create(
        model=model,
        # 4096 leaves headroom for "hard" topics where 5 detailed Q+A+explanation
        # entries can exceed 2k output tokens. Truncated tool-call JSON is one
        # of the most common silent failure modes in structured-output code.
        max_tokens=4096,
        tools=[QUIZ_TOOL],
        # Forcing the tool guarantees structured output — no parsing prose.
        tool_choice={"type": "tool", "name": "submit_quiz"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Create a {difficulty}-difficulty quiz on: {topic}. "
                    f"Produce exactly {n} questions. Vary question types "
                    f"(definition, application, comparison)."
                ),
            }
        ],
    )

    # If we hit the cap mid-tool-call, the JSON will be truncated and Pydantic
    # validation will fail with confusing "Field required" errors downstream.
    # Catch it here with a clear message — diagnostics > silent corruption.
    if response.stop_reason == "max_tokens":
        raise RuntimeError(
            f"Model hit max_tokens before finishing. Bump max_tokens or reduce n. "
            f"(input={response.usage.input_tokens}, output={response.usage.output_tokens})"
        )

    # The tool input IS the structured JSON — find the tool_use block.
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_quiz":
            return Quiz(**block.input)

    raise RuntimeError("Model did not call the submit_quiz tool.")


# ---- CLI -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate a structured quiz.")
    parser.add_argument("topic", help="Topic to quiz on")
    parser.add_argument("--n", type=int, default=5, help="Number of questions")
    parser.add_argument("--difficulty", default="medium", choices=["easy", "medium", "hard"])
    parser.add_argument("--json", action="store_true", help="Print raw JSON only")
    args = parser.parse_args()

    try:
        quiz = make_quiz(args.topic, n=args.n, difficulty=args.difficulty)
    except ValidationError as e:
        console.print(f"[red]Schema validation failed:[/]\n{e}")
        sys.exit(1)

    if args.json:
        print(json.dumps(quiz.model_dump(), indent=2))
        return

    console.rule(f"[bold cyan]Quiz: {quiz.topic}[/] [dim]({quiz.difficulty})[/]")
    for i, q in enumerate(quiz.questions, 1):
        console.print(Panel.fit(
            f"[bold]Q{i}.[/] {q.question}\n\n"
            f"[green]Answer:[/] {q.answer}\n"
            f"[dim]Why:[/] {q.explanation}",
            border_style="cyan",
        ))


if __name__ == "__main__":
    main()
