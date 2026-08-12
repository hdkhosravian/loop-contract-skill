#!/usr/bin/env python3
"""Fixture tests for fold_ledger.py — the gate's own oracle.

Each case builds a run directory in a tempdir, invokes the gate as a subprocess, and
asserts on its exit code (and, for failures, on a distinctive phrase in stderr, so a
case cannot pass by failing for an unrelated reason).

The board cases exercise the coordination checks: the gate must auto-detect
claims.jsonl / bulletin.jsonl / messages.jsonl beside the ledger — no flags — and a
run without those files must behave exactly as before they existed.

Run:  python3 tests/test_gate.py
Exit: 0 all cases hold · 1 otherwise
"""

import json
import os
import subprocess
import sys
import tempfile

GATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "skills", "loop-contract", "scripts", "fold_ledger.py")


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def base_run(d, ids=("R-1", "R-2")):
    """A minimal healthy KNOWN-mode run: every scoped row PASS with resolving evidence."""
    src = os.path.join(d, "src.txt")
    with open(src, "w", encoding="utf-8") as fh:
        fh.write("alpha\nbeta\n")
    write_jsonl(os.path.join(d, "scope.jsonl"),
                [{"id": i, "claim": f"claim {i}"} for i in ids])
    write_jsonl(os.path.join(d, "ledger.jsonl"),
                [{"id": i, "claim": f"claim {i}", "epic": "e1"} for i in ids])
    write_jsonl(os.path.join(d, "verdicts.jsonl"),
                [{"id": i, "verdict": "PASS", "evidence": ["src.txt:1"],
                  "proof_cmd": f"grep -n alpha src.txt  # {i}", "role": "engineer"}
                 for i in ids])
    write_jsonl(os.path.join(d, "decisions.jsonl"), [])


def run_gate(d):
    cmd = [sys.executable, GATE,
           "--ledger", os.path.join(d, "ledger.jsonl"),
           "--verdicts", os.path.join(d, "verdicts.jsonl"),
           "--decisions", os.path.join(d, "decisions.jsonl"),
           "--scope", os.path.join(d, "scope.jsonl"),
           "--out", os.path.join(d, "REPORT.md"),
           "--mode", "known", "--repo-root", d]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stderr


# -- board builders -------------------------------------------------------------------

def good_board(d):
    """A coherent multi-agent run: claims consistent, bulletin acked, messages typed,
    the one contradiction adjudicated, one superseded bulletin legitimately unacked."""
    write_jsonl(os.path.join(d, "claims.jsonl"), [
        {"item": "R-1", "role": "engineer", "event": "claim"},
        {"item": "R-1", "role": "engineer", "event": "release"},
        {"item": "R-2", "role": "checker", "event": "claim"},
        {"item": "R-2", "role": "checker", "event": "release"},
    ])
    write_jsonl(os.path.join(d, "bulletin.jsonl"), [
        {"id": "B-0", "fact": "org_id is the tenant key", "evidence": "src.txt:1",
         "cause_by": "recon", "published_by": "orchestrator", "scope": ["R-1"]},
        {"id": "B-1", "fact": "tenant_id replaces org_id", "evidence": "src.txt:2",
         "cause_by": "schema-recon", "published_by": "orchestrator",
         "scope": ["R-1"], "supersedes": "B-0"},
    ])
    write_jsonl(os.path.join(d, "messages.jsonl"), [
        {"from": "orchestrator", "to": "engineer", "type": "PUBLISHED:B-1"},
        {"from": "checker", "to": "orchestrator", "type": "CONTRADICTS:R-2"},
    ])
    write_jsonl(os.path.join(d, "decisions.jsonl"), [
        {"id": "D-1", "question": "checker contradicts R-2's premise",
         "resolution": "checker upheld on evidence", "rule_applied": "literal-doc",
         "affects": ["R-2"], "confidence": "high"},
    ])
    # R-1's verdict must acknowledge the live bulletin that names it
    write_jsonl(os.path.join(d, "verdicts.jsonl"), [
        {"id": "R-1", "verdict": "PASS", "evidence": ["src.txt:1"],
         "proof_cmd": "grep -n alpha src.txt  # R-1", "role": "engineer",
         "bulletins_seen": ["B-1"]},
        {"id": "R-2", "verdict": "PASS", "evidence": ["src.txt:2"],
         "proof_cmd": "grep -n beta src.txt  # R-2", "role": "checker"},
    ])


# -- cases ----------------------------------------------------------------------------

