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


def base_run_done(d, ids=("R-1", "R-2")):
    """A minimal healthy DONE-mode run: each row PASS with its own fix and distinct proof."""
    base_run(d, ids)
    write_jsonl(os.path.join(d, "verdicts.jsonl"),
                [{"id": i, "verdict": "PASS", "evidence": ["src.txt:1"],
                  "proof_cmd": f"grep -n {w} src.txt", "fix": "src.txt:1",
                  "fix_verdict": "PASS", "role": "engineer"}
                 for i, w in zip(ids, ("alpha", "beta"))])


def run_gate(d, mode="known", extra=None):
    cmd = [sys.executable, GATE,
           "--ledger", os.path.join(d, "ledger.jsonl"),
           "--verdicts", os.path.join(d, "verdicts.jsonl"),
           "--decisions", os.path.join(d, "decisions.jsonl"),
           "--scope", os.path.join(d, "scope.jsonl"),
           "--out", os.path.join(d, "REPORT.md"),
           "--mode", mode, "--repo-root", d]
    if mode == "done":
        cmd += ["--oracle-cmd", "true", "--expect-scope-count", "2"]
    cmd += extra or []
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


def case(name, expect_code, expect_phrase=None, mode="known", extra=None):
    def deco(fn):
        CASES.append((name, fn, expect_code, expect_phrase, mode, extra))
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


# -- adversarial cases from the review (each observed exit 0 before its fix) -----------

@case("bulletin superseding ITSELF cannot retire itself to dodge acks", 1,
      "supersedes itself")
def c_self_supersede(d):
    good_board(d)
    write_jsonl(os.path.join(d, "bulletin.jsonl"), [
        {"id": "B-1", "fact": "tenant_id replaces org_id", "evidence": "src.txt:2",
         "cause_by": "schema-recon", "published_by": "orchestrator",
         "scope": ["R-1"], "supersedes": "B-1"},
    ])
    write_jsonl(os.path.join(d, "verdicts.jsonl"), [
        {"id": "R-1", "verdict": "PASS", "evidence": ["src.txt:1"],
         "proof_cmd": "grep -n alpha src.txt", "role": "engineer"},
        {"id": "R-2", "verdict": "PASS", "evidence": ["src.txt:2"],
         "proof_cmd": "grep -n beta src.txt", "role": "checker"},
    ])


@case("bulletins_seen as a string cannot ack by substring", 1, "must be a list")
def c_seen_string(d):
    good_board(d)
    write_jsonl(os.path.join(d, "verdicts.jsonl"), [
        {"id": "R-1", "verdict": "PASS", "evidence": ["src.txt:1"],
         "proof_cmd": "grep -n alpha src.txt", "bulletins_seen": "B-10 was interesting"},
        {"id": "R-2", "verdict": "PASS", "evidence": ["src.txt:2"],
         "proof_cmd": "grep -n beta src.txt"},
    ])


@case("content-free decisions row is not an adjudication", 1, "adjudicat")
def c_shell_adjudication(d):
    good_board(d)
    write_jsonl(os.path.join(d, "decisions.jsonl"), [{"affects": ["R-2"]}])


@case("message with from:null gets a diagnostic, not a traceback", 1, "needs from")
def c_null_sender(d):
    good_board(d)
    write_jsonl(os.path.join(d, "messages.jsonl"), [
        {"from": None, "to": "checker", "type": "NEED:checker"},
        {"from": "checker", "to": "orchestrator", "type": "CONTRADICTS:R-2"},
    ])


@case("CLAIM message type was cut from the closed set — ownership is the file", 1,
      "closed set")
def c_claim_message(d):
    good_board(d)
    write_jsonl(os.path.join(d, "messages.jsonl"), [
        {"from": "engineer", "to": "orchestrator", "type": "CLAIM:R-1"},
        {"from": "checker", "to": "orchestrator", "type": "CONTRADICTS:R-2"},
    ])


@case("claim for an item not in the ledger", 1, "not in the ledger")
def c_ghost_claim(d):
    good_board(d)
    write_jsonl(os.path.join(d, "claims.jsonl"), [
        {"item": "R-99", "role": "ghost", "event": "claim"},
        {"item": "R-1", "role": "engineer", "event": "claim"},
        {"item": "R-2", "role": "checker", "event": "claim"},
    ])


@case("re-claim by the SAME role without release is still a double claim", 1,
      "without an intervening release")
