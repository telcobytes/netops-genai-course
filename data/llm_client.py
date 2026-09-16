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

Self-check:
    python data/llm_client.py              # which models your key can actually use
    python data/llm_client.py --call       # ...and one real call to prove it
    python data/llm_client.py --embeddings # which embedding models it can use
"""

import json
import logging
import os
import sys
import uuid


class _DropAFCAdvisory(logging.Filter):
    """google-genai logs an advisory about automatic function calling on every
    tool-enabled call. It is not an error and there is nothing for a student to
    fix, but it prints above the output and reads like one. Drop just that line.
    """

    def filter(self, record):
        return "automatic function calling" not in record.getMessage().lower()


def _silence_afc_advisory():
    names = set(logging.root.manager.loggerDict) | {
        "google_genai.models", "google_genai", "google.genai.models",
    }
    for name in names:
        if "genai" in name:
            logging.getLogger(name).addFilter(_DropAFCAdvisory())

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
        _silence_afc_advisory()   # after the import, so its loggers exist
        _client = genai.Client()  # reads GEMINI_API_KEY from the environment
    return _client


# ---------------------------------------------------------------------------
# Which model we call
# ---------------------------------------------------------------------------
# Google retires models on its own schedule, and it closes a model to NEW keys
# before the published shutdown date. In September 2026 `gemini-2.5-flash` —
# which this course originally pinned — started returning
#     404 NOT_FOUND: This model ... is no longer available to new users
# for keys created after the cutoff, while the docs still listed it as stable.
# Every new student has a new key, so a hard-pinned model is a trap.
#
# So: an ordered list of Flash-tier models that are on Gemini's free tier, and
# a client that walks down it when the one it asked for has been retired. You
# override the whole thing with COURSE_MODEL if you want a specific model:
#     export COURSE_MODEL="gemini-3.8-flash"
MODEL_CANDIDATES = [
    "gemini-3.6-flash",        # Google's own recommended replacement for 2.5-flash
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",        # last, for older keys where it still works
]

# Set COURSE_MODEL to force one model and disable the fallback entirely.
COURSE_MODEL = os.environ.get("COURSE_MODEL")
DEFAULT_MODEL = COURSE_MODEL or MODEL_CANDIDATES[0]

_resolved = None      # the model that worked last, so we stop re-probing
_retired = set()      # models this key has been told it cannot use


def _model_order():
    if COURSE_MODEL:
        return [COURSE_MODEL]
    order = [_resolved] if _resolved else []
    order += [m for m in MODEL_CANDIDATES if m != _resolved and m not in _retired]
    return order


def _is_retired(exc):
    """True when the error means 'this model is gone', not 'your call was bad'."""
    msg = str(exc).lower()
    return ("404" in msg or "not_found" in msg) and (
        "no longer available" in msg or "not found" in msg or "model" in msg
    )


def _generate(client, model, contents, config):
    """client.models.generate_content, with one safeguard: if the model has been
    retired, move to the next candidate rather than dying with a traceback."""
    global _resolved
    if model:                       # caller named a model explicitly — respect it
        return client.models.generate_content(
            model=model, contents=contents, config=config,
        )
    tried = []
    for candidate in _model_order():
        try:
            response = client.models.generate_content(
                model=candidate, contents=contents, config=config,
            )
            if candidate != _resolved:
                if tried:
                    print("[llm_client] not available to this key: "
                          f"{', '.join(tried)} — using {candidate} instead.")
                _resolved = candidate
            return response
        except Exception as exc:
            if not _is_retired(exc):
                raise
            _retired.add(candidate)
            tried.append(candidate)
    _no_model_left(tried)


def _no_model_left(tried):
    print("\n" + "=" * 65)
    print("[ERROR] None of the course's models are available to your API key.")
    print("=" * 65)
    print("Tried: " + ", ".join(tried))
    print("\nGoogle retires models faster than a recorded course can be re-cut,")
    print("so this is expected eventually and it is a one-line fix.")
    print("\n1. See what your key can actually use:")
    print("     python data/llm_client.py")
    print("\n2. Pick a Flash model from that list and pin it:")
    print("     export COURSE_MODEL=\"<the model id>\"")
    print("\nNothing else in the course needs to change — every module reads")
    print("this file, so one environment variable fixes all of them.")
    print("=" * 65 + "\n")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Embeddings — the same retirement problem, and the same shape of answer
# ---------------------------------------------------------------------------
# Module 4 embeds the knowledge base to do dense semantic retrieval. Embedding
# models get retired exactly like generation models do: on 16 Sep 2026
# `text-embedding-004` — which this course had pinned — started returning
#     404 NOT_FOUND: models/text-embedding-004 is not found for API version
#     v1beta, or is not supported for embedContent
# So embeddings live here now, behind the same candidate list, rather than
# reaching for the SDK from rag_pipeline.py. Override with COURSE_EMBEDDING_MODEL.
# Newest stable first, oldest last — the opposite of how this course was bitten
# twice, where the pinned model was the one that aged out.
EMBEDDING_CANDIDATES = [
    "gemini-embedding-2",
    "gemini-embedding-001",
    "text-embedding-005",
    "text-embedding-004",      # retired 16 Sep 2026; kept last for older keys
]

COURSE_EMBEDDING_MODEL = os.environ.get("COURSE_EMBEDDING_MODEL")

# Pinned so retrieval behaviour does not shift underneath the lecture when the
# model changes: gemini-embedding-* default to 3072 dimensions, the older
# text-embedding-* models to 768. Asking for 768 explicitly keeps every
# candidate producing the same shape, and keeps the deck's "768-dimensional"
# claim true. Cosine similarity normalizes anyway, so truncation is safe here.
EMBEDDING_DIMENSIONS = 768

_resolved_embedding = None
_retired_embeddings = set()


def _discover_embedding_model(client):
    """Last resort: ask the API what it actually has. Beats a hardcoded list
    that a future retirement will invalidate all over again."""
    try:
        for m in client.models.list():
            actions = [str(a) for a in (getattr(m, "supported_actions", None) or [])]
            if any("embed" in a.lower() for a in actions):
                return m.name.split("/", 1)[-1]
    except Exception:
        pass
    return None


_no_batch = set()          # models observed to return one vector for many inputs


def _embed_call(client, model, texts, cfg):
    """One embed_content call, with the count guaranteed to match the input.

    Not every embedding model accepts a batch. Some return ONE embedding for a
    list of many, and the caller in rag_pipeline zips chunks against vectors —
    where zip() silently truncates to the shorter list. That turned 24 ranked
    chunks into 1, so every query returned chunks[0] and retrieval stopped
    ranking anything at all. It looked like it worked: two documents asked for,
    one plausible document returned, no error anywhere.
    """
    def one(text):
        return client.models.embed_content(
            model=model, contents=[text], config=cfg).embeddings[0].values

    if len(texts) == 1 or model in _no_batch:
        return [one(t) for t in texts]

    result = client.models.embed_content(model=model, contents=texts, config=cfg)
    vectors = [e.values for e in result.embeddings]
    if len(vectors) == len(texts):
        return vectors

    # This model will not batch. Remember that, so we stop wasting a call on it,
    # then embed one at a time — slower, but a short vector list is a correctness
    # bug and a slow loop is only a slow loop.
    _no_batch.add(model)
    return [one(t) for t in texts]


def embed_texts(texts, task_type=None):
    """Embed a list of strings, returning one vector per input string.

    Walks EMBEDDING_CANDIDATES when a model has been retired, then asks the API
    what it has. Raises with a readable instruction block when nothing works —
    deliberately loud, because a silent fall back to keyword matching would let
    a lab claim semantic retrieval while doing something else entirely.

    task_type matters more than it looks. Retrieval is ASYMMETRIC: a short query
    and a long passage are not the same kind of text, and Gemini's embedding
    models encode them differently when told which is which. Pass
    "RETRIEVAL_DOCUMENT" for the corpus and "RETRIEVAL_QUERY" for the question.
    Leaving it unset embeds both the same way and measurably flattens the
    ranking — which is the opposite of what Module 4 is trying to demonstrate.
    """
    global _resolved_embedding
    client = _get_client()

    if COURSE_EMBEDDING_MODEL:
        order = [COURSE_EMBEDDING_MODEL]
    else:
        order = [_resolved_embedding] if _resolved_embedding else []
        order += [m for m in EMBEDDING_CANDIDATES
                  if m != _resolved_embedding and m not in _retired_embeddings]

    from google.genai import types
    cfg = types.EmbedContentConfig(
        output_dimensionality=EMBEDDING_DIMENSIONS, task_type=task_type)

    tried = []
    for candidate in order:
        try:
            vectors = _embed_call(client, candidate, texts, cfg)
            if candidate != _resolved_embedding:
                if tried:
                    print("[llm_client] embedding models not available to this key: "
                          f"{', '.join(tried)} — using {candidate} instead.")
                _resolved_embedding = candidate
            return vectors
        except Exception as exc:
            if not _is_retired(exc):
                raise
            _retired_embeddings.add(candidate)
            tried.append(candidate)

    discovered = _discover_embedding_model(client)
    if discovered and discovered not in tried:
        vectors = _embed_call(client, discovered, texts, cfg)
        print(f"[llm_client] none of the course's embedding models are available; "
              f"discovered {discovered} on your key and used that.")
        _resolved_embedding = discovered
        return vectors

    raise RuntimeError(
        "No embedding model available to this API key.\n"
        + "Tried: " + (", ".join(tried) or "(none)") + "\n"
        "Google retires embedding models the same way it retires chat models.\n"
        "Find one your key can use:\n"
        "    python data/llm_client.py --embeddings\n"
        "then pin it:\n"
        "    export COURSE_EMBEDDING_MODEL=\"<the model id>\"\n"
    )


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
    def __init__(self, call_id, name, args_dict, thought_signature=None):
        self.id = call_id
        self.function = _ToolCallFunction(name, json.dumps(args_dict))
        # Gemini 3.x thinking models attach an opaque `thought_signature` to each
        # function_call part, and REQUIRE it back, byte for byte, when that turn
        # is replayed in the conversation history. Drop it and the next request
        # fails with 400 INVALID_ARGUMENT:
        #     "Function call is missing a thought_signature in functionCall parts"
        # It is provider-specific and meaningless to the modules, so it rides
        # along here rather than appearing in the OpenAI-shaped interface.
        self.thought_signature = thought_signature


class _NormalizedMessage:
    """Mimics the shape of an OpenAI chat-completion message object closely
    enough that noc_assistant.py and noc_copilot.py need zero changes."""

    def __init__(self, content, tool_calls, raw_content=None):
        self.content = content
        self.tool_calls = tool_calls or None
        # The provider's own Content object for this turn. Replaying it verbatim
        # preserves thought signatures and any future per-part metadata Google
        # adds, which reconstructing from name+args cannot.
        self.raw_content = raw_content


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
            # A previous assistant turn that made tool call(s). Replay the
            # provider's own Content when we have it — that keeps the thought
            # signatures Gemini 3.x demands back, and anything else it attached.
            if getattr(m, "raw_content", None) is not None and m.raw_content.parts:
                raw_contents.append(m.raw_content)
                continue
            # Hand-built message (the capstone does this): rebuild, carrying the
            # signature across when the caller preserved one.
            parts = []
            if m.content:
                parts.append(types.Part(text=m.content))
            for tc in m.tool_calls or []:
                parts.append(types.Part(
                    function_call=types.FunctionCall(
                        name=tc.function.name,
                        args=json.loads(tc.function.arguments),
                    ),
                    thought_signature=getattr(tc, "thought_signature", None),
                ))
            if parts:   # Gemini rejects a Content with no parts at all
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
        # `all([])` is True, so an empty parts list would masquerade as a
        # function-response turn and get merged into the previous one.
        is_fn_response = bool(content.parts) and all(
            getattr(p, "function_response", None) for p in content.parts
        )
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

    response = _generate(client, model, contents, config)
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
    response = _generate(client, model, contents, config)

    candidate = response.candidates[0] if response.candidates else None
    content = getattr(candidate, "content", None) if candidate else None
    if content is None or not content.parts:
        # The model returned nothing usable — a safety stop, or it ran out of
        # output tokens mid-thought. Say so instead of raising AttributeError on
        # NoneType, which tells a student nothing.
        reason = getattr(candidate, "finish_reason", None) if candidate else None
        return _NormalizedMessage(
            f"[no content returned by the model (finish_reason={reason}). "
            f"Try a shorter question, or raise the output token limit.]",
            [],
        )

    text_parts, tool_calls = [], []
    for part in content.parts:
        if getattr(part, "text", None):
            text_parts.append(part.text)
        fc = getattr(part, "function_call", None)
        if fc:
            call_id = f"{fc.name}::{uuid.uuid4().hex[:6]}"
            tool_calls.append(_ToolCall(
                call_id, fc.name, dict(fc.args or {}),
                thought_signature=getattr(part, "thought_signature", None),
            ))

    return _NormalizedMessage(
        "\n".join(text_parts) if text_parts else None,
        tool_calls,
        raw_content=content,
    )

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


if __name__ == "__main__":
    # `python data/llm_client.py` is the course's self-check. Run it whenever a
    # lab fails in a way that looks like it is about the model rather than your
    # code. It makes no billable call unless you pass --call.
    print("Model candidates, in the order this file tries them:")
    for m in MODEL_CANDIDATES:
        print(f"    {m}")
    if COURSE_MODEL:
        print(f"\nCOURSE_MODEL is set to {COURSE_MODEL!r}, so only that one is used.")
    else:
        print(f"\nCOURSE_MODEL is not set, so the default is {DEFAULT_MODEL!r}.")

    print("\nModels your key can see that can generate text:")
    client = _get_client()
    visible = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if not actions or "generateContent" in actions:
            name = m.name.split("/", 1)[-1]
            visible.append(name)
            print(f"    {name}")
    if not visible:
        print("    (none returned — check that GEMINI_API_KEY is the right key)")
    else:
        usable = [m for m in MODEL_CANDIDATES if m in visible]
        print("\nOf the course's candidates, your key can see: "
              + (", ".join(usable) if usable else "NONE"))
        if not usable:
            print("Pick a Flash model from the list above and set COURSE_MODEL to it.")

    if "--embeddings" in sys.argv:
        print("\nEmbedding models your key can see:")
        found = []
        for m in client.models.list():
            actions = [str(a) for a in (getattr(m, "supported_actions", None) or [])]
            if any("embed" in a.lower() for a in actions):
                name = m.name.split("/", 1)[-1]
                found.append(name)
                print(f"    {name}")
        if not found:
            print("    (none) — this key cannot embed at all.")
        else:
            usable = [m for m in EMBEDDING_CANDIDATES if m in found]
            print("\nOf the course's embedding candidates, your key can see: "
                  + (", ".join(usable) if usable else "NONE"))
            if not usable:
                print(f"Set COURSE_EMBEDDING_MODEL to one of the above, "
                      f"e.g. export COURSE_EMBEDDING_MODEL=\"{found[0]}\"")

    if "--call" in sys.argv:
        print("\nMaking one real call to confirm end to end...")
        print(call_llm([{"role": "user", "content": "Reply with the word ready."}]))
