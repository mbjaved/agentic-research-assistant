# 🧠 Agentic Research Assistant

A small, production-shaped **multi-agent system** built on the Anthropic Claude API. Give it a topic and four specialist agents collaborate to produce a well-structured, source-grounded report — with a critic that reviews and sends the draft back for revision until it meets a quality bar.

Built to demonstrate **agentic orchestration, tool-use, and clean full-stack packaging** (CLI + FastAPI + web UI).

---

## What it does

```
        goal
          │
   ┌──────▼───┐   ┌────────────┐   ┌────────┐   ┌──────────────┐   ┌────────┐
   │ Planner  │──▶│ Researcher │──▶│ Writer │──▶│ Fact-Checker │──▶│ Critic │
   └──────────┘   │ (+ tools)  │   └────────┘   │  (+ tools)   │   └───┬────┘
  breaks goal      gathers facts   drafts the    verifies claims,      scores &
  into subtasks    per subtask     report        flags unsupported     sends back
                                        ▲               │                  │
                                        └── revise ◀─────┴──────────────────┘
                                        (fix flagged claims, then loop to score ≥ 8)
```

- **Planner** — decomposes the goal into focused research subtasks (structured JSON).
- **Researcher** — gathers findings per subtask. Uses a `web_search` tool via Claude's native tool-use when a search key is configured; otherwise falls back to model knowledge.
- **Writer** — composes a clean Markdown report strictly from the findings.
- **Fact-Checker** — extracts the report's key claims and verifies them (using `web_search` when available), flagging anything unsupported or uncertain so the Writer can correct or qualify it before review.
- **Critic** — scores the draft for accuracy, completeness, and clarity, and returns actionable feedback that drives a revision loop.

> **Citations:** when `web_search` is enabled, the Fact-Checker records the source URL for each verified claim, and an **Editor** pass inserts inline `[n]` markers and appends a numbered `## Sources` section — so the final report is traceable to its evidence.

Every step is streamed to a run log so you can *see the agents working* — in the terminal and in the web UI.

---

## Quickstart

```bash
# 1. Setup
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # then add your ANTHROPIC_API_KEY

# 2a. Run from the CLI
python main.py "How will agentic AI change software testing?"
python main.py "Compare RAG vs fine-tuning for enterprise search" --rounds 3 --output report.md

# 2b. Or run the web app
uvicorn app:app --reload
# open http://localhost:8000
```

Optional: set `TAVILY_API_KEY` in `.env` to give the Researcher live web search.

---

## Architecture

| File | Responsibility |
|---|---|
| `config.py` | Model config + cached Anthropic client |
| `agents.py` | `Agent` class (with a tool-use loop) + the five specialist agents |
| `tools.py` | `web_search` tool + Anthropic tool schema |
| `orchestrator.py` | Wires the agents into the plan → research → write → critique loop |
| `main.py` | CLI entry point |
| `app.py` | FastAPI backend + serves the web UI |
| `static/index.html` | Minimal, dependency-free front-end |

**Design choices worth noting**
- **Native tool-use loop** — `Agent.run()` handles Anthropic's `tool_use` / `tool_result` cycle generically, so any agent can be given tools.
- **Graceful degradation** — no search key? The demo still runs end-to-end.
- **Separation of concerns** — agents don't know about each other; the orchestrator owns the workflow, which makes it easy to add or reorder steps.
- **Observability** — a structured event log surfaces every agent action.

---

## Extending it

- Give the Researcher/Fact-Checker more tools (a calculator, a SQL/db reader, a file loader for **RAG over your own docs**).
- Deduplicate and rank citations, or render them as footnotes/hyperlinks in the UI.
- Swap the revision loop for parallel research (`asyncio`) to speed up multi-subtask runs.
- Persist runs to a database and add a history view.

---

## Why this exists

A compact reference for how I build agentic systems: clear agent boundaries, real tool-use, a quality-control loop, and a clean CLI/API/UI wrapper — the same patterns I apply to production Gen AI work.

*Built by Muhammad Bin Javed — Senior Software Engineer (Gen AI, Full-Stack). [LinkedIn](https://www.linkedin.com/in/mbj05)*

## License

MIT
