# Loop-engineering requirements — and where this skill implements each

A conformance matrix. The canon is synthesised from the primary sources in `SOURCES.md`; the right-hand
column is where the requirement actually lives here, so the claim is checkable rather than asserted.

Re-run this audit whenever the canon moves. A requirement with no implementation column is a gap, and
gaps belong in `scope.jsonl`, not in a footnote.

## Loop primitives

| # | Requirement | Why it exists | Implemented in |
|---|---|---|---|
| 1 | State lives outside the transcript | compaction or a crash otherwise destroys it | `contract-template.md` §2 spine — `scope/ledger/verdicts/decisions/metrics.jsonl` |
| 2 | Action space declared and stable; mask rather than remove | removal rewrites the prefix and voids the cache | `token-policy.md` — progressive disclosure |
| 3 | Every action returns a real observation, never self-report | otherwise the loop grades its own homework | `fold_ledger.py` — `proof_cmd` required; `--oracle-cmd` executed |
| 4 | Termination in **all** kinds: oracle · step · token/cost · wall-clock · no-progress · approval | most loops ship a step cap alone and burn budget in circles | §1 TERMINATION — SUCCESS / BUDGET (spawns · calls · context% · tokens/cost · wall-clock) / STALL / APPROVAL |

## Verification

| # | Requirement | Why | Implemented in |
|---|---|---|---|
| 5 | A machine-readable pass/fail the agent runs itself | without it "looks done" is the only stop signal | `fold_ledger.py` exit code; achievement oracle observed **red first** |
| 6 | The grader is not the actor | a producer re-derives its own reasoning and passes itself | `subagent-contracts.md` maker/checker — checker never sees producer reasoning |
| 7 | Reflection needs an external signal | self-critique without an oracle is decorative | oracle-first ordering in `SKILL.md` §0/§1 |
| 8 | Oracles exist beyond test suites | data/finance/non-code work is oracle-*rich*, not oracle-poor | `oracle-catalog.md` — eight-rung ladder |
| 9 | The model **builds** the oracle; it never **is** the oracle | judges score near chance on objective correctness | `oracle-catalog.md` — relational-not-value oracles |

## Context

| # | Requirement | Why | Implemented in |
|---|---|---|---|
| 10 | Compaction with a stated preservation contract | otherwise file lists and test commands vanish mid-task | `token-policy.md` rule 6 |
| 11 | Externalise to disk; cite paths, carry pointers | keeps the window small and restorable | rules 2–3, 8; `findings/` |
| 12 | Recitation of the goal at the tail | counters drift and multi-turn degradation | `PROGRESS.md` re-read first each phase |
| 13 | Prefix stability, append-only, deterministic serialisation | the dominant cost lever | `token-policy.md` — prefix stability |
| 14 | Progressive disclosure of tools/skills | a flat schema dump is billed every turn | `token-policy.md` — progressive disclosure |
| 15 | Keep the error **signal**; drop the error **payload** | scrubbed failures get repeated; raw payloads are bulky | `token-policy.md` — keep the error signal |

## Sub-agents

| # | Requirement | Why | Implemented in |
|---|---|---|---|
| 16 | Sub-agents for context isolation, not parallelism | the value is the small returned verdict | `subagent-contracts.md` |
| 17 | Writes single-threaded; read-only/advisory parallel | parallel writers carry conflicting implicit decisions | same — "the multi-agent argument as it settled" |
| 18 | Share context for decisions; isolate for judgment | an unprimed reviewer finds more real defects | same |
| 19 | No recursive spawning; hard spawn ceiling | otherwise the flat budget is meaningless | spawn contract `NO-SPAWN`; §1 BUDGET |

## Evaluation

| # | Requirement | Why | Implemented in |
|---|---|---|---|
| 20 | `pass^k`, not `pass@k` | a single green run proves little | `--require-agreement`; `outer-loops.md` |
| 21 | Distinguish coverage panel (conjunction) from repeatability (agreement) | conflating them tells you to erase real findings | `subagent-contracts.md` — two mechanisms |
| 22 | End-state eval plus trajectory diagnostics | counters say *that* it broke, not *where* | `metrics.jsonl`; report §10 |
| 23 | LLM-judge is a triage signal, never a gate | near chance on objective correctness | `oracle-catalog.md` rung note |

## Safety and durability

| # | Requirement | Why | Implemented in |
|---|---|---|---|
| 24 | Approval gate before irreversible actions, surviving restart | routine is exactly when nobody looks | §1 APPROVAL; persisted in the spine |
| 25 | Break the lethal trifecta per execution path | private data + untrusted content + egress = exfiltration | `oracle-catalog.md` anti-oracles |
| 26 | All tool output treated as untrusted input | injection arrives through tool returns, not the prompt | `token-policy.md` rule 9; spawn `DATA` clause |
| 27 | Checkpoint each step; idempotent mutating actions | a resumed run must not double-apply | §1 idempotent writes; per-item record-before-next |
| 28 | Trace the shape of every step, not its contents | you cannot improve what you cannot see | `metrics.jsonl` field spec |

## Outer loops

| # | Requirement | Why | Implemented in |
|---|---|---|---|
| 29 | Application loop — human sets goal, evidence returns, human redirects | keeps the human in the right place | delivery + APPROVAL + the report |
| 30 | Hill-climbing — transcripts → failure taxonomy → harness edit → re-eval | the actual development method | `outer-loops.md` — retro + ratified priors |
| 31 | Promote repeated lessons into **executable** procedures | prose lessons get re-derived every run | `outer-loops.md` — skill library |
| 32 | Recurrence reports the **delta**, not the same findings forever | the failure mode is alert fatigue | `recurring-jobs.md` |

## Deliberately out of scope

| Concern | Why not here |
|---|---|
| Rainbow/gradual deploys of a running agent fleet | deployment infrastructure, not loop design |
| OTel wire format / span semantics | the skill specifies *what* to record; the host owns transport |
| Sandboxing and credential scoping | enforced by the runtime — the contract says so explicitly rather than pretending prose can |
| Automated multi-run eval harness | a separate build; the skill designs one run and says so |

## Known open items

- **The gate is opt-in.** Every check `fold_ledger.py` performs happens only if the agent runs it. The
  skill makes "a done claim without an exit line is void" as sharp as prose can, but that is compliance,
  not enforcement. A host-level stop-hook that blocks turn-end until the gate passes would close it.
- **No end-to-end trial on a long multi-session job.** The gate is verified against fixtures; the
  behavioural half is not yet proven over a 40-item run that exceeds one context window.
