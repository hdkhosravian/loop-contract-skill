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

**Deterministic** — exit code, diff, assertion, checksum, type error. Cannot be talked into passing.
Grant the most autonomy here.

**Executable** — a run that produces a number compared to a committed threshold: benchmark, backtest,
replay, coverage. Strong, but only if the threshold is fixed *before* the run. A threshold chosen
afterwards is not an oracle.

**Panel + rubric** — an isolated sub-agent scoring against written criteria it did not author.
Useful for judgement-heavy work; must be isolated (a producer cannot grade itself) and rubric-bound
(free-form "is this good?" is not a rubric). A lone panel verdict is `pass@1`; for capital-safety or
high-stakes rows require **k independent verifications in agreement** (`pass^k`) — disagreement means
the rubric is underspecified, not that the agent is unreliable. See `references/outer-loops.md`.

**None** — taste, strategy, prose quality, design direction. Do not write an autonomous loop.

---

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

---

## Anti-oracles

These read as verification and provide none. Name them in the contract as forbidden:

- **Self-assessment.** "Review your work and confirm it is correct." The producer grading itself.
- **A test that asserts the mock.** Exercises the double, not the behaviour.
- **Existence checks.** Code that exists but is never called. Always check call sites — the contract
  should classify uncalled code as PARTIAL, never PASS.
- **A constant defined but not enforced.** Present in a config, never read at the boundary. FAIL.
- **Green suite that never ran.** Require the command and its observed exit status, not a claim.
- **Coverage without assertions.** Lines executed, nothing asserted.
- **A threshold set after seeing the result.** Retrofitted to whatever happened.
- **"The code already does X, so X must be intended."** Laundering a bug into the spec.

---

## Jobs that should not be loops

If the answer to "how does it prove success" is genuinely "a human looks at it", say so and write a
**checkpointed collaboration** instead: small units, explicit stop-and-show after each, no autonomous
continuation. Naming this honestly is more useful than dressing an unverifiable job in loop machinery —
that only produces confident nonsense faster.

Typical members: naming and API aesthetics, product strategy, prose voice, visual design direction,
anything whose success criterion is "the user likes it".
