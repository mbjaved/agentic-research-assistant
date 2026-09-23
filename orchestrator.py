"""Coordinates the multi-agent workflow.

Flow:  Planner -> Researcher (per subtask) -> Writer -> Critic -> (revise loop)

The orchestrator streams progress via an optional `on_event` callback so a CLI
or web UI can show the agents working.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from agents import (
    citation_agent,
    critic_agent,
    fact_checker_agent,
    parse_json,
    planner_agent,
    researcher_agent,
    writer_agent,
)
from tools import build_research_tools

Event = Callable[[str, str], None]


def _agent_json(agent, prompt: str, fallback: dict, on_event: Event | None = None) -> dict:
    """Run an agent expected to return JSON. Retry once with a strict nudge, then
    fall back to a default so a single malformed response never crashes the run."""
    try:
        return parse_json(agent.run(prompt, on_event=on_event))
    except Exception:
        try:
            return parse_json(
                agent.run(prompt + "\n\nReturn ONLY valid JSON — no prose, no code fences.")
            )
        except Exception:
            if on_event:
                on_event(agent.name, "response wasn't valid JSON; using a safe fallback.")
            return fallback


@dataclass
class RunResult:
    goal: str
    title: str
    report: str
    score: int
    rounds: int
    log: list = field(default_factory=list)
    fact_check: dict | None = None
    sources: list = field(default_factory=list)


def run_research(goal: str, max_rounds: int = 2, on_event: Event | None = None) -> RunResult:
    """Run the full pipeline for `goal` and return the final report + trace."""
    log: list = []

    def emit(agent: str, msg: str):
        log.append({"agent": agent, "message": msg})
        if on_event:
            on_event(agent, msg)

    # 1. Plan --------------------------------------------------------------
    emit("Planner", f"Breaking down the goal: {goal!r}")
    plan = _agent_json(
        planner_agent(), f"Goal: {goal}",
        fallback={"title": goal, "subtasks": [goal]}, on_event=on_event,
    )
    title = plan.get("title", goal)
    subtasks = plan.get("subtasks") or [goal]
    emit("Planner", f"Plan '{title}' with {len(subtasks)} subtasks.")

    # 2. Research each subtask --------------------------------------------
    tools, tool_fns = build_research_tools()
    researcher = researcher_agent(tools, tool_fns)
    findings = []
    for i, subtask in enumerate(subtasks, 1):
        emit("Researcher", f"[{i}/{len(subtasks)}] Researching: {subtask}")
        result = researcher.run(f"Question: {subtask}", on_event=on_event)
        findings.append(f"### {subtask}\n{result}")

    findings_block = "\n\n".join(findings)

    # 3. Write -------------------------------------------------------------
    writer = writer_agent()
    emit("Writer", "Drafting the report from findings.")
    report = writer.run(
        f"Goal: {goal}\nTitle: {title}\n\nResearch findings:\n{findings_block}\n\n"
        "Write the full report now."
    )

    # 4. Fact-check the draft, then fix any unsupported claims -------------
    fact_check = None
    emit("Fact-Checker", "Verifying the claims in the draft.")
    try:
        fact_check = _agent_json(
            fact_checker_agent(tools, tool_fns),
            f"Goal: {goal}\n\nReport:\n{report}",
            fallback={"claims": [], "issues": ""}, on_event=on_event,
        )
        claims = fact_check.get("claims", [])
        flagged = [c for c in claims if c.get("verdict") in ("unsupported", "uncertain")]
        issues = (fact_check.get("issues") or "").strip()
        emit(
            "Fact-Checker",
            f"Checked {len(claims)} claim(s); {len(flagged)} need attention."
            + (f" Issues: {issues}" if issues else " All supported."),
        )
        if issues:
            emit("Writer", "Correcting/qualifying flagged claims.")
            report = writer.run(
                f"Goal: {goal}\n\nCurrent report:\n{report}\n\n"
                f"A fact-checker flagged these claims to fix or qualify:\n{issues}\n\n"
                "Return the corrected report. Do not add unsupported facts; qualify or remove "
                "anything that cannot be substantiated."
            )
    except Exception as exc:  # never let fact-checking abort the run
        emit("Fact-Checker", f"Skipped (error: {exc}).")

    # 4b. Add inline citations from any verified sources ------------------
    sources: list = []
    if fact_check:
        seen = {}
        claim_for_url = {}
        for claim in fact_check.get("claims", []):
            for url in claim.get("sources", []) or []:
                if url and url not in seen:
                    seen[url] = len(seen) + 1
                    claim_for_url[url] = claim.get("claim", "")
        sources = list(seen.keys())
        if sources:
            emit("Editor", f"Adding inline citations for {len(sources)} source(s).")
            sources_block = "\n".join(
                f"{seen[url]}. {url} — supports: {claim_for_url[url]}" for url in sources
            )
            report = citation_agent().run(
                f"Report:\n{report}\n\nSources:\n{sources_block}\n\nAdd the citations now."
            )

    # 5. Critique + revise loop -------------------------------------------
    critic = critic_agent()
    score, rounds = 0, 0
    for round_no in range(1, max_rounds + 1):
        rounds = round_no
        emit("Critic", f"Reviewing draft (round {round_no}).")
        review = _agent_json(
            critic, f"Goal: {goal}\n\nReport:\n{report}",
            fallback={"score": 8, "verdict": "accept", "feedback": ""}, on_event=on_event,
        )
        score = int(review.get("score", 0))
        verdict = review.get("verdict", "revise")
        feedback = review.get("feedback", "")
        emit("Critic", f"Score {score}/10 — {verdict}. {feedback}")

        if verdict == "accept" or round_no == max_rounds:
            break

        emit("Writer", "Revising based on critic feedback.")
        report = writer.run(
            f"Goal: {goal}\n\nCurrent report:\n{report}\n\n"
            f"Editor feedback to address:\n{feedback}\n\nReturn the improved report."
        )

    emit("Done", f"Final score {score}/10 after {rounds} round(s).")
    return RunResult(
        goal=goal, title=title, report=report, score=score, rounds=rounds,
        log=log, fact_check=fact_check, sources=sources,
    )
