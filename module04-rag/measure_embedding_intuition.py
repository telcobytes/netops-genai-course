#!/usr/bin/env python3
"""
measure_embedding_intuition.py — the numbers behind the Module 4 intuition slide.

    GEMINI_API_KEY=... python module04-rag/measure_embedding_intuition.py            # the four phrases
    GEMINI_API_KEY=... python module04-rag/measure_embedding_intuition.py --probe    # the 2x2 probe

    Without a key it still prints the shared-word counts and the bag-of-words
    matrix — the half that needs no model — then stops before the dense numbers.

THE FOUR PHRASES (default)
    A  PRB saturation at the cell edge          incident_001's language
    B  site overloaded during evening peak      the ticket's language
    C  VoLTE calls dropping after handover      incident_003's language
    D  invoice dispute on account 4471          not a network fault

No pair shares a content word, so bag-of-words scores every pair 0.00 and cannot
rank any of them. The dense model can. Measured, it ranked A-C (0.79)
ABOVE A-B (0.61), with A-D last (0.51) -- that is, a DIFFERENT fault written in
radio jargon beat the SAME fault written in plain operational language.

That result was not the one expected, and it is the more useful one: dense
similarity tracks topic and register, not diagnosis. It is the phrase-level
version of the failure EVAL-03 shows at document level, where the VoLTE
postmortem wins a congestion question.

THE PROBE (--probe)
Three anchors, each paired with four partners crossed on two axes -- same fault
or not, same register or not. If register really does dominate, the mean of
"different fault, same register" beats "same fault, different register" across
all three anchors and not just the one phrase pair above. One pair is an
anecdote; this is the smallest thing that is not.
"""
import argparse
import datetime
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "data"))
sys.path.append(HERE)

import rag_pipeline as R  # noqa: E402

BOLD, DIM, GRN, RED, OFF = "\033[1m", "\033[2m", "\033[92m", "\033[91m", "\033[0m"

PHRASES = [
    ("A", "PRB saturation at the cell edge",     "incident_001 · the congestion postmortem"),
    ("B", "site overloaded during evening peak", "the ticket, in the field team's words"),
    ("C", "VoLTE calls dropping after handover", "incident_003 · a different cell"),
    ("D", "invoice dispute on account 4471",     "not a network fault at all"),
]

# anchor -> (partner, same_fault, same_register)
PROBE = {
    "PRB saturation at the cell edge": [
        ("sustained PRB utilisation above the planned threshold on the serving cell", 1, 1),
        ("site overloaded during evening peak",                                       1, 0),
        ("VoLTE calls dropping after handover",                                       0, 1),
        ("customers say their calls cut off when they move",                          0, 0),
    ],
    "RRC connection setup failures on the serving cell": [
        ("elevated RRC setup failure rate with NAS reject causes logged",              1, 1),
        ("phones cannot get on the network at that site",                              1, 0),
        ("backhaul packet delay variation exceeding the jitter budget",                0, 1),
        ("the internet feels slow there in the evenings",                              0, 0),
    ],
    "backhaul latency and jitter above budget on the transport link": [
        ("packet delay variation on the transport hop exceeding its budget",           1, 1),
        ("the link to that site keeps lagging",                                        1, 0),
        ("PRB utilisation sustained above the planned threshold",                      0, 1),
        ("too many people connected to that cell at once",                             0, 0),
    ],
}
CELL = {(1, 1): "same fault, same register",
        (1, 0): "same fault, PLAIN words",
        (0, 1): "different fault, same register",
        (0, 0): "different fault, plain words"}


def need_key():
    if os.environ.get("GEMINI_API_KEY"):
        return False
    print("\n   GEMINI_API_KEY is not set. The dense numbers are the whole point "
          "of this script.")
    return True


def embed(texts):
    vecs = R.embed_with_gemini_api(texts, "RETRIEVAL_DOCUMENT")
    assert len(vecs) == len(texts), f"got {len(vecs)} vectors for {len(texts)} texts"
    return dict(zip(texts, vecs))


