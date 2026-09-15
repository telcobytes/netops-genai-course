"""
gemini_quickstart.py — Module 1: your first API call

The three-line pattern, before any abstraction: initialize a client, call the
model, read the text. This is the code on the Module 1 slide, kept runnable so
you can see the raw call once before llm_client.py wraps it.

NOTE FOR MAINTAINERS: this is the ONLY file in the course that imports the
Gemini SDK directly instead of going through data/llm_client.py. That is
deliberate — the teaching point is that the wrapper hides nothing surprising.
Please do not "fix" this to use call_llm().

Run:
    python module01-summarizer/gemini_quickstart.py

Requires: GEMINI_API_KEY set in your environment. Without it, genai.Client()
raises before any network call — that error means the key is missing, not that
the script is broken.
"""

from google import genai

# 1. Initialize client (reads GEMINI_API_KEY from environment)
client = genai.Client()

# 2. Call the model with live telecom telemetry
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="""Cell CELL-031A at 08:45 AM:
- PRB utilization: 91.8%
- RRC drop rate: 7.6% (threshold: 5%)
- Active users: 201 (planned capacity: 150)
Explain the likely immediate cause in 2 sentences."""
)

# 3. Read the plain-text diagnosis
print(response.text)
