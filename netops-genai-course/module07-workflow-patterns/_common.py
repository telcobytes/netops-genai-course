"""
_common.py — shared helpers for the Module 7 workflow-pattern labs.

Two jobs:
  1. Put `data/` on the import path so every pattern can use the same four
     mock tools and the same guardrails as the rest of the course.
  2. Provide `ask()` — a thin wrapper over call_llm that falls back to canned
     responses when there's no API key, so the SHAPE of each pattern is
     runnable offline. The orchestration is the lesson here; the model is a
     component inside it.

Every script in this folder accepts --mock to force the offline path.
"""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))

from llm_client import call_llm  # noqa: E402

CYAN, YELLOW, GREEN, RED, BOLD, RESET = (
    "\033[96m", "\033[93m", "\033[92m", "\033[91m", "\033[1m", "\033[0m",
)


def offline() -> bool:
    """True when we should use canned responses instead of a live model."""
    return "--mock" in sys.argv or not os.environ.get("GEMINI_API_KEY")


def ask(prompt: str, mock: str = "") -> str:
    """One model call. Returns `mock` verbatim when running offline."""
    if offline():
        return mock.strip()
    return call_llm([{"role": "user", "content": prompt}]).strip()


def banner(title: str, subtitle: str = "") -> None:
    print(f"\n{BOLD}{'=' * 72}{RESET}")
    print(f"{BOLD}{title}{RESET}")
    if subtitle:
        print(subtitle)
    print(f"{BOLD}{'=' * 72}{RESET}")
    if offline():
        print(f"{YELLOW}[offline mode — canned model responses; set GEMINI_API_KEY for live]{RESET}")


def step(n, label: str, detail: str = "") -> None:
    print(f"\n{CYAN}[{n}] {label}{RESET}" + (f"\n    {detail}" if detail else ""))
