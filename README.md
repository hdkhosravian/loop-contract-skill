# loop-contract

A [Claude Code](https://docs.claude.com/en/docs/claude-code) skill that turns a rough, long-running task
into something an agent can actually finish — and **proves** it finished, rather than saying so.

The problem it exists for: an agent asked to "implement the remaining tasks" will produce a plan, do the
three easy items, add one test, and report success. Every part of that is individually defensible and
the whole is a failure. This skill makes that failure *structurally hard*.

```
you: "implement all 42 tasks and fix the issues"

  freeze scope        42 items, counted from YOUR source, sha-pinned — the job cannot shrink
  author the oracle   a check that FAILS right now and can only go green by doing the work
  per item            red → change → green → record its own proof
  the gate            runs the oracle itself and exits non-zero on anything unproven

  → working code, and an exit line you can check
```

## What makes it different

**The gate executes; it does not read.** `fold_ledger.py` runs your achievement oracle, resolves every
cited path, and exits non-zero if anything is unproven. A "done" claim without its exit line is void.

**Scope is frozen before the work and counted from the source.** The count comes from *your* number or a
recount command the gate runs — never from the agent's own enumeration, because the agent that
under-counts also supplies the count.

**Every item carries its own proof.** One smoke test cited for twenty rows is rejected — that pattern is
the signature of work that was not done.

**Two modes, one axis.** *"If the run returns a perfect report and changed nothing, are you happy?"*
No → **DONE** (the deliverable is the change). Yes → **KNOWN** (the deliverable is a verdict). Both
write a contract and then execute it.

**Domain-general.** Code, data, finance, research, plans. Reconciliation, invariants and metamorphic
relations are oracles too — a job with no test suite is rarely a job with no oracle.

## Install

**As a Claude Code plugin** (recommended — one command, updates with `/plugin`):

```
/plugin marketplace add hdkhosravian/loop-contract-skill
/plugin install loop-contract@loop-contract
```

**Or manually**, if you prefer a plain skill directory:

```bash
git clone https://github.com/hdkhosravian/loop-contract-skill /tmp/lc \
  && cp -r /tmp/lc/skills/loop-contract ~/.claude/skills/
```

Then just describe the work. `/loop-contract` also works, but is rarely needed.


## Using it

You never type a flag or a path — those belong to the agent.

| you say | it does |
|---|---|
| "implement all the remaining tasks" | freezes scope, works each item red→green, gates |
| "review PR #128 and find what's missing" | KNOWN run — findings with evidence and executed proofs |
| "find the bugs and fix them" | finds, then fixes and verifies each (not a findings list) |
| "reconcile these three CSVs" | reconciliation as the oracle; exceptions as the deliverable |
| "design a marketing plan" | the plan itself, checked against ratified per-component criteria |
| **"continue"** / "what's left?" | finds the spine on disk, recomputes the remainder, carries on |
| "audit this every week" | a recurring contract that reports **what changed**, not the same list |

## How completion is decided

```bash
python3 scripts/fold_ledger.py \
  --ledger .claude/loops/<job>/ledger.jsonl \
  --verdicts .claude/loops/<job>/verdicts.jsonl \
  --scope   .claude/loops/<job>/scope.jsonl \
  --mode done --oracle-cmd "pytest tests/" --expect-scope-count 42 \
  --out .claude/loops/<job>/REPORT.md
```

Fails on: a scoped item with no verdict · `FAIL`/`PARTIAL` in a DONE run · `PASS` with no recorded fix ·
rows sharing a `proof_cmd` · a citation that does not resolve · a `FAIL` quietly re-appended as `PASS` ·
a scope smaller than the source · a red oracle. Run `--remaining` for the resume worklist.

## Layout

| Path | What |
|---|---|
| `skills/loop-contract/SKILL.md` | entry point — triage, the DONE/KNOWN axis, the workflow |
| `skills/loop-contract/references/contract-template.md` | the contract skeleton |
| `skills/loop-contract/references/oracle-catalog.md` | the eight-rung oracle ladder; anti-oracles; oracles without tests |
| `skills/loop-contract/references/token-policy.md` | the cost arithmetic and the binding rules |
| `skills/loop-contract/references/subagent-contracts.md` | roles, spawn contract, coverage panel vs repeatability |
| `skills/loop-contract/references/triage-routing.md` | route / do-it / contract, and splitting a mixed request |
| `skills/loop-contract/references/outer-loops.md` | trajectory metrics, `pass^k`, hill-climbing across runs |
| `skills/loop-contract/references/recurring-jobs.md` | a contract on a schedule; the delta is the deliverable |
| `skills/loop-contract/references/execution-protocol.md` | running a contract on a Claude Code host |
| `skills/loop-contract/references/worked-example.md` | an annotated spec-conformance audit |
| `skills/loop-contract/scripts/fold_ledger.py` | the gate |
| `skills/loop-contract/scripts/extract_requirements.py` | a recall net over markdown — **not** the extractor |
| `docs/REQUIREMENTS.md` | the 32-requirement conformance matrix, and what is out of scope |
| `docs/SOURCES.md` | every empirical claim, its source, and which are house heuristics |

Run state lives in `.claude/loops/<job-slug>/`, one directory per job. Deliverables do **not** — that
directory is usually gitignored, and the artifact must outlive the run.

## Design principles

1. **An agent's reliability is bounded by its verifier, not its model.**
2. **The model reads and decides; a script confirms the result.** Comprehension is semantic and belongs
   to the model; verification must be ungameable and belongs to code. Reversing this is how a 42-task
   job silently becomes 35.
3. **Completion must be unsatisfiable by documentation.** The oracle is written red before the work, so
   no amount of eloquent reporting turns it green.
4. **A partial result with honest gaps beats a complete-looking one with invented passes.** `BLOCKED`
   with a reason is a legitimate output; a false `PASS` is the only unacceptable one.

## Honest limitations

- **The gate is opt-in.** Every check happens only if the agent runs it. The skill makes that norm as
  sharp as prose can; it is compliance, not enforcement.
- **Not yet proven end-to-end** on a multi-session job that exceeds one context window. The gate is
  verified against fixtures; the behavioural half is not.
- **`extract_requirements.py` is a recall net.** Its regexes find the conventions their author
  anticipated. On a project that writes requirements as prose it returns nothing useful. Read the
  source yourself; use the script to catch what you missed.

See `docs/SOURCES.md` for what is measured, what is practitioner consensus, and what is our own rule of
thumb — the three are never blended.
