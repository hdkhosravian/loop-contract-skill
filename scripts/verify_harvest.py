#!/usr/bin/env python3
"""
verify_harvest.py — prove the harvested ledger is grounded in the corpus and covers all of it.

Deterministic. stdlib only. This is the gate that makes model-driven extraction *safer* than the
regex extractor it replaces, rather than merely broader.

A regex guaranteed verbatim text by construction — but only over the lines it happened to match,
and it had no way to notice the lines it missed. A model reads everything and understands prose,
but can paraphrase (which softens a criterion) or invent (which manufactures one). Both of those
failures are mechanically checkable, and this script checks them:

    GROUNDING  every row's `claim` must appear verbatim in its own source file at its own `src`
               line, within a small window. A paraphrase does not appear. An invention does not
               appear. Neither survives this check.
    COVERAGE   every shard in the manifest must carry an explicit disposition — rows, or a stated
               "no requirements here" with a reason. A file nobody read is a non-zero exit, not a
               silent gap. This is the check the regex extractor could never have.

Exit codes:
    0  every row grounded, every shard accounted for
    1  integrity failure (ungrounded rows, unharvested shards, duplicate ids)
    2  bad input

Usage:
    python verify_harvest.py --ledger audit/ledger.jsonl --shards audit/shards.jsonl \
                             --coverage audit/coverage.jsonl --out audit/HARVEST.md
    python verify_harvest.py --ledger audit/ledger.jsonl --shards audit/shards.jsonl --window 5
"""

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

SRC = re.compile(r"^(?P<path>.+?):(?P<start>\d+)(?:-(?P<end>\d+))?$")

# Typographic substitutions applied only in the loose tier, so a smart quote in the doc versus a
# straight quote in the claim is a warning rather than a false alarm.
FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                      "–": "-", "—": "-", "−": "-", " ": " "})

MIN_REASON = 12


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


def collapse(s):
    return re.sub(r"\s+", " ", s).strip()


def loose(s):
    s = unicodedata.normalize("NFKC", s).translate(FOLD)
    s = re.sub(r"[`*_]", "", s)
    return collapse(s).casefold()


class Corpus:
    """Line cache. Files are read once even when a hundred rows cite them."""

    def __init__(self):
        self._lines = {}

    def lines(self, path):
        if path not in self._lines:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    self._lines[path] = fh.read().splitlines()
            except OSError:
                self._lines[path] = None
        return self._lines[path]


def ground(row, corpus, window):
    """(status, detail) — EXACT | LOOSE | UNGROUNDED | NOFILE | BADSRC."""
    m = SRC.match(str(row.get("src", "")))
    if not m:
        return "BADSRC", f"src {row.get('src')!r} is not path:line"

    path = m.group("path")
    lines = corpus.lines(path)
    if lines is None:
        return "NOFILE", f"cannot read {path}"

    start = int(m.group("start"))
    end = int(m.group("end") or start)
    claim = str(row.get("claim", ""))
    if not claim.strip():
        return "UNGROUNDED", "empty claim"

    # A wrapped claim spans lines the harvester did not cite; widen by its own length.
    span = len(claim) // 40 + 2
    lo = max(1, start - window)
    hi = min(len(lines), end + window + span)
    if lo > len(lines):
        return "UNGROUNDED", f"{path} has {len(lines)} lines, src points at {start}"

    haystack = " ".join(lines[lo - 1:hi])
    if collapse(claim) in collapse(haystack):
        return "EXACT", ""
    if loose(claim) in loose(haystack):
        return "LOOSE", "matched only after unicode/markup normalisation"

    at = collapse(lines[start - 1])[:90] if start <= len(lines) else "(past end of file)"
    return "UNGROUNDED", f"not found within ±{window} lines of {path}:{start}; line reads: {at!r}"


def shard_of(row, shards_by_path):
    """Which manifest shard does this row's src fall inside? None if outside every shard."""
    m = SRC.match(str(row.get("src", "")))
    if not m:
        return None
    line = int(m.group("start"))
    for s in shards_by_path.get(m.group("path"), ()):
        if s["start"] <= line <= s["end"]:
            return s["shard"]
    return None


def check_hashes(shards, corpus):
    """A shard whose text changed since indexing invalidates every line number harvested from it."""
    stale = []
    for s in shards:
        lines = corpus.lines(s["path"])
        if lines is None:
            stale.append((s["shard"], "file no longer readable"))
            continue
        text = "\n".join(lines[s["start"] - 1:s["end"]])
        if hashlib.sha1(text.encode("utf-8")).hexdigest() != s.get("sha1"):
            stale.append((s["shard"], "content changed since indexing"))
    return stale


