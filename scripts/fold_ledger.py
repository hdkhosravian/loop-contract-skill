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


def fold(ledger, verdicts):
    """Last verdict per id wins — verdict files are append-only, so later supersedes."""
    by_id, errors = {}, []
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
        by_id[vid].update({k: val for k, val in v.items() if k != "id"})

    return by_id, errors


def integrity(rows):
    """Checks that make a false PASS structurally hard to ship."""
    errs = []
    for rid, r in sorted(rows.items()):
        v = r.get("verdict")
        if v is None:
            errs.append(f"{rid}: no verdict (still OPEN)")
        elif v not in TERMINAL:
            errs.append(f"{rid}: non-terminal verdict {v!r}")
        elif v == "PASS":
            if not r.get("evidence"):
                errs.append(f"{rid}: PASS without evidence — a reading, not a verification")
            if not r.get("proof_cmd"):
                errs.append(f"{rid}: PASS without proof_cmd — nothing was actually run")
        elif v == "BLOCKED" and not r.get("blocked_reason"):
            errs.append(f"{rid}: BLOCKED without blocked_reason")
    return errs


def md_escape(s):
    return str(s).replace("|", "\\|").replace("\n", " ").strip()


def render(rows, decisions, group_by):
    counts = Counter(r.get("verdict", "OPEN") for r in rows.values())
    blocking = [r for r in rows.values() if r.get("verdict") in BLOCKING]
    partial = [r for r in rows.values() if r.get("verdict") == "PARTIAL"]
    blocked = [r for r in rows.values() if r.get("verdict") == "BLOCKED"]

    if blocking:
        verdict = "DO-NOT-SHIP"
        why = f"{len(blocking)} requirement(s) are not implemented or not enforced."
    elif partial or blocked:
        verdict = "SHIP-WITH-FIXES"
        why = f"{len(partial)} partial, {len(blocked)} unresolved. No hard failures."
    else:
        verdict = "SHIP"
        why = f"All {len(rows)} requirements verified with evidence and an executed proof."

    L = [f"# Conformance Report", "",
         f"## 1. Verdict: **{verdict}**", "", why, "",
         "  ".join(f"`{k}: {v}`" for k, v in sorted(counts.items())), ""]

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
    ap.add_argument("--allow-blocked", type=int, default=None,
                    help="max BLOCKED rows tolerated before failing the gate")
    args = ap.parse_args()

    ledger = load_jsonl(args.ledger)
    verdicts = load_jsonl(args.verdicts, required=False)
    decisions = load_jsonl(args.decisions, required=False)

    if not ledger:
        print("ERROR: ledger is empty — extraction failed, nothing to verify", file=sys.stderr)
        return 2

    rows, fold_errs = fold(ledger, verdicts)
    errs = fold_errs + integrity(rows)

    n_blocked = sum(1 for r in rows.values() if r.get("verdict") == "BLOCKED")
    if args.allow_blocked is not None and n_blocked > args.allow_blocked:
        errs.append(f"{n_blocked} BLOCKED rows exceeds --allow-blocked={args.allow_blocked}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(render(rows, decisions, args.group_by))

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
