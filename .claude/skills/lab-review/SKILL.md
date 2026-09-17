---
name: lab-review
description: Review one module's hands-on lab in this course (notebook, scripts, exercises, checkpoint, README) and, when a slide deck is given, the module's slides against it. Checks accuracy against the code and data, whether students can follow and complete it, concept delivery for telecom engineers new to AI, text to cut, and tone. Use when asked to review, evaluate or audit a lab, module or its slides, e.g. "review the module 6 lab" or "/lab-review module06 <deck.pptx>". Reports findings; changes nothing unless asked.
---

# Lab review

Review a module's lab the way a careful student would experience it, then report
what is wrong, what is confusing, and what to cut. Every finding must be
verified against the files, the data or a real run, never inferred.

**Arguments:** the module (`module06`, `6`, or a path), and optionally a deck
(`.pptx`). If no module is given, ask which one.

**The audience:** telecom and NOC engineers. They know PRBs, RRC and alarms; they
may not know what an embedding, a vector, cosine similarity or a prompt is.
Judge every explanation from that side of the screen.

## 1. Inventory everything a student touches

Read each of these in full, not excerpts:

- The module folder: `moduleNN-*/` — notebook (`*.ipynb`), every script, `README.md`.
- How students get there: the module's rows in `LABS.md` and the root
  `README.md`. Which file does the Colab badge open? That is the main path, and
  it must teach everything the slides build to.
- Any checkpoint that follows it: `checkpoints/*/` (`README.md`, `starter.py`,
  `check.py`), matched by the "After Module N" line.
- The data the lab reads: files under `data/` it imports or loads.
- Anything downstream that imports the module's code
  (`grep -rn "from <module>"`), so a suggested change doesn't break a later
  module or `module10-eval/run_eval.py`.
- Other working copies the user mentions. Run `git status` there too: an
  uncommitted edit to the same file will collide with your changes on merge.
- Any script that produced numbers quoted on a slide. If it isn't committed to
  this repo, students can't reproduce the slide; say so.

Read notebooks cell by cell:

```bash
python3 -c "
import json; nb = json.load(open('PATH'))
for i, c in enumerate(nb['cells']):
    print(f'--- CELL {i} [{c[\"cell_type\"]}]'); print(''.join(c['source']))"
```

### The deck

`python-pptx` may not be installed. Unzip into the scratchpad and use the bundled
script, which reads slides in **presentation order**. File names like
`slide37.xml` stop matching the slide number once slides are inserted:

```bash
unzip -oq deck.pptx -d <scratchpad>/deck
python3 .claude/skills/lab-review/scripts/deck_dump.py <scratchpad>/deck 33 44
```

Find the module's range by its "MODULE N" title slide and the next module's
title slide. Read the speaker notes as carefully as the slides; instructors
read them aloud.

Given a newer version of a deck you've already seen, diff the two with
`deck_dump.py <dir> --titles` for each and compare, to catch slides that were
added, moved or lost. Check whether pictures are the intended files
(`cmp ppt/media/imageN.svg <file>`).

## 2. Run what can be run

- Run every script offline first: `env -u GEMINI_API_KEY python3 <script>` (and
  `--offline` where a script has it). Offline runs are free. Compare what prints
  with what the text and the slides say will print.
- Runs that call the Gemini API cost the user money. Ask before running them,
  and say roughly how many calls it will make. Embedding N chunks is N calls.
- Offline bag-of-words and Gemini embeddings can rank differently. A result
  from one engine says nothing about the other. Note which engine every number
  you quote came from.
- To execute notebook code cells outside Colab, skip the `!git clone` cell,
  pre-seed `sys` and `os`, rewrite `/content/netops-genai-course` to the repo
  path, and stub `IPython.display` if IPython isn't installed.

## 3. What to check

**A. Wrong or broken**
- Every claim in text, comments, printed messages, slides and speaker notes
  against what the code does and what the run printed. Hard-coded messages
  that assert a result ("note how often X happens") are a common source of
  false statements.
- **Quotes and data claims against the source files.** `grep` every quoted
  phrase: it must appear verbatim in the file it's attributed to. Check "this
  document never uses the word X" claims with a word count. A slide that
  misquotes the knowledge base is disproved by the first student who opens it.
- **Numbers.** Every score or result needs a source: which script, which
  engine, which date. If you can't find one, mark it unverified.
- Names, counts and structure: section headings, number of documents, chunks
  or steps, file and function names, folders that must exist.
- Code on slides against the real code: signatures, return values, the line
  that does the work.
- Step numbering and terminology consistent across notebook, scripts, README,
  slides and the recap slide.
- Cross-references: "N slides from now", "the previous slide", and slide
  numbers written in code comments. All of them shift when slides are added.
- Commands and paths work from the directory the instructions imply.
- API usage matches the module's own teaching (e.g. the task type or
  parameter the lesson explains).
