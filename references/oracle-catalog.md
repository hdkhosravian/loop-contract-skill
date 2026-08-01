# Oracle Catalog

The oracle is the mechanism that decides success **without a human**. It is the load-bearing decision
in any contract: how long a loop can safely run is set by the quality of its verifier, not by the model.

Find it first. Everything else in the contract is a consequence of it.

## Contents

- Oracles by job type
- Ranking oracle strength
- Building an oracle when none exists
- Anti-oracles — things that look like verification and are not
- Jobs that should not be loops

---

## Oracles by job type

| Job | Oracle | Notes |
|---|---|---|
| Implement / build a feature | the acceptance test(s) for the new behaviour, written and observed **RED before** any implementation, then green + the pre-existing suite still green | Test-after-code is not an oracle. Written first, it is the one check a report cannot satisfy. |
| Fix-all remediation | each issue's own check now passes (recorded per row) + the full suite still green | Never one aggregate PASS over N fixes. |
| Investigate-then-fix | a repro that fails **for the right reason**, then goes green | Gate it: no fix work until the red is observed. |
| Root-cause analysis (diagnose only) | a reproduction (deterministic, or a stress loop for intermittents) **plus a necessity check**: suppress the hypothesised mechanism and show the symptom disappears, restore it and show it returns | A well-cited plausible story passes every citation check. Correlation is not cause — without the necessity check you ship the best-evidenced theory, and the bug recurs next week. |
| Produce-artifact (plan, design, curriculum) | ratified acceptance criteria per component **+ citation resolution + every number recomputed from its source** — see *Non-code deliverables* below | Component presence alone certifies a complete-looking document whose central claims are unchecked. |
| Spec conformance / audit | `Gate:` lines, ACs, MUST/SHALL, ratified constants, gap registers | Already written by the user. Harvest verbatim. Strongest and cheapest case. |
| PR / code review | test suite + typecheck + lint + coverage delta on changed lines | Add a red-team pass; tests only cover the anticipated. |
| Refactor | behaviour-preservation: full suite green + public API diff empty | The API diff is the real oracle; tests alone miss signature drift. |
| Bug fix | a failing reproduction test written **before** the fix | Contract must gate: no fix work until the repro fails for the right reason. |
| Migration | row counts, checksums, dual-read parity against the old path, rollback rehearsal | Parity over spot checks. Writes must be idempotent — upsert by a stable natural key, or check-before-write against the ledger — so a resumed run after a STALL/BUDGET stop cannot double-apply. |
| Test coverage push | coverage delta + mutation score | Coverage alone is gameable; mutation score is not. |
| Dependency upgrade | build + suite + lockfile diff + runtime smoke | |
| Performance work | benchmark harness, committed before any change | Without a committed baseline there is no oracle at all. |
| Doc generation | every claim resolves to a `path:line` that still exists; links resolve | Turns prose into something checkable. |
| Research sweep | every claim carries a retrievable citation; a second pass re-fetches a sample | |
| Security review | known-vuln scanners + written threat model rows, each with a reachability verdict | |
| Data pipeline | schema validation + invariants (nulls, ranges, uniqueness, referential integrity) | |
| Financial / trading logic | replay against historical data with committed pass thresholds | **Never** an LLM judge — the model learns to satisfy the judge, not the market. |

---

## Ranking oracle strength

Eight rungs, strongest first. **Take the highest rung the job admits** — most work that "has no test
suite" is actually eligible for rungs 2–5 and nobody looked.

**1. Native check** — the project's own pass/fail command. `go test ./...`, `cargo test`, `pytest`,
`npm test`, `mvn verify`, `dbt test`, `great_expectations checkpoint run`, a type-checker, a schema
validator, an exit code. Language-irrelevant: the contract names whatever command *this* project uses.

