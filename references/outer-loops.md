# Beyond the Single Run — Loop 4, Repeatability, Trajectory

The rest of this skill designs one run of one job (the doc's Loop 1–2). This file covers what wraps
*around* runs: how a contract is measured, repeated, and improved. It is loop engineering's outermost
loop — the compounding edge most harnesses never build.

## Trajectory observability — measure the run, not just its verdict

A verdict says *what*; the trajectory says *how it got there*, which is the only thing you can improve.

- Spine file `metrics.jsonl`: append one line per phase boundary —
  `{"phase":"P2","tool_calls":n,"spawns":n,"context_pct":n,"elapsed_s":n}`.
- The report ends with a **Process summary** folded from it: phases run, spawns used/ceiling,
  deterministic-vs-escalated split, context% at each gate, where it stalled.
- The metrics that actually matter (doc §6.6): steps-to-completion, **context-% at failure** (a run that
  always dies near 80% has a context problem, not a model problem), tool-error-rate, stall-rate, and
  **cost per *successful* task** — never cost-per-run, which flatters failures.

Per-iteration logging is the executing runtime's job; **per-phase is the contract's grain**. Write at the
phase boundary only — continuous metric-writing is itself noise (`token-policy.md` phase-boundary check).

## Repeatability — pass^k, not pass@1

Agents are non-deterministic, so a single green run proves little (doc §6.7). A deterministic-oracle row
is already reproducible — verify it once. Everything softer needs agreement across independent runs:

- **Row level.** Capital-safety and judgement rows PASS only when **k independent verifications agree**
  (default k=3, distinct lenses per `subagent-contracts.md`). Store the agreement count. Disagreement
  means the *rubric* is underspecified — tighten it and re-run; never average two verdicts into one.
- **Whole-job rehearsal.** Before trusting a weak-oracle contract on a high-stakes job, run P1–P3 on a
  small sample in **two fresh sessions** and diff `verdicts.jsonl`. Divergence is a design bug in the
  contract, caught cheaply before the full run.
- The target is `pass^k` (all k agree), not `pass@k` (at least one). 4-of-5 is a 20% failure rate —
  unacceptable on anything irreversible.

## Loop 4 — the contract hill-climbs across runs

One contract runs one job; contracts of a *kind* run forever. Each run must make the next better.

- **Ratified decisions are priors.** Every ambiguity resolved is in `decisions.jsonl` and surfaces in the
  report for the user to ratify or overturn. Overturned ones are corrections to fold into the next
  contract's §5 and ledger — decided once, not re-litigated.
- **The retro closes the loop.** The run's last act writes `retro.md` (template §8): which gate was noise,
  which oracle was weak, which placeholder was guessed, which decisions were overturned. The next
  `<job-type>` contract starts from that, not from zero.
- This is hill-climbing at the *contract-design* grain: the harness (the contract) improves against
  observed outcomes, run over run. The doc calls Loop 4 the competitive advantage; this is where a
  contract-generator earns it.

## What stays out of scope (state it, don't pretend)

A contract-generator does not run the live agent, so it does not own inference-time KV-cache measurement,
per-token tracing, or an automated multi-run eval harness. It *instructs* the executor on the first
(`token-policy.md` prefix rules) and *designs for* the others (`metrics.jsonl`, k-fold agreement, retro).
Building the automated eval harness itself is a separate job — a good candidate to route or contract on
its own (triage it).
