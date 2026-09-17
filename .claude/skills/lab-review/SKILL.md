---
name: lab-review
description: Review one module's hands-on lab in this course (notebook, scripts, exercises, checkpoint, README) for accuracy, whether students can follow and complete it, how well it delivers the concepts, text that should be cut, and tone. Use when asked to review, evaluate or audit a lab or module, e.g. "review the module 6 lab" or "/lab-review module06". Reports findings; changes nothing unless asked.
---

# Lab review

Review a module's lab the way a careful student would experience it, then report
what is wrong, what is confusing, and what to cut. Every finding must be
verified against the files or a real run, never inferred.

The argument names the module (`module06`, `6`, or a path). If none is given, ask
which module.

## 1. Inventory everything a student touches

Read each of these in full, not excerpts:

- The module folder: `moduleNN-*/` — notebook (`*.ipynb`), every script, `README.md`.
- How students get there: the module's rows in `LABS.md` and the root `README.md`
  (which file does the Colab badge open? That is the main path).
- Any checkpoint that follows it: `checkpoints/*/` (`README.md`, `starter.py`,
  `check.py`). Match them by the "After Module N" line.
- The data the lab reads: files under `data/` it imports or loads.
- Anything downstream that imports the module's code (`grep -rn "from <module>"`),
  so a suggested change doesn't break a later module or `module10-eval/run_eval.py`.

Read notebooks cell by cell with outputs:

```bash
python3 -c "
import json; nb = json.load(open('PATH'))
for i, c in enumerate(nb['cells']):
    print(f'--- CELL {i} [{c[\"cell_type\"]}]'); print(''.join(c['source']))"
```

If the user gives a slide deck, read the slides for this module too (text and
speaker notes). `python-pptx` may not be installed; unzip the `.pptx` into the
scratchpad and read `ppt/slides/slideN.xml` and `ppt/notesSlides/`.

## 2. Run what can be run

- Run every script offline first: `env -u GEMINI_API_KEY python3 <script>` (and
  `--offline` where a script has it). Offline runs are free; compare what prints
  with what the text says will print.
- Runs that call the Gemini API cost the user money. Ask before running them,
  and say roughly how many calls it will make.
- To execute notebook code cells outside Colab, skip the `!git clone` cell,
  pre-seed `sys` and `os`, rewrite `/content/netops-genai-course` to the repo
  path, and stub `IPython.display` if IPython isn't installed.

## 3. What to check

**A. Wrong or broken**
- Every claim in text, comments and printed messages against what the code
  does and what the run printed. Hard-coded messages that assert a result
  ("note how often X happens") are a common source of false statements.
- Names, counts and structure: section headings, number of documents or steps,
  file names, function names, folder names that must exist.
- Step numbering and terminology consistent across notebook, scripts, README
  and slides.
- Commands and paths work from the directory the instructions imply.
- API usage matches the module's own teaching (e.g. the right task type or
  parameter, the same one the lesson explains).
- Prerequisites stated consistently: whether an API key is needed, and what
  happens without one.

**B. Exercises**
For every "your turn", checkpoint task and TODO:
- Can a student do it with only what is written? Do they know which file and
  which line to change?
- Will the suggested change actually change the output? Watch for parameters
  or inputs the code ignores in that mode.
- Is the premise true? (A query said to "fit two incidents" must fit two.)
- Does it contradict another instruction elsewhere (e.g. writing into a corpus
  that a later module is graded against)?
- Does the pass condition depend on something unstated, such as which engine
  or model is available?

**C. Concept delivery**
- Is there one running example, or does the example change between files?
- Is the key idea stated explicitly, or only implied by code?
- Overclaims and misconceptions: scores read as confidence, a single run read
  as a law, "fixes" credited to the wrong cause.
- Does the main path (the notebook) teach everything the slides build to?
- Would predict-then-reveal land harder than stating the answer first?

**D. Text to cut**
- Changelog narration: "used to", "CORRECTION", dated stories about how the
  course was built or which bug was found. Keep the reasoning, in the present
  tense; the history belongs in git.
- Instructor-only notes in student files ("do not quote a result you have not run").
- Slide numbers in code or notebooks: they break whenever the deck changes.
- References to modules the student hasn't reached yet.
- The same rule or aphorism repeated in full in many places.

**E. Tone**
Written from the student's side, present tense, specific. Confident is good;
defensive or self-referential is not. Check punchline density in comments.

## 4. Verify before reporting

For each finding, have the evidence in hand: the `file:line`, the quoted text,
and where relevant the output that contradicts it. Drop anything you could not
confirm, or mark it clearly as unverified.

## 5. Report

Report in the conversation, most severe first. Don't edit files.

1. **Overall:** two or three sentences — is the lab sound, and what are the
   main problems?
2. **Wrong or broken (fix first):** a table with `#`, where (`file:line` or
   notebook cell), and the problem stated plainly with the evidence.
3. **Concept delivery:** bullets, each with a concrete suggested change.
4. **Text to cut or move to instructor notes:** bullets with `file:line`.
5. **Tone:** what works, and the patterns that get in the way.
6. **Suggested order:** the sequence you'd fix things in, main student path first.

End by offering to make the changes.

## If asked to make the changes

- Branch first if on `main`. One commit per area (for example the code, the
  exercises, the notebook), with messages in the style of `git log`: a plain
  subject line, then what was wrong and what changed.
- For comment-only edits to Python, confirm no logic changed by comparing each
  function's AST with its docstring stripped against the original.
- Re-run every changed script offline. Re-run anything that needs the API only
  with the user's go-ahead, and update any text the real output contradicts.
- Keep notebook JSON formatting as it was (`indent=1`, trailing newline) so
  the diff stays readable.