**2. Invariant / reconciliation** — properties the output must satisfy, checkable by a query. Control
totals tie out, debits equal credits, Σ(parts) == total, row counts match, no nulls in keys,
referential integrity holds, timestamps are monotonic, values sit in range. **In finance this is
proof-grade**: a three-way tie-out (ledger ↔ bank ↔ subledger) either reconciles to zero or it does
not. Wherever numbers exist, this rung is available.

**3. Differential (N-version)** — compute the same result a second, independent way and diff.
SQL vs dataframe, vectorised vs loop, new pipeline vs legacy in parallel-run. **Independence must be
engineered or the rung is worthless**: two implementations from the same agent and the same prompt fail
together far more often than chance (Knight & Leveson 1986; replicated 2026 with coding agents — 429
coincident failures where independence predicts 115). Force divergence: different paradigm, different
agent, spec re-derived from the source document.

**4. Metamorphic** — relations between *runs* that hold without any reference answer. Permutation
invariance (row order must not change an aggregate), scaling (double the quantities → revenue doubles,
margin % unchanged), subset additivity (Σ group sums == total), monotonicity (a positive transaction
cannot lower a balance), idempotence (re-running the pipeline yields identical output), round-trip
(parse∘serialise == identity, convert-and-convert-back). This is the workhorse when there is no ground
truth, and it is established in finance — metamorphic relations derived from IRS forms found real
defects in commercial tax software.

**5. Deferred ground truth** — reality supplies the label later: the market outcome, the A/B result, a
walk-forward fold. Strong **only** if the criterion, horizon and decision rule are frozen in an
immutable artifact *before* the outcome window opens, and the number of variants tried is logged
(unlogged trials make any threshold meaningless — see Deflated Sharpe Ratio). No peeking: continuously
re-checking a running experiment drives the false-positive rate from 5% to 25–40%.

**6. LLM-generated criteria, deterministically checked** — the model proposes invariants, metamorphic
relations, or reconciliation identities; *execution* delivers the verdict. See "The LLM builds the
oracle" below. This is where LLM power genuinely belongs.

**7. Panel + atomic criteria** — isolated graders answering **binary** questions they did not author,
each citing evidence. Decomposition into yes/no items measurably beats scalar scoring; a 1–10 "quality
score" is not a rubric. Use a panel of *different* model families, not one model thrice. Require
`pass^k` agreement on high-stakes rows; disagreement means the rubric is underspecified, not that the
agent is unreliable (`references/outer-loops.md`). Last resort for genuinely non-mechanical qualities.

**8. None** — pure taste: prose voice, visual direction, naming aesthetics. Do not write an autonomous
loop; write a checkpointed collaboration.

> **Scalar LLM-as-judge is not on this ladder as a gate.** Asked to rank two answers by *objective
> correctness* rather than human preference, strong judges score near chance (~56%, JudgeBench). High
> agreement figures come from open-ended preference benchmarks and do not transfer to correctness. Use
> a judge as a triage signal to decide what to check — never as the check.

---

## The LLM builds the oracle; it never *is* the oracle

The instinct "there's no test suite, so let the model judge it" is the one to resist — that is the
near-chance path. But the model is genuinely excellent at something adjacent: **knowing what ought to
be true in a domain**. Split the two roles that LLM-as-judge fuses:

| Role | Who does it | Why |
|---|---|---|
| Propose what must hold | the LLM | domain knowledge, breadth, recall of edge cases |
| Decide whether it holds | execution | deterministic, inspectable, re-runnable, ungameable |

The model writes the assertion; the machine returns the verdict. The criterion is then frozen, readable
by you, and re-runnable forever — none of which is true of a judgement.

**Ask for relational oracles, not value oracles.** This distinction decides whether the pattern works:

- ✅ **Relational** — "Σ of the per-region totals must equal the grand total"; "reversing input order
  must not change the mean"; "no output row may reference a customer id absent from the dimension".
  These are checkable *without knowing the right answer*, which is exactly the situation you are in.
- ❌ **Value** — "assert revenue == 4_182_390". The model cannot infer expected values; asked for these
  it produces confident wrong numbers, or worse, reads them off the implementation and asserts what the
  code already does — laundering the bug into the spec.

