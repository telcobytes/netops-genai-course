"""
llm_client.py — one place to swap LLM providers for the whole course repo.

Every module imports `call_llm` and `call_llm_tools` from here instead of hitting
an SDK directly. Change code in THIS FILE ONLY and every module's code follows —
summarizer.py, react_agent.py, noc_assistant.py, rag_pipeline.py, run_eval.py, and
noc_copilot.py never talk to google-genai (or OpenAI/Anthropic) directly.

Defaults to Google's Gemini API (free tier available via Google AI Studio — no
credit card needed to follow along with this course). OpenAI/Anthropic
equivalents are commented below each function if you'd rather use those instead.

Setup:
    pip install google-genai
    export GEMINI_API_KEY="..."          # get one free at aistudio.google.com
"""

import json
import os
import sys
import uuid

_client = None


def _get_client():
    global _client
    if _client is None:
        if not os.environ.get("GEMINI_API_KEY"):
            print("\n" + "=" * 65)
            print("[ERROR] GEMINI_API_KEY environment variable is not set.")
            print("=" * 65)
            print("To run the course labs, set your API key in your terminal session:")
            print("  macOS / Linux:       export GEMINI_API_KEY=\"your_api_key_here\"")
            print("  Windows CMD:         set GEMINI_API_KEY=\"your_api_key_here\"")
            print("  Windows PowerShell:  $env:GEMINI_API_KEY=\"your_api_key_here\"")
            print("\nYou can get a free API key at: https://aistudio.google.com/")
            print("(Google AI Studio free tier does not require a credit card)")
            print("=" * 65 + "\n")
            sys.exit(1)
        from google import genai
        _client = genai.Client()  # reads GEMINI_API_KEY from the environment
    return _client


