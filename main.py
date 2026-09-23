"""CLI entry point.

Usage:
    python main.py "How will agentic AI change software testing?"
    python main.py "Compare RAG vs fine-tuning for enterprise search" --rounds 3 --output report.md
"""
import argparse
import sys

from orchestrator import run_research


def _print_event(agent: str, message: str):
    print(f"  [{agent:<10}] {message}")


def main():
    parser = argparse.ArgumentParser(description="Agentic Research Assistant (multi-agent, Claude).")
    parser.add_argument("goal", help="The research goal or question.")
    parser.add_argument("--rounds", type=int, default=2, help="Max critic/revise rounds (default 2).")
    parser.add_argument("--output", help="Write the final report to this Markdown file.")
    args = parser.parse_args()

    print(f"\nGoal: {args.goal}\n" + "-" * 60)
    result = run_research(args.goal, max_rounds=args.rounds, on_event=_print_event)

    print("\n" + "=" * 60 + f"\n# {result.title}\n(score {result.score}/10, {result.rounds} round(s))\n")
    print(result.report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(f"# {result.title}\n\n{result.report}\n")
        print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
