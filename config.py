"""Central configuration and the shared Anthropic client."""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

# Set CLAUDE_MODEL in your .env to any model your API key can access,
# e.g. claude-sonnet-4-5, claude-sonnet-5, or claude-3-5-sonnet-20241022.
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

# A cheaper/faster model for lightweight steps (critic scoring, planning).
CLAUDE_FAST_MODEL = os.getenv("CLAUDE_FAST_MODEL", CLAUDE_MODEL)

MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2000"))

# The Writer and citation Editor output a whole report, so they need more room —
# otherwise the report (and its Sources section) gets cut off mid-sentence.
WRITER_MAX_TOKENS = int(os.getenv("WRITER_MAX_TOKENS", "4000"))


@lru_cache(maxsize=1)
def get_client():
    """Return a cached Anthropic client. Raises a clear error if no key is set."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    # Bounded retries + per-request timeout so a bad call fails fast instead of
    # hanging for minutes on backoff.
    return anthropic.Anthropic(api_key=api_key, max_retries=2, timeout=60.0)
