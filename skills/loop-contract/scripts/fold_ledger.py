#!/usr/bin/env python3
"""
fold_ledger.py — join ledger + verdicts into a report, and act as the completion gate.

Deterministic. stdlib only. This script is the reason "done" is a fact rather than a
claim: the agent cannot declare completion, it can only make this exit 0.

Exit codes:
    0  every row has a terminal verdict and the report was written
    1  integrity failure (unknown / duplicate / non-terminal / evidence-less rows)
    2  bad input

Usage:
    python fold_ledger.py --ledger audit/ledger.jsonl \
                          --verdicts audit/verdicts.jsonl \
                          --decisions audit/decisions.jsonl \
                          --out audit/REPORT.md
    python fold_ledger.py ... --group-by epic --allow-blocked 3
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
from collections import Counter, defaultdict

TERMINAL = {"PASS", "FAIL", "PARTIAL", "BLOCKED"}
BLOCKING = {"FAIL"}


def load_jsonl(path, required=True):
    if not os.path.exists(path):
        if required:
            print(f"ERROR: missing {path}", file=sys.stderr)
            sys.exit(2)
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"ERROR: {path}:{n} is not valid JSON — {e}", file=sys.stderr)
                sys.exit(2)
    return rows


SEVERITY = {"FAIL": 0, "BLOCKED": 1, "PARTIAL": 2, "PASS": 3}


def fold(ledger, verdicts):
    """Last verdict per id wins — verdict files are append-only, so later supersedes.

    Supersession is legitimate (you fixed the thing), but a silent upgrade from FAIL to
    PASS is also how an inconvenient verdict gets laundered. Every overturn is recorded
    and surfaced in the report so a human reading the receipt sees the flip.
    """
    by_id, errors, overturns = {}, [], []
    for r in ledger:
        rid = r.get("id")
        if not rid:
            errors.append(f"ledger row without id: {json.dumps(r)[:120]}")
            continue
        if rid in by_id:
            errors.append(f"duplicate ledger id: {rid}")
        by_id[rid] = dict(r)

    for v in verdicts:
        vid = v.get("id")
        if vid not in by_id:
            errors.append(f"verdict for unknown id: {vid}")
            continue
        prev, new = by_id[vid].get("verdict"), v.get("verdict")
        if prev and new and prev != new and SEVERITY.get(new, -1) > SEVERITY.get(prev, -1):
            overturns.append({
                "id": vid, "from": prev, "to": new,
                "prev_proof": by_id[vid].get("proof_cmd"), "new_proof": v.get("proof_cmd"),
            })
        by_id[vid].update({k: val for k, val in v.items() if k != "id"})

    return by_id, errors, overturns


def integrity(rows, mode="known"):
    """Checks that make a false PASS structurally hard to ship.

    mode="known" (audit/review): a FAIL row is a legitimate finding — the run completed.
    mode="done"  (implement/fix/produce): a FAIL or PARTIAL row means the change was NOT
        made, so the job is not finished. Without this, a ledger whose every row is
        verdicted "FAIL — not implemented" against completely unchanged code exits 0 and
        certifies a thorough write-up of unfinished work as a completed run.
    """
    errs = []
    for rid, r in sorted(rows.items()):
        v = r.get("verdict")
        if v is None:
            errs.append(f"{rid}: no verdict (still OPEN)")
        elif v not in TERMINAL:
            errs.append(f"{rid}: non-terminal verdict {v!r}")
        elif v in ("PASS", "PARTIAL", "FAIL"):
            # Not just PASS: PARTIAL ("looks half-wired") and FAIL ("I couldn't find it") are the
            # verdicts most often asserted from a reading. An absence is a claim, not a fact —
            # it needs a command that ran and a positive control, same as a presence.
            if not r.get("evidence"):
                errs.append(f"{rid}: {v} without evidence — a reading, not a verification")
            if not r.get("proof_cmd"):
                errs.append(f"{rid}: {v} without proof_cmd — nothing was actually run")
            if v == "PARTIAL" and not r.get("missing"):
                errs.append(f"{rid}: PARTIAL without `missing` — say what is absent to reach done")
        elif v == "BLOCKED" and not r.get("blocked_reason"):
            errs.append(f"{rid}: BLOCKED without blocked_reason")

        if mode == "done":
            if v in ("FAIL", "PARTIAL"):
                errs.append(f"{rid}: {v} in a DONE job — the change was not made. Documenting "
                            f"what is missing does not complete the work; apply the fix, or mark "
                            f"it BLOCKED with a reason if it genuinely cannot be done.")
            elif v == "PASS":
                # Gate P2' requires each change to carry its own applied-and-verified proof.
                # "already satisfied" is legitimate but must be declared, not left blank:
                # fix="none" + no_change_reason says so on the record.
                fix = r.get("fix")
                if fix == "none":
                    if not r.get("no_change_reason"):
                        errs.append(f"{rid}: fix=\"none\" without `no_change_reason` — say why this "
                                    f"row needed no change, and keep the proof that it is satisfied.")
                elif not fix:
                    errs.append(f"{rid}: PASS in a DONE job without `fix` — no change was recorded, "
                                f"so nothing was delivered for this row. If it was already "
                                f"satisfied, set fix=\"none\" with a no_change_reason.")
                elif r.get("fix_verdict") != "PASS":
                    errs.append(f"{rid}: `fix` recorded but fix_verdict is "
                                f"{r.get('fix_verdict')!r} — the change was not verified.")

    # Nothing delivered at all: every row blocked/absent still means the job is not done.
    if mode == "done" and rows and not any(r.get("verdict") == "PASS" for r in rows.values()):
        errs.append("DONE job with zero PASS rows — nothing was delivered. A run in which every row "
                    "is BLOCKED is a documented standstill, not a completed job.")
    return errs


def remaining(rows, scope):
    """The worklist, computed from disk rather than remembered.

    A long run dies mid-phase and resumes with an empty context. "Continue from where you
    were" is then unanswerable — the agent remembers nothing. This recomputes what is left
    from scope minus terminal verdicts, so resume is deterministic and survives compaction,
    /clear, a crash, or a fresh session.
    """
    out = []
    for s in scope:
        sid = s.get("id")
        if not sid:
            continue
        r = rows.get(sid)
        if r is None or r.get("verdict") not in TERMINAL:
            out.append({"id": sid, "claim": (s.get("claim") or "")[:120],
                        "state": "OPEN" if r is None else str(r.get("verdict"))})
    return out


def check_scope(rows, scope, mode):
    """Scope is frozen before the work; the gate checks the work covered ALL of it.

    Without this the agent that does the work also decides what the work was, and the
    cheapest way to pass is to enumerate three easy tasks, do those, and declare victory.
    Every scope id must appear in the ledger with a terminal verdict, and in DONE mode
    must actually be delivered.
    """
    errs = []
    have = set(rows)
    for s in scope:
        sid = s.get("id")
        if not sid:
            continue
        if sid not in have:
            errs.append(f"{sid}: in frozen scope but missing from the ledger — scope cannot shrink "
                        f"after the work starts. Add the row and give it a terminal verdict.")
            continue
        v = rows[sid].get("verdict")
        if v is None:
            errs.append(f"{sid}: in scope, still OPEN — every scoped item needs a verdict.")
        elif mode == "done" and v not in ("PASS", "BLOCKED"):
            errs.append(f"{sid}: in scope, verdict {v} — scoped work is not delivered.")
    extra = have - {s.get("id") for s in scope if s.get("id")}
    if scope and extra:
        errs.append(f"{len(extra)} ledger row(s) are not in the frozen scope "
                    f"({', '.join(sorted(extra)[:5])}…) — scope grew mid-run; re-freeze it "
                    f"deliberately or drop them.")
    return errs


def check_agreement(rows, require_k):
    """Two distinct mechanisms, enforced distinctly.

    Coverage panel (`lenses`): distinct questions, combined by conjunction — any lens FAIL
    fails the row. A lens disagreeing is a finding, never a reason to soften the rubric.
    Repeatability (`k`/`agreement`): the SAME question run k times — here agreement is the
    measurement, and unanimity (pass^k) is the production bar.
    """
    errs = []
    for rid, r in sorted(rows.items()):
        lenses = r.get("lenses")
        if isinstance(lenses, dict) and lenses:
            failed = [ln for ln, v in lenses.items() if v in ("FAIL", "PARTIAL")]
            if failed and r.get("verdict") == "PASS":
                errs.append(f"{rid}: PASS but lens(es) {', '.join(sorted(failed))} did not pass — a "
                            f"coverage panel combines by AND. Any lens failing fails the row; that "
                            f"disagreement is a finding to investigate, not one to average away.")
        if require_k is None:
            continue
        if r.get("check") == "judgement" and r.get("verdict") in ("PASS", "PARTIAL", "FAIL"):
            agree, k = r.get("agreement"), r.get("k")
            if agree is None or k is None:
                errs.append(f"{rid}: judgement row without a repeatability record — run the same "
                            f"rubric {require_k}× and store k/agreement.")
            elif k < require_k or agree < k:
                errs.append(f"{rid}: repeatability {agree}/{k}, needs unanimity over ≥{require_k} runs "
                            f"(pass^k). Split verdicts mean the criterion is ambiguous — tighten the "
                            f"rubric and re-run; do not average.")
    return errs


def check_per_task_proof(rows, mode):
    """Each delivered task must carry its OWN executed proof, distinct from its neighbours'.

    Catches the dominant dummy-work pattern: one test written once, then cited as the
    proof_cmd for twenty different rows.
    """
    if mode != "done":
        return []
    errs, seen = [], {}
    for rid, r in sorted(rows.items()):
        if r.get("verdict") != "PASS" or r.get("fix") == "none":
            continue
        pc = (r.get("proof_cmd") or "").strip()
        if pc:
            seen.setdefault(pc, []).append(rid)
    for pc, ids in seen.items():
        if len(ids) > 1:
            errs.append(f"{len(ids)} rows share the identical proof_cmd {pc!r} "
                        f"({', '.join(ids[:4])}…) — one command cannot be the individual proof of "
                        f"several distinct changes. Give each row a check that exercises it.")
    return errs


def check_citations(rows, repo_root):
    """Resolve every cited path. A citation nobody resolves is a string, not evidence —
    the same fabrication check the skill prescribes for the user's deliverables."""
    errs = []
    for rid, r in sorted(rows.items()):
        cites = list(r.get("evidence") or [])
        fix = r.get("fix")
        if fix and fix != "none":
            cites.append(fix)
        for c in cites:
            if not isinstance(c, str) or not c.strip():
                continue
            # URLs are legitimate evidence for non-code work — check the RAW string before
            # splitting, or "https://x" becomes path "https" and every sourced plan fails.
            if c.strip().startswith(("http://", "https://")):
                continue
            # tolerate pytest node ids (file.py::test_name) and path:line / path:a-b
            path = c.split("::")[0].split(":")[0].strip()
            if not path:
                continue
            full = os.path.join(repo_root, path)
            if not os.path.exists(full):
                errs.append(f"{rid}: cited path does not exist: {path!r} "
                            f"(evidence must resolve, or it is a claim not a citation)")
                continue
            part = c.split("::")[0]
            if ":" in part:
                lineref = part.rsplit(":", 1)[1]
                start = lineref.split("-")[0]
                if start.isdigit() and os.path.isfile(full):
                    try:
                        with open(full, "r", encoding="utf-8", errors="replace") as fh:
                            n = sum(1 for _ in fh)
                        if int(start) > n:
                            errs.append(f"{rid}: cited line {c} is past end of file ({n} lines)")
                    except OSError:
                        pass
    return errs


