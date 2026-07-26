# loop-contract

A [Claude Code](https://docs.claude.com/en/docs/claude-code) skill for turning a rough, long-running
agentic task into something an agent can actually finish — and stop at the right moment.

Given a rough need in any domain, it first **triages**: it routes to the best existing
skill/plugin/agent when one fits, and only **designs** a solution when none does. For a long autonomous
job the design is a copy-paste-ready, *loop-engineered* **contract**:

- an immutable, falsifiable **mission** re-read every phase;
- **three-kind termination** (success / budget / stall) plus an approval gate for irreversible writes;
- an append-only **ledger spine** on disk that survives compaction and `/clear`;
- a **deterministic-before-expensive** verification cascade;
- bounded **sub-agent contracts** (context isolation, not parallelism);
- a hard **token policy** built on the O(n²) cost of re-billed context;
- and an outer layer — trajectory metrics, `pass^k` repeatability, and a cross-run retro (Loop 4).

The completion gate is real code, not a promise: `fold_ledger.py` exits non-zero on any missing,
duplicate, unproven, or non-terminal row — so "done" is a fact, not a claim.

## Scripts enumerate and verify; the model interprets

Deciding what counts as a requirement is judgement, and pattern-matching for `Gate:` and `MUST` finds
only the labelled minority — silently, so the count it prints reads as coverage. Deciding what text
exists, and proving a harvested claim is really in it, are mechanical.

So the boundary sits between them. `index_corpus.py` shards every readable line of the corpus and
prints what it could not read; it filters nothing, so it cannot drop a source. Sub-agents read the
shards and harvest requirements from prose, tables, tests, comments, and CI configs. Then
`verify_harvest.py` proves every claim appears **verbatim at its cited `path:line`** and that **every
shard was accounted for** — a paraphrase, an invention, or an unread file is a non-zero exit. A bounded
adversarial sweep measures what the harvest still missed, and that find-rate is reported as the recall
estimate rather than rounded up to "complete".

## Install

```bash
git clone git@github.com:hdkhosravian/loop-contract-skill.git ~/.claude/skills/loop-contract
```

Then, in Claude Code, invoke `/loop-contract` or just describe a multi-step job (audit, migration,
PR review, backfill, research sweep, …).

## Layout

| Path | What |
|---|---|
| `SKILL.md` | Entry point — the triage front-door and the contract workflow. |
| `references/contract-template.md` | The fill-in contract skeleton. |
| `references/harvest-protocol.md` | Index → sharded harvest → grounding gate → recall sweep. |
| `references/oracle-catalog.md` | Oracles by job type; what to do when there is none. |
| `references/subagent-contracts.md` | Sub-agent role design, spawn contract, output schema. |
| `references/token-policy.md` | The token arithmetic and the binding rules. |
| `references/execution-protocol.md` | How a fresh session should *run* a contract. |
| `references/outer-loops.md` | Trajectory metrics, `pass^k`, Loop 4 hill-climbing. |
| `references/triage-routing.md` | The route-else-design front-door rubric. |
| `references/worked-example.md` | An annotated spec-conformance audit contract. |
| `scripts/index_corpus.py` | Enumerate every readable line into a shard manifest — the coverage contract. |
| `scripts/verify_harvest.py` | The grounding + coverage gate: verbatim claims, no unread shards. |
| `scripts/fold_ledger.py` | The deterministic fold + completion gate. |