def four_phrases():
    print(f"{BOLD}Four phrases{OFF}")
    for k, t, why in PHRASES:
        print(f"   {k}  {t:<42} {DIM}{why}{OFF}")
    shared = {(a[0], b[0]): set(R._tokenize(a[1])) & set(R._tokenize(b[1]))
              for a, b in itertools.combinations(PHRASES, 2)}
    print(f"\n{BOLD}Content words shared by each pair{OFF}")
    for (ka, kb), w in shared.items():
        print(f"   {ka} vs {kb}:  {len(w)}   {sorted(w) or ''}")
    if any(shared.values()):
        print(f"\n   {RED}A pair shares a word — the keyword matrix is no longer a "
              f"clean zero. Reword before quoting this.{OFF}")
    vocab = sorted({w for _, t, _ in PHRASES for w in R._tokenize(t)})
    bow = lambda x, y: R._cosine_similarity(R._vectorize(R._tokenize(x), vocab),
                                            R._vectorize(R._tokenize(y), vocab))
    print(f"\n{BOLD}Bag-of-words cosine (offline){OFF}")
    print("        " + "".join(f"{k:>10}" for k, _, _ in PHRASES))
    for ka, ta, _ in PHRASES:
        print(f"   {ka:<5}" + "".join(f"{bow(ta, tb):>10.2f}" for _, tb, _ in PHRASES))
    if need_key():
        return 1
    V = embed([t for _, t, _ in PHRASES])
    cos = lambda x, y: R._cosine_similarity(V[x], V[y])
    print(f"\n{BOLD}Dense cosine (gemini-embedding-2, {len(next(iter(V.values())))}d){OFF}")
    print("        " + "".join(f"{k:>10}" for k, _, _ in PHRASES))
    for ka, ta, _ in PHRASES:
        print(f"   {ka:<5}" + "".join(f"{cos(ta, tb):>10.2f}" for _, tb, _ in PHRASES))
    A, B, C, D = (p[1] for p in PHRASES)
    print(f"\n{BOLD}For the slide{OFF}   measured {datetime.date.today():%d %b %Y}")
    for lbl, s, why in (("A vs B", cos(A, B), "same fault, plain words"),
                        ("A vs C", cos(A, C), "different fault, same jargon"),
                        ("A vs D", cos(A, D), "not a network problem")):
        print(f"   {lbl}  {s:.2f}   {why}")
    print(f"\n   {DIM}Absolute values mean little — dense cosine rarely goes near "
          f"zero. Only the ordering is a result.{OFF}")
    print(f"   B vs D is {cos(B, D):.2f}: plain operational language sits nearly as "
          f"close to an invoice as to its own fault.")
    return 0


def probe():
    if need_key():
        return 1
    texts = sorted({a for a in PROBE} | {p for v in PROBE.values() for p, _, _ in v})
    V = embed(texts)
    cos = lambda x, y: R._cosine_similarity(V[x], V[y])
    buckets = {k: [] for k in CELL}
    for anchor, partners in PROBE.items():
        print(f"\n{BOLD}{anchor}{OFF}")
        for partner, sf, sr in partners:
            s = cos(anchor, partner)
            buckets[(sf, sr)].append(s)
            print(f"   {s:.2f}   {DIM}{CELL[(sf, sr)]:<32}{OFF} {partner}")
    print(f"\n{BOLD}Mean by cell, across all three anchors{OFF}")
    means = {k: sum(v) / len(v) for k, v in buckets.items()}
    for k in ((1, 1), (0, 1), (1, 0), (0, 0)):
        print(f"   {means[k]:.2f}   {CELL[k]}   {DIM}n={len(buckets[k])}{OFF}")
    dominates = means[(0, 1)] > means[(1, 0)]
    print(f"\n   {GRN if dominates else RED}register {'DOES' if dominates else 'DOES NOT'} "
          f"dominate diagnosis{OFF}: a different fault in the same register scores "
          f"{means[(0,1)]:.2f} against {means[(1,0)]:.2f} for the same fault in plain words.")
    print(f"   {DIM}Measured {datetime.date.today():%d %b %Y}. One model, one day. "
          f"Say that on the slide.{OFF}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true",
                    help="the 2x2: fault vs register, three anchors")
    raise SystemExit(probe() if ap.parse_args().probe else four_phrases())