DEFAULT_MODEL = os.environ.get("COURSE_MODEL", "gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Internal helpers: translate our simple OpenAI-shaped messages/tools into
# what the Gemini SDK expects, and translate Gemini's response back into the
# same shape every module already expects. Nothing outside this file needs to
# know any of this happens.
# ---------------------------------------------------------------------------

class _ToolCallFunction:
    def __init__(self, name, arguments_json_str):
        self.name = name
        self.arguments = arguments_json_str  # kept as a JSON STRING on purpose —
        # every module calls json.loads(tool_call.function.arguments), matching
        # the OpenAI convention, even though Gemini hands us a dict natively.


class _ToolCall:
    def __init__(self, call_id, name, args_dict):
        self.id = call_id
        self.function = _ToolCallFunction(name, json.dumps(args_dict))


class _NormalizedMessage:
    """Mimics the shape of an OpenAI chat-completion message object closely
    enough that noc_assistant.py and noc_copilot.py need zero changes."""

    def __init__(self, content, tool_calls):
        self.content = content
        self.tool_calls = tool_calls or None


def _messages_to_gemini(messages):
    """Convert our list of {"role": ..., "content": ...} dicts (plus, from
    Module 6 onward, raw _NormalizedMessage / tool-result entries) into a
    Gemini `system_instruction` string and a `contents` list.
    """
    from google.genai import types

    system_instruction = None
    raw_contents = []

    for m in messages:
        if isinstance(m, _NormalizedMessage):
            # A previous assistant turn that made tool call(s)
            parts = []
            if m.content:
                parts.append(types.Part(text=m.content))
            for tc in m.tool_calls or []:
                parts.append(types.Part(function_call=types.FunctionCall(
                    name=tc.function.name, args=json.loads(tc.function.arguments)
                )))
            raw_contents.append(types.Content(role="model", parts=parts))
            continue

        role = m.get("role")
        if role == "system":
            system_instruction = m["content"]
        elif role == "user":
            raw_contents.append(types.Content(
                role="user", parts=[types.Part(text=m["content"])]
            ))
        elif role == "assistant":
            raw_contents.append(types.Content(
                role="model", parts=[types.Part(text=m["content"])]
            ))
        elif role == "tool":
            # tool_call_id encodes the function name as "name::uniqueid" —
            # see _ToolCall above — so we can build a proper function_response.
            fn_name = m["tool_call_id"].split("::")[0]
            try:
                payload = json.loads(m["content"])
            except (json.JSONDecodeError, TypeError):
                payload = {"result": m["content"]}
            raw_contents.append(types.Content(
                role="user",
                parts=[types.Part(function_response=types.FunctionResponse(
                    name=fn_name, response={"result": payload}
                ))],
            ))

    # Gemini expects consecutive function-response parts merged into one turn
    # rather than sent as separate back-to-back "user" turns (matters when the
    # model made several parallel tool calls in Module 6/11).
    merged = []
    for content in raw_contents:
        is_fn_response = all(getattr(p, "function_response", None) for p in content.parts)
        if (
            merged
            and is_fn_response
            and all(getattr(p, "function_response", None) for p in merged[-1].parts)
            and merged[-1].role == "user"
        ):
            merged[-1] = types.Content(role="user", parts=merged[-1].parts + content.parts)
        else:
            merged.append(content)

    return system_instruction, merged


def _convert_tools_to_gemini(openai_style_tools):
    from google.genai import types

    declarations = []
    for t in openai_style_tools:
        fn = t["function"]
        declarations.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return [types.Tool(function_declarations=declarations)]


# ---------------------------------------------------------------------------
# Public interface — this is what every module actually imports
# ---------------------------------------------------------------------------

def call_llm(messages, model=None, json_mode=False):
    """Plain chat completion. Returns the assistant's text content.

    messages: list of {"role": "system"|"user"|"assistant", "content": str}
    json_mode: if True, enforces the response is valid JSON (Module 3's technique)
    """
    from google.genai import types

    client = _get_client()
    system_instruction, contents = _messages_to_gemini(messages)
    config = types.GenerateContentConfig(system_instruction=system_instruction)
    if json_mode:
        config.response_mime_type = "application/json"

    response = client.models.generate_content(
        model=model or DEFAULT_MODEL,
        contents=contents,
        config=config,
    )
    return response.text

    # --- OpenAI equivalent ---
    # from openai import OpenAI
    # client = OpenAI()
    # kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    # response = client.chat.completions.create(
    #     model=model or "gpt-4o-mini", messages=messages, **kwargs,
    # )
    # return response.choices[0].message.content

    # --- Anthropic equivalent ---
    # import anthropic
    # client = anthropic.Anthropic()
    # system = next((m["content"] for m in messages if m["role"] == "system"), None)
    # user_messages = [m for m in messages if m["role"] != "system"]
    # response = client.messages.create(
    #     model=model or "claude-sonnet-4-6", max_tokens=1024,
    #     system=system, messages=user_messages,
    # )
    # return response.content[0].text


def call_llm_tools(messages, tools, model=None):
    """Chat completion with tool-calling enabled (Module 6+).

    Returns a message-like object with `.content` and `.tool_calls` — the same
    shape callers would get from an OpenAI response, even though this is
    actually calling Gemini under the hood. tool_calls entries have
    `.id`, `.function.name`, and `.function.arguments` (a JSON string).
    """
    client = _get_client()
    system_instruction, contents = _messages_to_gemini(messages)
    gemini_tools = _convert_tools_to_gemini(tools)

    from google.genai import types
    config = types.GenerateContentConfig(
        system_instruction=system_instruction, tools=gemini_tools,
    )
    response = client.models.generate_content(
        model=model or DEFAULT_MODEL, contents=contents, config=config,
    )

    candidate = response.candidates[0]
    text_parts, tool_calls = [], []
    for part in candidate.content.parts:
        if getattr(part, "text", None):
            text_parts.append(part.text)
        fc = getattr(part, "function_call", None)
        if fc:
            call_id = f"{fc.name}::{uuid.uuid4().hex[:6]}"
            tool_calls.append(_ToolCall(call_id, fc.name, dict(fc.args)))

    return _NormalizedMessage("\n".join(text_parts) if text_parts else None, tool_calls)

    # --- OpenAI equivalent ---
    # from openai import OpenAI
    # client = OpenAI()
    # response = client.chat.completions.create(
    #     model=model or "gpt-4o-mini", messages=messages, tools=tools,
    # )
    # return response.choices[0].message   # already shaped this way natively


def parse_json_response(text):
    """Small helper: parse a JSON-mode response, with a clear error if it fails."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Expected valid JSON from the model but got: {text!r}"
        ) from e