**Generate from the source, blind to the implementation.** Derive the invariants from the spec, the
regulation, the design doc, the schema — not from the code under test. An oracle written by looking at
the implementation encodes *actual* behaviour, and rubber-stamps whatever is wrong with it.

**Verify the oracles themselves before trusting them.** Generated assertions are frequently wrong
(fewer than half of LLM-written unit tests are fully correct in published measurements). Cheap filter:
each proposed invariant must (a) be expressible as a command, (b) **pass on known-good data**, and
(c) **fail on a deliberately corrupted copy**. An invariant that cannot fail is not a check — that
positive/negative control pair costs seconds and removes most of the risk.

## Building an oracle when none exists

In order of preference:

1. **Harvest.** Search the repo and docs for criteria already written: `Gate:`, `AC:`, `MUST`, `SHALL`,
   definition-of-done, acceptance checkboxes, existing test names, CI gate configs. Most teams have
   these and have forgotten.
2. **Make the first phase build it.** P1 writes the failing test, the benchmark harness, or the
   invariant checker; later phases must make it pass. Slower, and it converts an unverifiable job
   into a verifiable one — usually worth it.
3. **Invert.** If success is hard to define, define failure precisely and check for its absence:
   no unhandled path, no unmigrated row, no uncovered branch, no constant defined but unenforced.
4. **Narrow.** Split off the verifiable part, contract that, and hand the rest back to the user as
   a checkpointed collaboration. Say explicitly which part you split off and why.
5. **Ratify.** When success is real but not machine-checkable (a plan, a design, a curriculum, prose
   with requirements), decompose the deliverable into required components, write one **concrete,
   checkable** acceptance criterion per component — "every KPI has a baseline, a numeric target and a
   measurement method"; "the budget sums to the stated cap and every channel carries a one-line
   rationale" — and have the user ratify the list *before* drafting. Then draft against it and check
   each. Weaker than a test, far stronger than taste, and it still fails loudly on a missing component.

---

## When the job isn't a test suite

**Any language.** The harness plumbing (`fold_ledger.py` and friends) is stdlib-only and operates on
JSONL — it never touches your project's language, and Python is incidental to it. The *oracle* is
always the project's own command: `go test ./...`, `cargo test`, `bundle exec rspec`, `dotnet test`,
`dbt test`. If `python3` is not available at all, the completion gate degrades to a shell one-liner
(`jq -e 'select(.verdict==null or .verdict=="FAIL")' ledger.jsonl && exit 1`) — the gate is a
non-zero exit, not a specific script.

**Data / analytics work.** This is oracle-*rich*, not oracle-poor. In rough order of cost:
1. schema, volume, freshness, uniqueness, referential integrity — a declarative data-quality gate
   (dbt tests, Great Expectations, Soda, Pandera, Deequ) that exits non-zero. Cheap; make it mandatory.
2. reconciliation to an independent source, and control totals that must tie out.
3. metamorphic relations (rung 4) — the workhorse, since analytics rarely has a reference answer.
4. differential recomputation (rung 3) with *forced* implementation diversity.

Note the limit practitioners agree on: data-quality frameworks check **the data, not the logic**. A
pipeline can be arithmetically wrong and pass every expectation. Necessary floor, not sufficient.

**Financial data.** Reconciliation is the native oracle and it is proof-grade — use it before anything
else. Cross-foot, tie out three ways, require Δ == 0 or an explained variance. Recompute every figure
independently. For anything predictive, the oracle is **executable and numeric, never a model's
opinion** — an LLM verifier here learns to satisfy the verifier rather than the market. Lock the
threshold, the horizon and the decision rule before the outcome window opens, and log how many
variants you tried.

**Non-code deliverables** (a plan, a strategy, an analysis, a report). Make it structurally checkable,
then check structure deterministically and content atomically:
1. **Required components, pre-declared.** Decide the sections and what each must contain *before*
   drafting. Presence then becomes a parse, not a judgement.
