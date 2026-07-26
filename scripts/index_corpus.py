#!/usr/bin/env python3
"""
index_corpus.py — enumerate every readable line of the corpus into shards.

Deterministic. stdlib only. This script **does not decide what a requirement is** — that is the
judgement a regex cannot make and a model can. It only answers the question a model cannot answer
reliably: *what is the complete set of text that must be looked at?*

That division is the point. The old extractor filtered lines with regexes, so anything phrased
outside the anticipated conventions vanished silently and a zero count looked like an empty
document. This script filters nothing. It emits a shard for every line range of every readable
file, and prints — loudly — everything it could not read and why. A source can now be missed only
if this manifest omits it, and the manifest is auditable.

The manifest is also the coverage contract: `verify_harvest.py` fails the harvest unless every
shard here has an explicit disposition, so "nobody ever read that file" becomes a non-zero exit
rather than a silent gap.

Usage:
    python index_corpus.py docs/ -o audit/shards.jsonl
    python index_corpus.py docs/ src/ --max-lines 80 --ext .md,.py,.sql
    python index_corpus.py . --git --exclude 'vendor/*' --exclude '*.lock'

Shard row:
    {"shard":"docs/spec.md#004","path":"docs/spec.md","start":88,"end":141,
     "heading":"Execution > Gates","lines":54,"sha1":"<of the shard text>"}

Line numbers are 1-indexed and inclusive on both ends.
"""

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys

FENCE = re.compile(r"^\s*(?:```|~~~)")
HEADING = re.compile(r"^(#{1,6})\s+(\S.*?)\s*$")

MARKDOWN_EXT = {".md", ".markdown", ".mdx", ".rst", ".txt", ".adoc"}

# Directories that are never a source of requirements. Everything skipped is reported.
PRUNE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache",
              ".pytest_cache", ".ruff_cache", "dist", "build", ".next", "target"}


def is_binary(path, probe=8192):
    try:
        with open(path, "rb") as fh:
            return b"\0" in fh.read(probe)
    except OSError:
        return True


def git_tracked(root):
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "-z"],
                             capture_output=True, check=True).stdout
        return {os.path.normpath(os.path.join(root, p))
                for p in out.decode("utf-8", "replace").split("\0") if p}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def walk(paths, exts, excludes, tracked, max_bytes, skipped):
    """Yield every candidate file. Anything rejected lands in `skipped` with a reason."""
    seen = set()

    def consider(p):
        p = os.path.normpath(p)
        if p in seen:
            return
        seen.add(p)
        rel = p
        if any(fnmatch.fnmatch(rel, pat) for pat in excludes):
            return skipped.append((rel, "matched --exclude"))
        if tracked is not None and p not in tracked:
            return skipped.append((rel, "not tracked by git (--git)"))
        ext = os.path.splitext(p)[1].lower()
        if exts and ext not in exts:
            return skipped.append((rel, f"extension {ext or '(none)'} not in --ext"))
        try:
            size = os.path.getsize(p)
        except OSError as e:
            return skipped.append((rel, f"unreadable: {e.strerror}"))
        if size > max_bytes:
            return skipped.append((rel, f"{size} bytes > --max-bytes (raise it or shard by hand)"))
        if is_binary(p):
            return skipped.append((rel, "binary"))
        yielded.append(p)

    yielded = []
    for root in paths:
        if os.path.isfile(root):
            consider(root)
        elif os.path.isdir(root):
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = sorted(d for d in dirnames if d not in PRUNE_DIRS)
                for n in sorted(filenames):
                    consider(os.path.join(dirpath, n))
        else:
            skipped.append((root, "no such path"))
    return sorted(yielded)