def render(rows, shards, statuses, unharvested, empty, stale, orphans, dupes, window):
    n_ok = sum(1 for s in statuses.values() if s[0] in ("EXACT", "LOOSE"))
    bad = {i: s for i, s in statuses.items() if s[0] not in ("EXACT", "LOOSE")}
    counts = Counter(s[0] for s in statuses.values())

    L = ["# Harvest Verification", "",
         f"- rows: **{len(rows)}** · grounded: **{n_ok}** · ungrounded: **{len(bad)}**",
         f"- shards: **{len(shards)}** · unharvested: **{len(unharvested)}** · "
         f"declared empty: **{len(empty)}**",
         "  ".join(f"`{k}: {v}`" for k, v in sorted(counts.items())), ""]

    def block(title, items, fmt, note=None):
        L.append(f"## {title}")
        L.append("")
        if not items:
            L.append("_none_")
            L.append("")
            return
        if note:
            L.extend([note, ""])
        for it in items[:200]:
            L.append(f"- {fmt(it)}")
        if len(items) > 200:
            L.append(f"- ... and {len(items) - 200} more")
        L.append("")

    block("Ungrounded rows", sorted(bad.items()),
          lambda kv: f"`{kv[0]}` — {kv[1][0]}: {kv[1][1]}",
          "Each of these is a paraphrase, an invention, or a wrong line number. "
          "Fix the ledger row against the source; do not relax this script.")
    block("Unharvested shards", sorted(unharvested),
          lambda s: f"`{s}` — no rows and no `no-requirements` record. Nobody read this.",
          "This is the lost-source check. A shard here was silently skipped.")
    block("Duplicate ids", sorted(dupes), lambda i: f"`{i}`")
    block("Rows outside every shard", sorted(orphans),
          lambda i: f"`{i}` — src is not inside any indexed shard; the corpus index missed this file.")
    block("Stale shards", stale, lambda t: f"`{t[0]}` — {t[1]}",
          "The corpus changed after indexing. Re-index and re-verify: line numbers have moved.")
    block("Shards declared empty", sorted(empty),
          lambda t: f"`{t[0]}` — {t[1]}",
          "Reviewable by eye. A wrong 'no requirements here' is how recall quietly drops.")

    L.append(f"_Grounding window: ±{window} lines. LOOSE rows matched only after normalisation._")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ledger", default="audit/ledger.jsonl")
    ap.add_argument("--shards", default="audit/shards.jsonl")
    ap.add_argument("--coverage", default="audit/coverage.jsonl")
    ap.add_argument("--out", default="audit/HARVEST.md")
    ap.add_argument("--window", type=int, default=3,
                    help="line drift tolerated when grounding a claim (default 3)")
    ap.add_argument("--allow-loose", action="store_true",
                    help="treat normalisation-only matches as clean instead of listing them")
    ap.add_argument("--strict-hash", action="store_true",
                    help="fail on stale shards instead of warning")
    args = ap.parse_args()

    ledger = load_jsonl(args.ledger)
    shards = load_jsonl(args.shards)
    coverage = load_jsonl(args.coverage, required=False)

    if not shards:
        print("ERROR: shard manifest is empty — run index_corpus.py first", file=sys.stderr)
        return 2
    if not ledger:
        print("ERROR: ledger is empty — the harvest produced nothing. That is a harvest failure, "
              "not an empty corpus; check coverage.jsonl for what the harvesters claimed.",
              file=sys.stderr)
        return 1

    corpus = Corpus()
    by_path = defaultdict(list)
    for s in shards:
        by_path[s["path"]].append(s)

    statuses, dupes, orphans, seen = {}, set(), set(), set()
    rows_per_shard = Counter()

    for r in ledger:
        rid = r.get("id") or f"(no id) {str(r.get('src'))}"
        if rid in seen:
            dupes.add(rid)
        seen.add(rid)
        statuses[rid] = ground(r, corpus, args.window)
        sh = r.get("shard") or shard_of(r, by_path)
        if sh is None:
            orphans.add(rid)
        else:
            rows_per_shard[sh] += 1

    declared = {c.get("shard"): c for c in coverage}
    all_shards = {s["shard"] for s in shards}

    unharvested, empty = set(), []
    for sid in all_shards:
        if rows_per_shard.get(sid):
            continue
        rec = declared.get(sid)
        reason = (rec or {}).get("reason", "")
        if rec and rec.get("status") in ("no-requirements", "unreadable") and len(reason) >= MIN_REASON:
            empty.append((sid, reason))
        else:
            unharvested.add(sid)

    stale = check_hashes(shards, corpus)

    errs = []
    errs += [f"{i}: {s[1]}" for i, s in sorted(statuses.items()) if s[0] not in ("EXACT", "LOOSE")]
    errs += [f"shard never harvested: {s}" for s in sorted(unharvested)]
    errs += [f"duplicate ledger id: {i}" for i in sorted(dupes)]
    errs += [f"row outside every indexed shard: {i}" for i in sorted(orphans)]
    if args.strict_hash:
        errs += [f"stale shard: {s} ({why})" for s, why in stale]

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(render(ledger, shards, statuses, unharvested, empty, stale,
                        orphans, dupes, args.window))

    n_loose = sum(1 for s in statuses.values() if s[0] == "LOOSE")
    if n_loose and not args.allow_loose:
        print(f"note: {n_loose} row(s) matched only after normalisation — listed in {args.out}",
              file=sys.stderr)
    if stale and not args.strict_hash:
        print(f"note: {len(stale)} shard(s) changed since indexing — line numbers may have moved",
              file=sys.stderr)

    if errs:
        print(f"HARVEST GATE FAILED — {len(errs)} error(s). Fix the ledger, not this script.",
              file=sys.stderr)
        for e in errs[:40]:
            print(f"  - {e}", file=sys.stderr)
        if len(errs) > 40:
            print(f"  ... and {len(errs) - 40} more", file=sys.stderr)
        return 1

    print(f"HARVEST GATE PASSED — {len(ledger)} rows grounded · "
          f"{len(all_shards)} shards accounted for -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