- Prerequisites stated consistently everywhere: whether an API key is needed
  for the script, the notebook and the checkpoint, and what happens without one.

**B. Exercises**
For every "your turn", checkpoint task and TODO:
- Can a student do it with only what is written? Do they know which file and
  which line to change?
- Will the suggested change actually change the output? Watch for parameters
  or inputs the code ignores in that mode.
- Is the premise true? A query said to "fit two incidents" must fit two; a
  topic said to be missing from the knowledge base must be missing.
- Does it contradict another instruction elsewhere (e.g. writing into a corpus
  that a later module is graded against)?
- Does the pass condition depend on something unstated, such as which engine
  is available? Can it be passed by gaming the engine (keyword stuffing)?

**C. Concept delivery**
- **One running example.** The script, notebook, exercises, slides and recap
  should follow the same scenario. A different example in each file is a
  common, silent source of confusion.
- Is the key idea stated explicitly, or only implied by code? Look for the part
  that confused you or the user while reviewing; students will hit it too.
- Overclaims and misconceptions: similarity scores read as confidence, one run
  read as a law, "fixes" credited to the wrong cause, "similar" read as "same
  diagnosis".
- When a measurement contradicts the intended claim, the claim changes, not the
  example. Don't swap in phrases until one happens to work; report what was
  measured, including the cases that didn't follow the pattern.
- Would predict-then-reveal land harder than stating the answer first?
- **Plain-language explanations in the code.** Does each step say, in words a
  NOC engineer would use, what it does and why, with a real example from the
  course data (an actual chunk, an actual query string, an actual ranking)?
  Missing explanations are a finding.

**D. Text to cut**
- Changelog narration: "used to", "CORRECTION", dated stories about how the
  course was built or which bug was found. Keep the reasoning, in the present
  tense; the history belongs in git.
- Instructor-only notes in student files ("do not quote a result you have not run").
- Slide numbers in code or notebooks.
- References to modules the student hasn't reached yet.
- Speaker notes that retell a story another slide's notes already tell.
- The same rule or aphorism repeated in full in many places.

Don't confuse the two kinds of comment: history gets cut, explanation stays.
A long comment that teaches the concept with an example is not clutter.

**E. Tone**
Written from the student's side, present tense, specific. Confident is good;
defensive, self-referential or jokey at the student's expense ("instead of a
refund") is not. Check punchline density.

## 4. Verify before reporting

For each finding, have the evidence in hand: the `file:line` or slide title,
the quoted text, and the file content or output that contradicts it. Drop
anything you could not confirm, or mark it clearly as unverified.

## 5. Report

Report in the conversation, most severe first. Don't edit files.

1. **Overall:** two or three sentences — is the lab sound, and what are the
   main problems?
2. **Wrong or broken (fix first):** a table with `#`, where (`file:line`,
   notebook cell, or slide title), and the problem stated plainly with evidence.
3. **Slides vs lab** (when a deck was given): mismatches, grouped by slide title.
4. **Concept delivery:** bullets, each with a concrete suggested change.
5. **Text to cut or move to instructor notes:** bullets with locations.
6. **Tone:** what works, and the patterns that get in the way.
7. **Suggested order:** the sequence you'd fix things in, main student path first.

End by offering to make the changes.

## If asked to make the changes

**Code, notebooks and READMEs**
- Branch first if on `main`. One commit per area (for example the code, the
  exercises, the notebook), with messages in the style of `git log`: a plain
  subject line, then what was wrong and what changed.
- When adding explanations, write for the audience above: what the step does,
  why, and a real example computed from the course data (run it; don't
  invent the output).
- For comment-only edits to Python, confirm no logic changed: compare the AST
  of the whole module with docstrings stripped against the original. If a
  user-facing string changed too, confirm that's the only other difference.
- Re-run every changed script offline. Re-run anything that needs the API only
  with the user's go-ahead, and update any text the real output contradicts.
- Keep notebook JSON formatting as it was (`indent=1`, trailing newline) so
  the diff stays readable.

**Slides**
The deck is edited outside this repo. Produce two things:
- **Diagrams** as standalone SVG files next to the deck, in the deck's own
  palette and fonts (read them from `ppt/slides/slideN.xml` and
  `ppt/theme/theme1.xml`). Every fact in a diagram is checked against the data
  or a real run before it's drawn.
- **A prompt for Cowork** (or whoever edits the deck), written for a reader with
  no context:
  - never overwrite the deck; save a new timestamped file
  - find slides by title, not number
  - give exact old text and exact new text; if old text isn't found, skip it
    and report it rather than guessing
  - insert diagrams as SVG, and stop rather than substitute a PNG
  - render the changed slides and check nothing is clipped; confirm the slide count
  - report the new filename and anything it couldn't do

When the edited deck comes back, check it: each requested change applied,
pictures identical to the files (`cmp`), slide count and order as expected,
cross-references still right, and nothing new that contradicts the lab.