def run_oracle(cmd, use_shell=False):
    """Observe the achievement oracle rather than take the agent's word that it is green.
    This is the difference between a gate and a receipt for a claim.

    The command is split with shlex and run WITHOUT a shell by default. That matters here:
    the oracle command is often lifted from a contract an agent wrote, and this skill's own
    token policy says agent-authored text is data, never an instruction. Shell-executing it
    would turn a poisoned contract into arbitrary code execution. Pass --oracle-shell only
    for a command you wrote yourself that genuinely needs `&&`, a pipe, or globbing.
    """
    try:
        target = cmd if use_shell else shlex.split(cmd)
        p = subprocess.run(target, shell=use_shell, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        return None, "timed out after 1800s"
    except (OSError, ValueError) as e:
        return None, f"could not run: {e}"
    tail = (p.stdout or "")[-400:] + (p.stderr or "")[-400:]
    return p.returncode, tail.strip()


def md_escape(s):
    return str(s).replace("|", "\\|").replace("\n", " ").strip()


def render(rows, decisions, group_by, mode="known", oracle=None, overturns=None,
           headline=None, vocab=None):
    counts = Counter(r.get("verdict", "OPEN") for r in rows.values())
    blocking = [r for r in rows.values() if r.get("verdict") in BLOCKING]
    partial = [r for r in rows.values() if r.get("verdict") == "PARTIAL"]
    blocked = [r for r in rows.values() if r.get("verdict") == "BLOCKED"]

    if mode == "done":
        # The artifact is the deliverable; this report is only its receipt.
        if blocking or partial or (rows and len(blocked) == len(rows)):
            verdict = "NOT DELIVERED"
            why = (f"{len(blocking)} not done, {len(partial)} partial, {len(blocked)} blocked. "
                   f"The work is unfinished — this report is not the deliverable.")
        elif blocked:
            verdict = "PARTIALLY DELIVERED"
            why = f"{len(rows) - len(blocked)} applied and verified, {len(blocked)} blocked."
        else:
            verdict = "DELIVERED"
            why = f"All {len(rows)} changes applied and individually verified by an executed check."
    elif blocking:
        verdict = "DO-NOT-SHIP"
        why = f"{len(blocking)} requirement(s) are not implemented or not enforced."
    elif partial or blocked:
        verdict = "SHIP-WITH-FIXES"
        why = f"{len(partial)} partial, {len(blocked)} unresolved. No hard failures."
    else:
        verdict = "SHIP"
        why = f"All {len(rows)} requirements verified with evidence and an executed proof."

    if oracle:
        status = "GREEN" if oracle["code"] == 0 else f"RED (exit {oracle['code']})"
        why += f"  ·  Achievement oracle `{oracle['cmd']}` — **{status}**, observed by this script."
    if overturns:
        why += (f"  ·  ⚠ {len(overturns)} verdict(s) were raised after an earlier terminal verdict — "
                f"see Overturned verdicts below.")

    if vocab:
        parts = [v.strip() for v in vocab.split(",")]
        if len(parts) == 3:
            good, mid, bad = parts
            verdict = {"SHIP": good, "DELIVERED": good,
                       "SHIP-WITH-FIXES": mid, "PARTIALLY DELIVERED": mid,
                       "DO-NOT-SHIP": bad, "NOT DELIVERED": bad}.get(verdict, verdict)

    L = ["# Delivery Receipt" if mode == "done" else "# Conformance Report", "",
         f"## 1. Verdict: **{verdict}**", "", why, "",
         "  ".join(f"`{k}: {v}`" for k, v in sorted(counts.items())), ""]
    if headline:
        L[1:1] = ["", "## 0. Answer", "", f"**{headline}**", ""]

    def table(title, items, cols, note=None):
        L.append(f"## {title}")
        L.append("")
        if not items:
            L.append("_none_")
            L.append("")
            return
        if note:
            L.append(note)
            L.append("")
        L.append("| " + " | ".join(c[0] for c in cols) + " |")
        L.append("|" + "|".join("---" for _ in cols) + "|")
        for it in sorted(items, key=lambda r: str(r.get("id"))):
            L.append("| " + " | ".join(md_escape(c[1](it)) for c in cols) + " |")
        L.append("")

    ev = lambda r: ", ".join(f"`{e}`" for e in (r.get("evidence") or [])) or "—"

    table("2. Blocking", blocking, [
        ("ID", lambda r: r.get("id")),
        ("Claim", lambda r: r.get("claim", "")[:110]),
        ("Missing", lambda r: r.get("note", "")),
        ("Source", lambda r: f"`{r.get('src','')}`"),
    ])
    table("3. Partial", partial, [
        ("ID", lambda r: r.get("id")),
        ("Claim", lambda r: r.get("claim", "")[:110]),
        ("Exists", lambda r: ev(r)),
        ("Missing", lambda r: r.get("note", "")),
    ])
    table("4. Blocked", blocked, [
        ("ID", lambda r: r.get("id")),
        ("Claim", lambda r: r.get("claim", "")[:110]),
        ("Reason", lambda r: r.get("blocked_reason", "")),
    ])

    # coverage matrix — a group with zero rows is a process failure, not a clean bill of health
    L.append(f"## 5. Coverage by {group_by}")
    L.append("")
    groups = defaultdict(Counter)
    for r in rows.values():
        groups[r.get(group_by) or r.get("section") or "ungrouped"][r.get("verdict", "OPEN")] += 1
    order = ["PASS", "PARTIAL", "FAIL", "BLOCKED"]
    L.append("| " + group_by + " | " + " | ".join(order) + " | total |")
    L.append("|" + "|".join("---" for _ in range(len(order) + 2)) + "|")
    for g in sorted(groups):
        c = groups[g]
        L.append(f"| {md_escape(g)} | " + " | ".join(str(c.get(o, 0)) for o in order)
                 + f" | {sum(c.values())} |")
    L.append("")

    # constants get their own table: ratified value vs value in code is where drift hides
    consts = [r for r in rows.values() if r.get("kind") == "constant"]
    if consts:
        table("6. Ratified constants", consts, [
            ("Constant", lambda r: r.get("claim", "")),
            ("Verdict", lambda r: r.get("verdict", "")),
            ("In code", lambda r: ev(r)),
            ("Note", lambda r: r.get("note", "")),
        ])

    if overturns:
        L.append("## 6b. Overturned verdicts")
        L.append("")
        L.append("_A verdict that was raised after an earlier terminal one. Legitimate when you fixed "
                 "the thing — check that the new proof reflects the change._")
        L.append("")
        L.append("| ID | From | To | Earlier proof | New proof |")
        L.append("|---|---|---|---|---|")
        for o in overturns:
            L.append(f"| {md_escape(o['id'])} | {o['from']} | {o['to']} | "
                     f"`{md_escape(o.get('prev_proof') or '—')}` | `{md_escape(o.get('new_proof') or '—')}` |")
        L.append("")

    L.append("## 7. Decisions made on your behalf")
    L.append("")
    if decisions:
        L.append("_Ratify or overturn each of these._")
        L.append("")
        L.append("| ID | Question | Resolution | Rule | Affects | Confidence |")
        L.append("|---|---|---|---|---|---|")
        for d in decisions:
            L.append("| {} | {} | {} | {} | {} | {} |".format(
                md_escape(d.get("id", "")), md_escape(d.get("question", "")),
                md_escape(d.get("resolution", "")), md_escape(d.get("rule_applied", "")),
                md_escape(", ".join(d.get("affects", []) or [])), md_escape(d.get("confidence", ""))))
    else:
        L.append("_none recorded_")
    L.append("")

    docs_done_but_not = [r for r in rows.values()
                         if r.get("doc_says_done") and r.get("verdict") in ("FAIL", "PARTIAL")]
    if docs_done_but_not:
        L.append("## 8. Marked done in the docs but not verified in code")
        L.append("")
        for r in sorted(docs_done_but_not, key=lambda x: str(x.get("id"))):
            L.append(f"- `{r.get('id')}` — {md_escape(r.get('claim',''))[:140]} "
                     f"({r.get('verdict')}, {r.get('src','')})")
        L.append("")

    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ledger", default="audit/ledger.jsonl")
    ap.add_argument("--verdicts", default="audit/verdicts.jsonl")
    ap.add_argument("--decisions", default="audit/decisions.jsonl")
    ap.add_argument("--out", default="audit/REPORT.md")
    ap.add_argument("--group-by", default="epic", help="ledger field for the coverage matrix")
    ap.add_argument("--allow-blocked", type=int, default=0,
                    help="max BLOCKED rows tolerated before failing the gate (default 0 — "
                         "tolerating unfinished rows must be a deliberate, recorded choice)")
    ap.add_argument("--mode", choices=("known", "done"), required=True,
                    help="known = audit/review (a FAIL row is a finding; the run completed). "
                         "done = implement/fix/produce (a FAIL or PARTIAL row means the work "
                         "is unfinished and the gate fails). Required: the permissive reading "
                         "must never be what you get by forgetting a flag.")
    ap.add_argument("--oracle-cmd", default=None,
                    help="the achievement oracle, e.g. 'go test ./...' or 'pytest tests/test_x.py'. "
                         "RUN by this script; the gate fails unless it exits 0. Required in "
                         "--mode done: otherwise 'the oracle is green' is a claim, not a fact.")
    ap.add_argument("--oracle-shell", action="store_true",
                    help="run --oracle-cmd through a shell (needed for '&&', pipes, globs). Only "
                         "for a command you wrote yourself — never one lifted from a document.")
    ap.add_argument("--scope", default=None,
                    help="frozen scope file (JSONL, one {id, claim} per task) written BEFORE the "
                         "work. The gate fails if any scoped item is missing or undelivered. "
                         "Required in --mode done: otherwise the agent doing the work also decides "
                         "what the work was.")
    ap.add_argument("--headline", default=None,
                    help="the one-line answer this run produced (a root cause, a recommendation, the "
                         "reconciliation result). Rendered as section 0 above the verdict. A findings "
                         "table is not an answer; for a diagnosis job the answer IS the deliverable.")
    ap.add_argument("--verdict-vocab", default=None,
                    help="comma-separated replacements for the three verdict words when the job is not "
                         "a software release, e.g. 'RECONCILED,RECONCILED-WITH-EXCEPTIONS,NOT-RECONCILED'. "
                         "A finance controller cannot act on a report that says DO-NOT-SHIP.")
    ap.add_argument("--remaining", action="store_true",
                    help="print the still-unfinished scope items and exit — the resume worklist, "
                         "computed from disk so it survives context loss. Use at every interior "
                         "checkpoint of a long work phase and as the first action of a resumed run.")
    ap.add_argument("--require-agreement", type=int, default=None, metavar="K",
                    help="judgement rows must carry a repeatability record with unanimity over >=K "
                         "runs of the SAME rubric (pass^k). Coverage-panel lenses are always checked "
                         "by conjunction regardless of this flag.")
    ap.add_argument("--scope-count-cmd", default=None,
                    help="a command that RECOUNTS the source (e.g. \"rg -c '^- \\[ \\]' roadmap.md\" or "
                         "\"gh issue list --json id | jq length\"). The gate runs it and compares its "
                         "integer output to the scope row count. This is the only check that catches "
                         "under-enumeration, because it derives the expected number from the source "
                         "rather than from the agent that built the scope.")
    ap.add_argument("--expect-scope-count", type=int, default=None,
                    help="the row count recorded when scope was frozen at P1; mismatch fails the gate")
    ap.add_argument("--expect-scope-sha", default=None,
                    help="sha256 of scope.jsonl recorded at freeze time; mismatch fails the gate")
    ap.add_argument("--repo-root", default=".",
                    help="root for resolving cited paths in evidence/fix (default cwd)")
    ap.add_argument("--skip-citation-check", action="store_true",
                    help="do not resolve cited paths (for ledgers citing things outside the repo)")
    args = ap.parse_args()

    ledger = load_jsonl(args.ledger)
    verdicts = load_jsonl(args.verdicts, required=False)
    decisions = load_jsonl(args.decisions, required=False)

    if not ledger:
        print("ERROR: ledger is empty — extraction failed, nothing to verify", file=sys.stderr)
        return 2

    rows, fold_errs, overturns = fold(ledger, verdicts)

    if args.remaining:
        if not args.scope:
            print("ERROR: --remaining needs --scope", file=sys.stderr)
            return 2
        left = remaining(rows, load_jsonl(args.scope))
        total = len(load_jsonl(args.scope))
        print(f"{len(left)} of {total} scope items remain:")
        for r in left:
            print(f"  {r['id']:<12} [{r['state']}] {r['claim']}")
        return 0 if not left else 1
    errs = fold_errs + integrity(rows, args.mode)

    if not args.skip_citation_check:
        errs += check_citations(rows, args.repo_root)

    errs += check_per_task_proof(rows, args.mode)
    errs += check_agreement(rows, args.require_agreement)

    if args.scope:
        scope_rows = load_jsonl(args.scope)
        errs += check_scope(rows, scope_rows, args.mode)
        # The freeze is only real if it cannot be rewritten to match what got done.
        if args.expect_scope_count is not None and len(scope_rows) != args.expect_scope_count:
            errs.append(f"scope has {len(scope_rows)} rows but {args.expect_scope_count} were "
                        f"expected — either the source was under-enumerated at P1 (the "
                        f"{args.expect_scope_count - len(scope_rows)} missing items were never "
                        f"scoped, so no amount of good work covers them) or scope.jsonl was edited "
                        f"after the freeze. Re-derive the count from the source, not from the "
                        f"scope file.")
        if args.scope_count_cmd:
            code, tail = run_oracle(args.scope_count_cmd, args.oracle_shell)
            n = None
            if code == 0:
                for tok in reversed(tail.replace(":", " ").split()):
                    if tok.strip().isdigit():
                        n = int(tok.strip()); break
            if code != 0 or n is None:
                errs.append(f"--scope-count-cmd failed (exit {code}) or printed no integer: {tail[:150]} "
                            f"— an unverifiable recount is not a recount.")
            elif n != len(scope_rows):
                errs.append(f"source recount says {n} items but scope.jsonl has {len(scope_rows)} — "
                            f"{abs(n - len(scope_rows))} item(s) were never scoped. This is the gap the "
                            f"agent's own count cannot see; resolve it before working.")
        if args.mode == "done" and args.expect_scope_count is None and not args.scope_count_cmd:
            errs.append("--mode done with --scope but no --expect-scope-count: the scope file is "
                        "self-reported, so under-enumerating the source passes silently. Supply the "
                        "count the user stated, or one derived from the source by a command.")
        if args.expect_scope_sha:
            import hashlib
            with open(args.scope, "rb") as fh:
                actual = hashlib.sha256(fh.read()).hexdigest()
            if actual != args.expect_scope_sha:
                errs.append(f"scope.jsonl sha256 {actual[:12]}… does not match the {args.expect_scope_sha[:12]}… "
                            f"recorded at freeze time — the scope changed mid-run.")
    else:
        errs.append(f"--mode {args.mode} without --scope: nothing pins what the full job was, so a "
                    f"run that covered three of twenty items would pass. Freeze the scope before "
                    f"working. (A genuinely unenumerable job may pass --scope /dev/null deliberately.)")

    # Observe the oracle. Without this the whole gate certifies self-reported strings.
    oracle = None
    if args.mode == "done" and not args.oracle_cmd:
        errs.append("--mode done without --oracle-cmd: nothing was executed, so completion would "
                    "rest on the agent's own claim. Name the check that must go green.")
    elif args.oracle_cmd:
        code, tail = run_oracle(args.oracle_cmd, args.oracle_shell)
        oracle = {"cmd": args.oracle_cmd, "code": code, "tail": tail}
        if code != 0:
            errs.append(f"achievement oracle `{args.oracle_cmd}` exited {code} — the work is not "
                        f"done. Last output: {tail[:200]}")

    # A FAIL quietly re-appended as PASS is how an inconvenient verdict gets laundered.
    for o in overturns:
        if args.mode == "done" and o["from"] == "FAIL" and o["prev_proof"] == o["new_proof"]:
            errs.append(f"{o['id']}: verdict raised {o['from']}→{o['to']} with the same proof_cmd — "
                        f"re-verify with a command that reflects the change, or leave it FAIL.")

    n_blocked = sum(1 for r in rows.values() if r.get("verdict") == "BLOCKED")
    if n_blocked > args.allow_blocked:
        errs.append(f"{n_blocked} BLOCKED rows exceeds --allow-blocked={args.allow_blocked}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(render(rows, decisions, args.group_by, args.mode, oracle, overturns,
                        args.headline, args.verdict_vocab))

    if errs:
        print(f"GATE FAILED — {len(errs)} integrity error(s). Fix the ledger, not this script.",
              file=sys.stderr)
        for e in errs[:40]:
            print(f"  - {e}", file=sys.stderr)
        if len(errs) > 40:
            print(f"  ... and {len(errs) - 40} more", file=sys.stderr)
        return 1

    print(f"GATE PASSED — {len(rows)} rows folded -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
