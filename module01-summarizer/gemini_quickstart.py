"""
gemini_quickstart.py — Module 1: your first API call

The three-line pattern, before any abstraction: initialize a client, call the
model, read the text. This is the code on the Module 1 slide, kept runnable so
you can see the raw call once before llm_client.py wraps it.

NOTE FOR MAINTAINERS: this is the ONLY file in the course that imports the
Gemini SDK directly instead of going through data/llm_client.py. That is
deliberate — the teaching point is that the wrapper hides nothing surprising.
Please do not "fix" this to use call_llm().

It imports TWO things from llm_client, and neither one is the call itself:

  resolve_model()   returns a model id this key can actually use. Writing a
                    model id in here instead would re-create the failure this
                    course has already shipped twice — `gemini-2.5-flash` and
                    `text-embedding-004` were both retired while the docs still
                    called them stable, and a pinned name turns that into a 404
                    in the first lab a student ever runs.
  require_api_key() prints the same missing-key message every other lab prints.
                    Without it, genai.Client() answers a missing key with an SDK
                    traceback — a bad first impression in the first script of
                    the course, and the one error a beginner cannot yet read.

The generate_content call below is still the raw SDK call. That is the point.

Run:
    python module01-summarizer/gemini_quickstart.py

    Needs GEMINI_API_KEY. Without it, the run prints how to set one and stops —
    there is no offline mode here.
"""

import os
import sys

from google import genai

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
from llm_client import require_api_key, resolve_model  # noqa: E402

# 0. Fail readably, not with a stack trace, when the key is missing.
require_api_key()

# 1. Initialize client (reads GEMINI_API_KEY from environment)
client = genai.Client()

# 2. Call the model with live telecom telemetry
response = client.models.generate_content(
    model=resolve_model(),
    contents="""Cell CELL-031A at 08:45 AM:
- PRB utilization: 91.8%
- RRC drop rate: 7.6% (threshold: 5%)
- Active users: 201 (planned capacity: 150)
Explain the likely immediate cause in 2 sentences."""
)

# 3. Read the plain-text diagnosis
print(response.text)
