# Worked Example — Spec-Conformance Audit

> **This is the KNOWN archetype** — the deliverable *is* the verdict, so the contract is audit-shaped
> end to end. Do **not** copy its shape onto a DONE job (implement / fix-all / investigate-then-fix /
> migrate / produce-artifact). There the mission is an imperative, P1′ authors a failing oracle and
> observes it red, P2′ makes the change, the gate runs `--mode done`, and the deliverable is the
> artifact — not `REPORT.md`.

The request, roughly as it arrived:

> Read these design docs deeply. Check what we did in PR #128 task by task, make sure everything in the
> planning is fully implemented and the code sits in the right place. Don't ask me questions — run a
> team of engineer, UI/UX, domain expert, analyst and let them decide.
> Think deeply but don't waste tokens.

Six requirements, three of them in tension. What follows is how each was translated.

---

## Translation table

| In the request | In the contract | Why this form |
|---|---|---|
| "check task by task" | `ledger.jsonl`, one atomic row per task/constant/gap | Makes the work countable. Prose reviews cannot be audited for completeness; a ledger can. |
| "make sure fully implemented" | Evidence standard: PASS needs `path:line` **and** an executed `proof_cmd` | Directly targets "looks done". Uncalled code → PARTIAL. Constant defined but unenforced → FAIL. |
| "run a team of…" | Roles mapped 1:1 onto the review panel already named in their docs (`reviewer-domain` … `reviewer-architect`) | The panel existed. Each role reads only its own doc — real isolation, and names the user trusts. |
| "don't ask me" | §5 ordered tie-break + `decisions.jsonl` | "Don't ask" is a request for autonomy, not for guessing. Ordered rules terminate; panel votes deadlock. |
| "think deeply" | Phase gates with countable completeness checks | Depth as a structural property, not an instruction to try harder. |
| "don't waste tokens" | §4 binding policy + P2→P3 cascade | The two together, not either alone. |

---

## The three decisions that carried the contract

**Their `Gate:` lines became the oracle.** The roadmap already had a `Gate:` line per epic — pre-written,
ratified acceptance criteria. Every one entered the ledger **verbatim**. This was the highest-leverage
move available and it cost nothing: the criteria already existed, and the only real risk was an agent
paraphrasing them into something softer.

Generalisation: before designing any oracle, search for one the user already wrote.

**Deterministic sweep before the expensive panel.** Roughly two thirds of rows reduce to "does this
symbol exist, is it called, does this test pass, does this constant equal the ratified value" — all
settleable with `rg` and a test runner. Only the remainder reached the panel.

Cost fell and accuracy rose at the same time, because grep does not confabulate.

**The 499-line spec was never opened whole.** Section index in P0, then `sed -n 'a,bp'` for one section
at a time in P1. Opened once in full, it re-bills every subsequent turn — the quadratic term in a
40-turn job.

---

## Phase shape

```
P0  deterministic recon      gh pr view / rg for Gate: lines / symbol map     ~0 tokens
P1  requirement extraction   roadmap + decisions full; spec by section        expensive, necessarily
P2  deterministic sweep      rg / tests / typecheck per row                   ~0 tokens, ~65% of rows
P3  role panel               one batched spawn per role, only OPEN rows      the real cost
P4  adversarial              their own red-team table, run against the code   medium
P5  fold                     script joins ledger+verdicts, non-zero on gaps   ~0 tokens
```

P1 is deliberately the expensive phase and its gate is deliberately strict — it prints a count per
category and treats any zero as extraction failure. An incomplete ledger means every later phase
audits the wrong thing with full confidence. **P1 is not where to economise.**

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
