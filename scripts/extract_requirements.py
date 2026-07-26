#!/usr/bin/env python3
"""
extract_requirements.py — pull acceptance criteria out of markdown into a ledger.

Deterministic. No model, no network, stdlib only. Every row it emits is a verbatim
copy of text the user already wrote, which is the point: paraphrased criteria are
softened criteria, and softened criteria are how a false PASS gets manufactured.

Usage:
    python extract_requirements.py docs/**/*.md -o audit/ledger.jsonl
    python extract_requirements.py docs/roadmap.md --pattern 'Gate:' --kind gate
    python extract_requirements.py docs/ -o ledger.jsonl --stats

Tune PATTERNS to the project's own conventions before relying on the counts.
"""

import argparse
import glob
import json
import os
import re
import sys

# (kind, compiled regex, capture group holding the requirement text)
# Order matters: the first pattern that matches a line wins.
PATTERNS = [
    # "Gate: all disposition writes go through the episode writer"
    ("gate", re.compile(r"^\s*(?:[-*]\s*)?\*{0,2}Gate\*{0,2}\s*:\s*(?P<text>.+?)\s*$", re.I), "text"),
    # "AC-3: ..." / "AC: ..."
    ("ac", re.compile(r"^\s*(?:[-*]\s*)?\*{0,2}AC(?:-\d+)?\*{0,2}\s*:\s*(?P<text>.+?)\s*$"), "text"),
    # "- [ ] T1a.3 single-writer enforced"   (unchecked = still open)
    ("task", re.compile(r"^\s*[-*]\s*\[(?P<mark>[ xX])\]\s*(?P<text>.+?)\s*$"), "text"),
    # normative statements
    ("normative", re.compile(r"^\s*(?:[-*]\s*)?(?P<text>.*\b(?:MUST NOT|MUST|SHALL NOT|SHALL|REQUIRED)\b.*?)\s*$"), "text"),
    # "| MAX_DRAWDOWN | 0.15 |"  or  "MAX_DRAWDOWN = 0.15"  or  "`X`: 0.15"
    ("constant", re.compile(r"^\s*\|?\s*`?(?P<name>[A-Z][A-Z0-9_]{2,})`?\s*[|=:]\s*(?P<val>[^|]+?)\s*\|?\s*$"), None),
    # gap / risk registers: "G-4: ..." / "R-2 | ..." / "LB1 — ..."
    ("gap", re.compile(r"^\s*\|?\s*\*{0,2}(?P<id>[A-Z]{1,3}-?\d+)\*{0,2}\s*[|:—–-]\s*(?P<text>.+?)\s*\|?\s*$"), "text"),
]

# Lines under these headings are skipped — they describe the work, they are not the work.
SKIP_HEADING = re.compile(r"^#{1,6}\s*(example|appendix|glossary|changelog|references?|notes?)\b", re.I)

ID_HINT = re.compile(r"\b((?:LB|T|G|R|D|AC|EPIC)-?\d+[a-z]?(?:\.\d+)*)\b")


def iter_files(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                for n in sorted(names):
                    if n.endswith((".md", ".markdown")):
                        yield os.path.join(root, n)
        elif any(ch in p for ch in "*?["):
            yield from sorted(glob.glob(p, recursive=True))
        elif os.path.isfile(p):
            yield p


def current_section(stack):
    return " > ".join(s for s in stack if s)


def extract(path, only_kinds=None, extra_pattern=None, extra_kind="custom"):
    rows, stack, skipping = [], ["", "", "", "", "", ""], False
    in_fence = False

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")

            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            h = re.match(r"^(#{1,6})\s+(.*)$", line)
            if h:
                depth = len(h.group(1))
                stack[depth - 1] = h.group(2).strip()
                for d in range(depth, 6):
                    stack[d] = ""
                skipping = bool(SKIP_HEADING.match(line))
                continue
            if skipping or not line.strip():
                continue

            pats = list(PATTERNS)
            if extra_pattern:
                pats.insert(0, (extra_kind, re.compile(extra_pattern), "text"))

            for kind, rx, grp in pats:
                if only_kinds and kind not in only_kinds:
                    continue
                m = rx.match(line)
                if not m:
                    continue

                gd = m.groupdict()
                if kind == "constant":
                    text = f"{gd['name']} == {gd['val'].strip()}"
                    if not re.search(r"[\d\"'\[]|true|false|null", gd["val"], re.I):
                        break  # prose, not a value
                else:
                    text = (gd.get(grp) or "").strip()

                if len(text) < 8 or text.startswith(("http", "|---", "---")):
                    break

                idm = ID_HINT.search(text) or ID_HINT.search(current_section(stack))
                rows.append({
                    "id": (gd.get("id") or (idm.group(1) if idm else None)
                           or f"{kind.upper()}-{os.path.basename(path)}-{lineno}"),
                    "src": f"{path}:{lineno}",
                    "section": current_section(stack),
                    "kind": kind,
                    "claim": text,               # VERBATIM. never rewrite this field.
                    "check": "deterministic" if kind == "constant" else "unclassified",
                    "status": "OPEN",
                })
                if kind == "task" and gd.get("mark", " ").lower() == "x":
                    rows[-1]["doc_says_done"] = True
                break
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="markdown files, globs, or directories")
    ap.add_argument("-o", "--out", default="-", help="output jsonl path (default stdout)")
    ap.add_argument("--pattern", help="extra regex with a (?P<text>...) group")
    ap.add_argument("--kind", default="custom", help="kind label for --pattern")
    ap.add_argument("--only", help="comma-separated kinds to keep")
    ap.add_argument("--stats", action="store_true", help="print per-kind counts to stderr")
    args = ap.parse_args()

    only = set(args.only.split(",")) if args.only else None
    rows, seen = [], set()

    for path in iter_files(args.paths):
        for r in extract(path, only, args.pattern, args.kind):
            key = (r["kind"], r["claim"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(r)

    # disambiguate repeated ids
    counts = {}
    for r in rows:
        counts[r["id"]] = counts.get(r["id"], 0) + 1
        if counts[r["id"]] > 1:
            r["id"] = f"{r['id']}#{counts[r['id']]}"

    out = sys.stdout if args.out == "-" else open(args.out, "w", encoding="utf-8")
    try:
        for r in rows:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    finally:
        if out is not sys.stdout:
            out.close()

    if args.stats or args.out != "-":
        by = {}
        for r in rows:
            by[r["kind"]] = by.get(r["kind"], 0) + 1
        print(f"extracted {len(rows)} rows -> {args.out}", file=sys.stderr)
        for k in sorted(by):
            print(f"  {k:<12} {by[k]}", file=sys.stderr)
        missing = [k for k, _, _ in PATTERNS if k not in by]
        if missing:
            print(f"  ZERO rows for: {', '.join(missing)}", file=sys.stderr)
            print("  A zero here usually means the pattern does not match this project's"
                  " conventions. Tune PATTERNS before trusting these counts.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