def heading_spans(lines):
    """(start, end, heading_path) per markdown section. Preamble is its own span."""
    marks, stack, in_fence = [], ["", "", "", "", "", ""], False
    for i, line in enumerate(lines, 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        h = HEADING.match(line)
        if not h:
            continue
        depth = len(h.group(1))
        stack[depth - 1] = h.group(2).strip()
        for d in range(depth, 6):
            stack[d] = ""
        marks.append((i, " > ".join(s for s in stack if s)))

    spans = []
    if not marks or marks[0][0] > 1:
        spans.append((1, (marks[0][0] - 1) if marks else len(lines), "(preamble)"))
    for idx, (start, path) in enumerate(marks):
        end = marks[idx + 1][0] - 1 if idx + 1 < len(marks) else len(lines)
        spans.append((start, end, path))
    return [(a, b, h) for a, b, h in spans if b >= a]


def chunk(spans, max_lines):
    """Split any span longer than max_lines. Oversized sections are the usual silent-skip trap."""
    out = []
    for start, end, head in spans:
        if end - start + 1 <= max_lines:
            out.append((start, end, head))
            continue
        part, cursor = 1, start
        while cursor <= end:
            stop = min(cursor + max_lines - 1, end)
            out.append((cursor, stop, f"{head} (part {part})"))
            cursor, part = stop + 1, part + 1
    return out


def shards_for(path, max_lines):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    if not lines:
        return [], 0

    if os.path.splitext(path)[1].lower() in MARKDOWN_EXT:
        spans = chunk(heading_spans(lines), max_lines)
    else:
        spans = [(s + 1, min(s + max_lines, len(lines)), "")
                 for s in range(0, len(lines), max_lines)]

    rows = []
    for n, (start, end, head) in enumerate(spans):
        text = "\n".join(lines[start - 1:end])
        rows.append({
            "shard": f"{path}#{n:03d}",
            "path": path,
            "start": start,
            "end": end,
            "heading": head,
            "lines": end - start + 1,
            "sha1": hashlib.sha1(text.encode("utf-8")).hexdigest(),
        })
    return rows, len(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="files or directories to index")
    ap.add_argument("-o", "--out", default="-", help="output jsonl path (default stdout)")
    ap.add_argument("--max-lines", type=int, default=120,
                    help="split any section longer than this (default 120)")
    ap.add_argument("--ext", default="",
                    help="comma-separated extensions to keep, e.g. '.md,.py'. Default: everything readable")
    ap.add_argument("--exclude", action="append", default=[], help="glob to skip (repeatable)")
    ap.add_argument("--git", action="store_true", help="index only git-tracked files")
    ap.add_argument("--max-bytes", type=int, default=2_000_000, help="per-file size ceiling")
    args = ap.parse_args()

    exts = {e if e.startswith(".") else "." + e
            for e in (x.strip().lower() for x in args.ext.split(",")) if e}
    tracked = git_tracked(args.paths[0] if os.path.isdir(args.paths[0]) else ".") if args.git else None
    if args.git and tracked is None:
        print("ERROR: --git given but this is not a git repo (or git is unavailable)", file=sys.stderr)
        return 2

    skipped = []
    files = walk(args.paths, exts, args.exclude, tracked, args.max_bytes, skipped)

    rows, total_lines = [], 0
    for p in files:
        got, n = shards_for(p, args.max_lines)
        rows.extend(got)
        total_lines += n

    if not rows:
        print("ERROR: indexed 0 shards — every candidate was skipped. See the SKIPPED list above; "
              "widen --ext / --exclude or drop --git.", file=sys.stderr)

    out = sys.stdout if args.out == "-" else open(args.out, "w", encoding="utf-8")
    try:
        for r in rows:
            out.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    finally:
        if out is not sys.stdout:
            out.close()

    print(f"indexed {len(files)} file(s) · {total_lines} line(s) · {len(rows)} shard(s) -> {args.out}",
          file=sys.stderr)
    if skipped:
        print(f"SKIPPED {len(skipped)} path(s) — read this list, a lost source hides here:", file=sys.stderr)
        for p, why in skipped[:60]:
            print(f"  - {p}  ({why})", file=sys.stderr)
        if len(skipped) > 60:
            print(f"  ... and {len(skipped) - 60} more", file=sys.stderr)
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