def c_same_role_reclaim(d):
    good_board(d)
    write_jsonl(os.path.join(d, "claims.jsonl"), [
        {"item": "R-1", "role": "engineer", "event": "claim"},
        {"item": "R-1", "role": "engineer", "event": "claim"},
        {"item": "R-2", "role": "checker", "event": "claim"},
    ])


@case("claims.jsonl present but empty -> one clear error, not per-row noise", 1,
      "no events")
def c_empty_claims(d):
    good_board(d)
    open(os.path.join(d, "claims.jsonl"), "w").close()


@case("--require-board fails when no board files exist", 1, "require-board",
      extra=["--require-board"])
def c_require_board(d):
    pass


@case("evidence as a string -> one type error, not one error per character", 1,
      "must be a list")
def c_string_evidence(d):
    write_jsonl(os.path.join(d, "verdicts.jsonl"), [
        {"id": "R-1", "verdict": "PASS", "evidence": "src.txt:1",
         "proof_cmd": "grep -n alpha src.txt"},
        {"id": "R-2", "verdict": "PASS", "evidence": ["src.txt:2"],
         "proof_cmd": "grep -n beta src.txt"},
    ])


# -- done-mode cases (the completion-gate half was previously untested) -----------------

@case("done: delivered run passes", 0, mode="done")
def c_done_ok(d):
    base_run_done(d)


@case("done: a FAIL row means the work is unfinished", 1, "in a DONE job", mode="done")
def c_done_fail_row(d):
    base_run_done(d)
    write_jsonl(os.path.join(d, "verdicts.jsonl"), [
        {"id": "R-1", "verdict": "PASS", "evidence": ["src.txt:1"],
         "proof_cmd": "grep -n alpha src.txt", "fix": "src.txt:1", "fix_verdict": "PASS"},
        {"id": "R-2", "verdict": "FAIL", "evidence": ["src.txt:2"],
         "proof_cmd": "grep -n beta src.txt"},
    ])


@case("done: duplicate scope ids cannot pad out --expect-scope-count", 1,
      "duplicate scope id", mode="done")
def c_scope_padding(d):
    base_run_done(d)
    write_jsonl(os.path.join(d, "scope.jsonl"),
                [{"id": i, "claim": f"claim {i}"} for i in ("R-1", "R-2", "R-1", "R-2")])


@case("done: dup-padded scope matching the frozen count still fails", 1,
      "duplicate scope id", mode="done",
      extra=["--expect-scope-count", "4"])
def c_scope_padding_matched(d):
    base_run_done(d)
    write_jsonl(os.path.join(d, "scope.jsonl"),
                [{"id": i, "claim": f"claim {i}"} for i in ("R-1", "R-2", "R-1", "R-2")])


@case("done: one test cited for two rows via comment suffix is still one proof", 1,
      "share the identical proof_cmd", mode="done")
def c_comment_dedupe(d):
    base_run_done(d)
    write_jsonl(os.path.join(d, "verdicts.jsonl"), [
        {"id": "R-1", "verdict": "PASS", "evidence": ["src.txt:1"],
         "proof_cmd": "grep -n alpha src.txt  # R-1", "fix": "src.txt:1", "fix_verdict": "PASS"},
        {"id": "R-2", "verdict": "PASS", "evidence": ["src.txt:2"],
         "proof_cmd": "grep -n alpha src.txt  # R-2", "fix": "src.txt:1", "fix_verdict": "PASS"},
    ])


@case("done: FAIL->PASS with a cosmetic comment on the proof is still laundering", 1,
      "same proof_cmd", mode="done")
def c_comment_laundering(d):
    base_run_done(d)
    write_jsonl(os.path.join(d, "verdicts.jsonl"), [
        {"id": "R-1", "verdict": "FAIL", "evidence": ["src.txt:1"],
         "proof_cmd": "grep -n alpha src.txt"},
        {"id": "R-1", "verdict": "PASS", "evidence": ["src.txt:1"],
         "proof_cmd": "grep -n alpha src.txt  # re-verified", "fix": "src.txt:1",
         "fix_verdict": "PASS"},
        {"id": "R-2", "verdict": "PASS", "evidence": ["src.txt:2"],
         "proof_cmd": "grep -n beta src.txt", "fix": "src.txt:1", "fix_verdict": "PASS"},
    ])


def main():
    failures = 0
    for name, build, want_code, want_phrase, mode, extra in CASES:
        with tempfile.TemporaryDirectory() as d:
            base_run(d)
            build(d)
            code, err = run_gate(d, mode, extra)
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
