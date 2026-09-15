"""Checkpoint 3 — pass/fail. Run: python check.py"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.append(os.path.join(HERE, "..", "..", "module10-eval"))

from assertions import check_assertions, summarize, format_results  # noqa: E402

VOCAB = {"required_tools", "forbidden_tools", "tool_order", "max_ticket_severity",
         "must_retrieve", "must_not_retrieve", "answer_must_mention", "answer_must_not_mention"}


def main() -> int:
    from starter import MY_CASE as case

    checks = []
    spec = case.get("assertions") or {}
    used = [k for k in spec if k in VOCAB]

    checks.append(("scenario is filled in", bool(case.get("scenario", "").strip()),
                   f"{len(case.get('scenario', ''))} chars"))
    checks.append(("failure mode is named", bool(spec.get("name", "").strip()), spec.get("name") or "empty"))
    checks.append(("rationale is filled in", bool(spec.get("rationale", "").strip()),
                   f"{len(spec.get('rationale', ''))} chars"))
    checks.append(("at least two assertions", len(used) >= 2,
                   f"{len(used)} used: {', '.join(used) or 'none'}"))
    checks.append(("good trace provided", bool(case.get("good_trace")),
                   f"{len(case.get('good_trace') or [])} steps"))
    checks.append(("bad trace provided", bool(case.get("bad_trace")),
                   f"{len(case.get('bad_trace') or [])} steps"))

    if not all(ok for _, ok, _ in checks):
        return report(case, checks, None, None)

    good = check_assertions(case, case.get("good_answer", ""), case["good_trace"])
    bad = check_assertions(case, case.get("bad_answer", ""), case["bad_trace"])
    g_hit, g_tot = summarize(good)
    b_hit, b_tot = summarize(bad)

    checks.append(("passes on the good trace", g_tot > 0 and g_hit == g_tot, f"{g_hit}/{g_tot}"))
    checks.append(("REJECTS the bad trace", b_hit < b_tot,
                   f"{b_hit}/{b_tot}" + ("" if b_hit < b_tot else "  <- assertions too weak")))
    return report(case, checks, good, bad)


def report(case, checks, good, bad) -> int:
    print(f"\nCheckpoint 3 — Write your own eval  ({case.get('case_id', '?')})\n" + "-" * 58)
    for label, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL':4}  {label:28} {detail}")
    if good is not None:
        print("\n  Against your GOOD trace:")
        print(format_results(good, indent="      "))
        print("\n  Against your BAD trace:")
        print(format_results(bad, indent="      "))
    passed = all(ok for _, ok, _ in checks)
    print("-" * 58)
    print("  PASS — your case discriminates. That's a real test." if passed
          else "  FAIL — see README.md, 'The requirement that catches people'.")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
