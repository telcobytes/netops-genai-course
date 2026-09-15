"""Checkpoint 2 — pass/fail. Run: python check.py"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from starter import load_alarms  # noqa: E402

EXPECTED = {
    "ALM-7101": "RAN",        # sustained PRB saturation over planned capacity
    "ALM-7102": "TRANSPORT",  # packet delay variation on the backhaul hop
    "ALM-7103": "CORE",       # NAS attach rejects + Diameter result codes
    "ALM-7104": "DROP",       # MINOR, informational, auto-cleared in 90s
    "ALM-7105": "RAN",        # uplink interference raising the noise floor
}


def main() -> int:
    try:
        from starter import route
        route(load_alarms()[0])
    except NotImplementedError:
        print("\n  route() is not implemented yet — see README.md\n")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"\n  route() raised {type(exc).__name__}: {exc}\n")
        return 1

    print("\nCheckpoint 2 — Build the dispatcher\n" + "-" * 58)
    correct = 0
    dropped_noise = False
    for alarm in load_alarms():
        got = route(alarm)
        want = EXPECTED[alarm["alarm_id"]]
        ok = got == want
        correct += ok
        if alarm["alarm_id"] == "ALM-7104" and ok:
            dropped_noise = True
        print(f"  {'PASS' if ok else 'FAIL'}  {alarm['alarm_id']}  got {got:9} want {want:9}"
              f"  {alarm['alarm_type']}")

    print("-" * 58)
    print(f"  {correct}/5 correct" + ("" if dropped_noise else "   (ALM-7104 was NOT dropped)"))
    if correct == 5:
        print("  PASS — every alarm on the right desk, and the noise on none of them.")
        return 0
    if not dropped_noise:
        print("  FAIL — check the DROP route first. Re-read 'The one that matters'.")
    else:
        print("  FAIL — see README.md.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