2. **Atomic binary criteria**, not a quality score — "every workstream names an owner", "every
   milestone carries a date", "the downside case is quantified", "the budget sums to the stated cap".
   Falsifiable by a specific reader. Decomposed yes/no items measurably beat Likert scoring.
3. **Citation resolution — deterministic and high-value.** Every claim traces to a source; every URL
   resolves; every quoted string actually appears at the cited location. This is a script, and it
   catches most fabrication for near-zero cost.
4. **Recompute every number** from its stated source. This converts most of an "analysis" back into
   invariant/reconciliation territory above.
5. Reserve human checkpoints for the genuinely unfalsifiable — strategy choice, risk appetite — not
   for anything mechanically checkable.

## Anti-oracles

These read as verification and provide none. Name them in the contract as forbidden:

- **Self-assessment.** "Review your work and confirm it is correct." The producer grading itself.
- **A test that asserts the mock.** Exercises the double, not the behaviour.
- **Existence checks.** Code that exists but is never called. Always check call sites — the contract
  should classify uncalled code as PARTIAL, never PASS.
- **A constant defined but not enforced.** Present in a config, never read at the boundary. FAIL.
- **Green suite that never ran.** Require the command and its observed exit status, not a claim.
- **Coverage without assertions.** Lines executed, nothing asserted.
- **A loop holding the lethal trifecta.** Three capabilities that are each fine alone and catastrophic
  together: access to **private data**, exposure to **untrusted content**, and a means of **external
  communication**. Any agent with all three can be talked by the untrusted content into exfiltrating the
  private data, and no prompt-level instruction reliably prevents it. Audit each *execution path*, not
  the agent as a whole — a research sweep that reads scraped pages (untrusted), has repo access
  (private), and can open a PR or call a webhook (egress) holds all three. Break one circle: drop the
  egress, sandbox the data, or gate the send behind APPROVAL. This is a design-time check, not a
  runtime one; state which circle you broke in the contract.
- **An unproven absence.** "I searched and found nothing" is a *claim*, not a fact — the command may
  have died, been mis-globbed by the shell, or searched the wrong tree, and `|| echo "confirmed: none"`
  will happily print a confirmation of a command that never ran. Before recording an absence: confirm
  exit 0 **and** run a positive control that you know should match. FAIL and PARTIAL need a `proof_cmd`
  exactly like PASS does.
- **A value oracle the model invented.** `assert total == 4_182_390` where the number came from the
  model's head, or worse from the implementation. Prefer relations that hold without knowing the answer.
- **An invariant that cannot fail.** If it passes on deliberately corrupted data, it checks nothing.
- **Differential testing without engineered independence.** Two implementations from the same agent and
  prompt share the same misreading and fail together.
- **A scalar LLM quality score used as a gate.** Near chance on correctness; triage signal only.
- **Peeking at a running experiment**, or picking the threshold after the outcome. Both manufacture
  significance. Freeze the rule first; log how many variants were tried.
- **A threshold set after seeing the result.** Retrofitted to whatever happened.
- **"The code already does X, so X must be intended."** Laundering a bug into the spec.

---

## Jobs that should not be loops

Distinguish **weak-oracle-but-decomposable** (marketing plan, curriculum, proposal, ADR — these *can*
be checkpointed loops via **Ratify**, and their deliverable is the artifact itself) from **pure taste
with no articulable criterion** (visual direction, prose voice, naming aesthetics). Only the latter gets
no loop. Saying "this needs a human" about a decomposable artifact is how a DONE job quietly becomes a
document nobody asked for.

If the answer to "how does it prove success" is genuinely "a human looks at it", say so and write a
**checkpointed collaboration** instead: small units, explicit stop-and-show after each, no autonomous
continuation. Naming this honestly is more useful than dressing an unverifiable job in loop machinery —
that only produces confident nonsense faster.

Typical members: naming and API aesthetics, product strategy, prose voice, visual design direction,
anything whose success criterion is "the user likes it".
