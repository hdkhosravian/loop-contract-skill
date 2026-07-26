# Worked Example — Spec-Conformance Audit

The request, roughly as it arrived:

> Read these design docs deeply. Check what we did in PR #57 task by task, make sure everything in the
> planning is fully implemented and the code sits in the right place. Don't ask me questions — run a
> team of engineer, UI/UX, trader, economist, mathematician, statistician and let them decide.
> Think deeply but don't waste tokens.

Six requirements, three of them in tension. What follows is how each was translated.

---

## Translation table

| In the request | In the contract | Why this form |
|---|---|---|
| "check task by task" | `ledger.jsonl`, one atomic row per task/constant/gap | Makes the work countable. Prose reviews cannot be audited for completeness; a ledger can. |
| "make sure fully implemented" | Evidence standard: PASS needs `path:line` **and** an executed `proof_cmd` | Directly targets "looks done". Uncalled code → PARTIAL. Constant defined but unenforced → FAIL. |
| "run a team of…" | Roles mapped 1:1 onto the panel already in their docs (`seat-1-trader` … `seat-6-architect`) | The panel existed. Each seat reads only its own doc — real isolation, and names the user trusts. |
| "don't ask me" | §5 ordered tie-break + `decisions.jsonl` | "Don't ask" is a request for autonomy, not for guessing. Ordered rules terminate; panel votes deadlock. |
| "think deeply" | Phase gates with countable completeness checks | Depth as a structural property, not an instruction to try harder. |
| "don't waste tokens" | §4 binding policy + P2→P3 cascade | The two together, not either alone. |

---

## The three decisions that carried the contract

**Their `Gate:` lines became the oracle.** The roadmap already had a `Gate:` line per epic — pre-written,
ratified acceptance criteria. Every one entered the ledger **verbatim**. This was the highest-leverage
move available and it cost nothing: the criteria already existed.

The risk here is two-sided, and only one side is obvious. Paraphrasing a `Gate:` line softens it — that
is the visible risk, and grounding every claim at `path:line` kills it. The invisible one is that the
labelled lines are not the whole spec: harvest only what is labelled and you inherit a scope that looks
complete and is not. Both sides need an answer, and they need different ones.

Generalisation: before designing any oracle, search for one the user already wrote — then assume the
labelled ones are the minority.

**Deterministic sweep before the expensive panel.** Roughly two thirds of rows reduce to "does this
symbol exist, is it called, does this test pass, does this constant equal the ratified value" — all
settleable with `rg` and a test runner. Only the remainder reached the seats.

Cost fell and accuracy rose at the same time, because grep does not confabulate.

**The 499-line spec was never opened whole.** Section index in P0, then `sed -n 'a,bp'` for one section
at a time in P1. Opened once in full, it re-bills every subsequent turn — the quadratic term in a
40-turn job.

---

## Phase shape

```
P0  deterministic recon      gh pr view / index_corpus.py / symbol map        ~0 tokens
P1  harvest                  sharded harvesters -> ground -> recall sweep     expensive, necessarily
P2  deterministic sweep      rg / tests / typecheck per row                   ~0 tokens, ~65% of rows
P3  seat panel               one batched spawn per seat, only OPEN rows       the real cost
P4  adversarial              their own red-team table, run against the code   medium
P5  fold                     script joins ledger+verdicts, non-zero on gaps   ~0 tokens
```

P1 is deliberately the expensive phase and its gate is deliberately strict. An incomplete ledger means
every later phase audits the wrong thing with full confidence. **P1 is not where to economise** — and
the first version of this skill economised there anyway, extracting with regexes over markdown. It
found the roadmap's labelled `Gate:` lines and silently missed the invariants that lived in prose, in
the migration files, and in three test names. The count it printed looked like coverage.

The fix was not a better regex. It was moving the boundary: `index_corpus.py` enumerates every line of
the corpus (it filters nothing, so it cannot drop a source), harvester sub-agents read the shards and
judge what constrains the implementation, and `verify_harvest.py` proves every returned claim really
appears verbatim at its cited line and that no shard went unread. Recall from the model, precision from
a byte comparison. See `references/harvest-protocol.md`.

## The gate that makes "done" a fact

`fold_ledger.py` exits non-zero on any missing, duplicate, or non-terminal row. The agent cannot
declare completion; it can only make the script exit 0. That is the difference between a completion
condition and a completion claim.

## What generalises

- Harvest the user's existing criteria verbatim before writing any of your own.
- Map roles onto names the user already uses.
- Classify aggressively as deterministic; escalate only the remainder.
- Make the completion gate a script exit code, never a judgement.
- Treat "don't ask me" as a request for an ordered tie-break, not for guesswork.
- Never open the large authoritative document whole.
