# Loop Engineering — the discipline this skill implements

Everything in `loop-contract` is an implementation of one idea. This document is that idea, stated
plainly, so the skill's design choices read as consequences rather than preferences.

For the sources behind each claim see [`SOURCES.md`](SOURCES.md); for the audit of *this* skill against
the requirements below see [`REQUIREMENTS.md`](REQUIREMENTS.md).

---

## 1. What a loop actually is

A language model, by itself, is one-shot: text in, text out, no memory, no actions. An **agent** is that
model placed inside a loop:

```
until done:
    look at the current state
    decide on an action          (a tool call)
    execute it
    append the result to state
    repeat
```

That is the whole architecture of every modern coding agent. Five lines.

**Loop engineering is the craft of designing that loop** — as opposed to designing the prompt inside it.
It begins the moment you accept that "use a better model" is not the only variable. Two people with the
same model build very different agents: one runs unattended for hours, the other is lost by step four.
The difference is almost never the model.

### The lineage

| Layer | The question it answers |
|---|---|
| Prompt engineering | how do I *phrase* the task? |
| Context engineering | *what* should be in the window? |
| Harness engineering | what *environment* is the model wired into — tools, files, feedback? |
| **Loop engineering** | how does this cycle *repeat, verify, and recover*? |

Each subsumes the last. The reason the last one exists: **in real engineering work the opening
instruction never determines the whole path.** Conflicting dependencies, malformed inputs, a test that
fails for an unrelated reason — these appear only at runtime. You cannot write the path in advance, so
you build a system that finds the path while running.

---

## 2. Anatomy — six parts, no exceptions

| Part | What it is | Where `loop-contract` puts it |
|---|---|---|
| **State** | what survives between iterations | the spine on disk — `scope/ledger/verdicts/decisions/metrics.jsonl` |
| **Policy** | model + instructions; state → action | the contract itself, re-read each phase |
| **Action space** | the tools it *may* use | the token policy's progressive disclosure |
| **Environment** | where actions actually happen | the repo, the shell, the data |
| **Observation** | what comes back and enters state | `proof_cmd` output, executed and recorded |
| **Termination** | when it stops | §1 — success · budget · stall · approval |

The two hardest parts are the last two: what you let back into context, and when you stop. Most loops
get both wrong.

---

## 3. The five failure modes

These are the whole reason the discipline exists. Every section of a contract defeats one.

**1 · Compounding error.** Multiply per-step reliability across a long chain and it collapses — the
arithmetic is unforgiving well before step fifty. The answer is not a better model; it is **recovery**,
which breaks the multiplication. Hence a gate at every phase boundary instead of one at the end.

**2 · Context rot.** A 200k window means you *may* use 200k, not that you should. Every token spent
costs money *and* attention: attention is a finite budget spread thinner as the window grows, so
retrieval quality degrades long before the window is full. A raw 3,000-token API dump steals attention
from the next decision.

**3 · Quadratic cost.** Each turn re-sends the history, so cumulative billed input grows with the
*square* of turn count — twenty turns adding 5k each is not 100k but over a million tokens. Note this is
a **different** quadratic from the attention one above; conflating them is the standard error. Both
argue for a small window; only one is about billing.

**4 · Dead loops and oscillation.** The same tool with the same arguments forty times; fixing A breaks
B, fixing B breaks A; by step thirty the agent is solving something adjacent to the task. A step cap
alone doesn't catch these — it lets the loop burn every step going in circles, then report as though it
merely ran out of room.

**5 · Silent failure — the dangerous one.** Absent an external check, an agent optimises for the
*appearance* of completion. It says "done ✅" and it is not done. Without an oracle you have no way to
know, and neither does it.

---

## 4. The central law

> **An agent's power is not bounded by its model. It is bounded by its verifier.**

How long a loop can safely run without a human is directly proportional to the quality of the check that
tells it whether it succeeded. Everything else in this document is marginal optimisation.

Verifiers, strongest first:

| Kind | Example | Strength |
|---|---|---|
| Deterministic | compiler, test suite, schema validation, exit code | ★★★★★ |
| Executable | benchmark, replay, reconciliation, reproduction | ★★★★ |
| Panel + rubric | an isolated grader scoring against criteria it did not author | ★★★ |
| Self-check | "review your work and confirm it's right" | ★ |

The golden rule: **before granting an agent a new capability, ask how you will know it did the job
correctly. If there is no answer, don't grant it.**

Two corollaries this skill leans on heavily:

- **The producer cannot grade itself.** Self-review without an external signal reliably fails; a checker
  that never saw the producer's reasoning finds materially more.
- **The model builds the oracle; it never *is* the oracle.** Asked to judge objective correctness, even
  strong models score near chance. But asked *what must be true here*, they are excellent. Let the model
  propose the invariant; let execution deliver the verdict.

---

## 5. Loops inside loops

The single agent loop is only the innermost ring:

```
┌─ Loop 4 · Hill climbing (days–weeks) ─────────────────┐
│   run evals → find the weakness → improve the harness │
│  ┌─ Loop 3 · Application (per user) ───────────────┐  │
│  │   user → agent → output → feedback              │  │
│  │  ┌─ Loop 2 · Verification (per task) ────────┐  │  │
│  │  │   produce → check → correct               │  │  │
│  │  │  ┌─ Loop 1 · Agent (seconds) ─────────┐   │  │  │
│  │  │  │   reason → act → observe           │   │  │  │
│  │  │  └────────────────────────────────────┘   │  │  │
│  │  └───────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────┘
```

Most teams build Loop 1 and stop. **The compounding advantage is in Loop 4** — a system that improves
itself against measured outcomes. In this skill that is `retro.md`, ratified decisions carried forward
as priors, and the rule that a lesson which *could* be a command should stop being a sentence.

---

## 6. What follows from all of this

Each rule in the skill is a consequence of something above — not a style preference:

| Rule | Follows from |
|---|---|
| Find the oracle before writing anything else | §4 — the verifier bounds everything |
| The oracle is observed **red** before the work | §3.5 — otherwise completion is satisfiable by a report |
| Scope frozen and counted from *the source* | §3.5 — the agent that under-counts also supplies the count |
| One proof per item, never one for the batch | §3.5 — a shared proof is the signature of work not done |
| A gate that **runs** the check rather than reading a claim | §4 — a claim about an exit code is not an exit code |
| Phase gates rather than one final check | §3.1 — break the multiplication |
| Evidence as `path:line`, bulk output to disk | §3.2, §3.3 — both quadratics |
| Append-only spine, `PROGRESS.md` re-read each phase | §2 state, §3.4 — recitation defeats drift |
| Termination in four kinds, not a step cap | §3.4 — a step cap alone permits circling |
| Sub-agents for isolation, writes single-threaded | §2 action space; parallel writers make conflicting decisions |
| Retro + ratified priors across runs | §5 — Loop 4 is where the advantage compounds |

If you disagree with a rule, the productive argument is with the failure mode behind it.

---

## 7. Where this skill deliberately stops

Loop engineering also covers things a *document* cannot enforce: sandboxing, credential scoping,
inference-time cache measurement, an automated multi-run eval harness. The skill names those and hands
them to the runtime rather than pretending prose can enforce them — see the out-of-scope table in
[`REQUIREMENTS.md`](REQUIREMENTS.md).

The honest boundary: this skill makes the right thing *structural and checkable*. It cannot make an
agent run the gate. That last step is compliance, and it is stated as an open item rather than hidden.