CASES = []


def case(name, expect_code, expect_phrase=None):
    def deco(fn):
        CASES.append((name, fn, expect_code, expect_phrase))
        return fn
    return deco


@case("legacy run, no board files -> unchanged, gate passes", 0)
def c_legacy(d):
    pass


@case("coherent board -> gate passes", 0)
def c_good(d):
    good_board(d)


@case("second claim without release -> duplicated work", 1, "duplicated work")
def c_double_claim(d):
    good_board(d)
    write_jsonl(os.path.join(d, "claims.jsonl"), [
        {"item": "R-1", "role": "engineer", "event": "claim"},
        {"item": "R-1", "role": "checker", "event": "claim"},
        {"item": "R-2", "role": "checker", "event": "claim"},
    ])


@case("verdicted row never claimed -> off-board work", 1, "never claimed")
def c_unclaimed(d):
    good_board(d)
    write_jsonl(os.path.join(d, "claims.jsonl"), [
        {"item": "R-1", "role": "engineer", "event": "claim"},
    ])


@case("bulletin row without provenance -> fails", 1, "provenance")
def c_no_provenance(d):
    good_board(d)
    write_jsonl(os.path.join(d, "bulletin.jsonl"), [
        {"id": "B-1", "fact": "tenant_id replaces org_id", "scope": ["R-1"]},
    ])


@case("verdict blind to a live bulletin naming it -> fails", 1, "bulletins_seen")
def c_unacked(d):
    good_board(d)
    write_jsonl(os.path.join(d, "verdicts.jsonl"), [
        {"id": "R-1", "verdict": "PASS", "evidence": ["src.txt:1"],
         "proof_cmd": "grep -n alpha src.txt  # R-1", "role": "engineer"},
        {"id": "R-2", "verdict": "PASS", "evidence": ["src.txt:2"],
         "proof_cmd": "grep -n beta src.txt  # R-2", "role": "checker",
         "bulletins_seen": []},
    ])


@case("supersedes an id not on the board -> fails", 1, "supersedes")
def c_bad_supersede(d):
    good_board(d)
    write_jsonl(os.path.join(d, "bulletin.jsonl"), [
        {"id": "B-1", "fact": "tenant_id replaces org_id", "evidence": "src.txt:2",
         "cause_by": "schema-recon", "published_by": "orchestrator",
         "scope": ["R-1"], "supersedes": "B-404"},
    ])


@case("free-prose message type -> outside the closed set", 1, "closed set")
def c_prose_message(d):
    good_board(d)
    write_jsonl(os.path.join(d, "messages.jsonl"), [
        {"from": "engineer", "to": "checker",
         "type": "hey, quick thought on how we should name things"},
        {"from": "checker", "to": "orchestrator", "type": "CONTRADICTS:R-2"},
    ])


@case("CONTRADICTS without adjudication -> fails the run", 1, "adjudicat")
def c_unadjudicated(d):
    good_board(d)
    write_jsonl(os.path.join(d, "decisions.jsonl"), [])


@case("message cap exceeded -> narration is not coordination", 1, "cap")
def c_cap(d):
    good_board(d)
    msgs = [{"from": "engineer", "to": "checker", "type": f"NEED:checker  # {n}"}
            for n in range(9)]
    msgs.append({"from": "checker", "to": "orchestrator", "type": "CONTRADICTS:R-2"})
    write_jsonl(os.path.join(d, "messages.jsonl"), msgs)


@case("PUBLISHED nudge for a bulletin not on the board -> fails", 1, "no such bulletin")
def c_ghost_publish(d):
    good_board(d)
    write_jsonl(os.path.join(d, "messages.jsonl"), [
        {"from": "orchestrator", "to": "engineer", "type": "PUBLISHED:B-9"},
        {"from": "checker", "to": "orchestrator", "type": "CONTRADICTS:R-2"},
    ])


def main():
    failures = 0
    for name, build, want_code, want_phrase in CASES:
        with tempfile.TemporaryDirectory() as d:
            base_run(d)
            build(d)
            code, err = run_gate(d)
            ok = code == want_code and (want_phrase is None or want_phrase in err)
            print(f"{'PASS' if ok else 'FAIL'}  {name}")
            if not ok:
                failures += 1
                print(f"      expected exit {want_code}"
                      + (f" with {want_phrase!r} in stderr" if want_phrase else "")
                      + f", got exit {code}")
                for line in err.strip().splitlines()[:6]:
                    print(f"      | {line}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} cases hold")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
