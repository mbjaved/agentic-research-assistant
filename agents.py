"""Agent abstraction and the four specialist agents.

Each Agent wraps a Claude system prompt and can optionally call tools via
Anthropic's native tool-use loop. The orchestrator wires them together.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from config import CLAUDE_MODEL, MAX_TOKENS, WRITER_MAX_TOKENS, get_client


def _extract_text(message) -> str:
    """Concatenate all text blocks from an Anthropic message response."""
    return "".join(block.text for block in message.content if block.type == "text").strip()


def _parse_json(text: str):
    """Best-effort JSON extraction: handles ```json fences and surrounding prose."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    # Fall back to the first {...} or [...] span if needed.
    if not fenced:
        span = re.search(r"(\{.*\}|\[.*\])", candidate, re.DOTALL)
        if span:
            candidate = span.group(1)
    return json.loads(candidate)


@dataclass
class Agent:
    """A single-purpose agent backed by a Claude system prompt."""

    name: str
    system: str
    model: str = CLAUDE_MODEL
    max_tokens: int = MAX_TOKENS                         # per-agent output budget
    tools: list = field(default_factory=list)          # Anthropic tool schemas
    tool_fns: dict = field(default_factory=dict)        # name -> python callable

    def run(
        self,
        prompt: str,
        on_event: Callable[[str, str], None] | None = None,
        max_tool_rounds: int = 2,
    ) -> str:
        """Send `prompt` to the agent, resolving any tool calls, return final text."""
        client = get_client()
        messages = [{"role": "user", "content": prompt}]

        for _ in range(max_tool_rounds + 1):
            kwargs = dict(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system,
                messages=messages,
            )
            if self.tools:
                kwargs["tools"] = self.tools

            message = client.messages.create(**kwargs)

            if message.stop_reason != "tool_use":
                return _extract_text(message)

            # Resolve every tool_use block, then continue the loop.
            messages.append({"role": "assistant", "content": message.content})
            tool_results = []
            for block in message.content:
                if block.type != "tool_use":
                    continue
                fn = self.tool_fns.get(block.name)
                if on_event:
                    on_event(self.name, f"calling tool `{block.name}` {json.dumps(block.input)}")
                try:
                    result = fn(**block.input) if fn else f"No tool named {block.name}"
                except Exception as exc:  # keep the loop robust for a demo
                    result = f"Tool error: {exc}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })
            messages.append({"role": "user", "content": tool_results})

        # Tool-round budget exhausted: force one final answer without tools.
        final = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.system + "\n\nStop using tools now and give your best final answer.",
            messages=messages,
        )
        return _extract_text(final)


# --------------------------------------------------------------------------
# Specialist agents
# --------------------------------------------------------------------------

def planner_agent() -> Agent:
    return Agent(
        name="Planner",
        system=(
            "You are a research planner. Given a topic or goal, break it into a focused "
            "research plan. Return ONLY JSON of the form:\n"
            '{"title": "...", "subtasks": ["question 1", "question 2", "question 3"]}\n'
            "Use exactly 3 sharp, non-overlapping subtasks that together cover the goal."
        ),
    )


def researcher_agent(tools: list, tool_fns: dict) -> Agent:
    return Agent(
        name="Researcher",
        system=(
            "You are a diligent researcher. For the given question, gather the key facts and "
            "insights. If a web_search tool is available, use it for anything time-sensitive or "
            "factual before answering; otherwise rely on your knowledge and say so. "
            "Return 4-8 concise bullet points of findings, each self-contained."
        ),
        tools=tools,
        tool_fns=tool_fns,
    )


def writer_agent() -> Agent:
    return Agent(
        name="Writer",
        max_tokens=WRITER_MAX_TOKENS,
        system=(
            "You are a technical writer. Using the research findings provided, write a clear, "
            "well-structured report in Markdown with a short intro, logical sections with "
            "headings, and a brief conclusion. Keep it focused — roughly 600-900 words — and "
            "make sure it is complete with a proper conclusion (never cut off mid-section). "
            "Be accurate and cite specifics from the findings. Do not invent facts beyond them."
        ),
    )


def fact_checker_agent(tools: list, tool_fns: dict) -> Agent:
    return Agent(
        name="Fact-Checker",
        system=(
            "You are a meticulous fact-checker. Extract the key factual claims from the report "
            "and assess whether each is well-supported. If a web_search tool is available, use it "
            "to verify time-sensitive, statistical, or surprising claims before judging them. "
            "Return ONLY JSON of the form:\n"
            '{"claims": [{"claim": "...", "verdict": "supported" | "unsupported" | "uncertain", '
            '"note": "...", "sources": ["https://...", "https://..."]}], '
            '"issues": "concise summary of any unsupported/uncertain claims the writer must fix or '
            'qualify — empty string if everything checks out"}\n'
            "In each claim's `sources`, include only URLs you actually obtained from web_search "
            "results. If you did not search, leave `sources` as an empty list."
        ),
        tools=tools,
        tool_fns=tool_fns,
    )


def citation_agent() -> Agent:
    return Agent(
        name="Editor",
        max_tokens=WRITER_MAX_TOKENS,
        system=(
            "You add citations to a finished report WITHOUT changing its meaning or wording. "
            "You are given the report and a numbered list of sources (URL + the claim each "
            "supports).\n"
            "1. Insert inline citations as clickable Markdown links of the exact form "
            "[[1]](https://the-source-url) immediately after the sentences they support, using "
            "that source's URL.\n"
            "2. Append a '## Sources' section as a numbered Markdown list where each item links "
            "to its URL, e.g. `1. [https://example.com](https://example.com)`.\n"
            "Do not alter the prose otherwise and do not invent citations or URLs. "
            "Return the full updated Markdown report."
        ),
    )


def critic_agent() -> Agent:
    return Agent(
        name="Critic",
        system=(
            "You are a rigorous editor. Evaluate the report against the original goal for "
            "accuracy, completeness, structure, and clarity. Return ONLY JSON of the form:\n"
            '{"score": 0-10, "verdict": "accept" | "revise", "feedback": "specific, actionable notes"}\n'
            'Use "accept" only when score >= 8.'
        ),
    )


# Expose the JSON parser for the orchestrator.
parse_json = _parse_json
