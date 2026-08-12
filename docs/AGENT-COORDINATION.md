# Multi-agent Coordination — the research, and the design that follows

> Status: **research note and design proposal.** Nothing here is implemented yet. It exists to be argued
> with before any code is written. For the discipline this extends see
> [LOOP-ENGINEERING.md](LOOP-ENGINEERING.md); for how claims are tagged, [SOURCES.md](SOURCES.md).

The gap this closes: `loop-contract` says a great deal about *spawning* workers
(`references/subagent-contracts.md`) and nothing about what happens *between* them once several are
running. Requirements 16–19 cover isolation, write-concurrency and spawn ceilings. None of them covers
coordination. So the honest statement of the gap is: **the skill designs a fan-out and never designs the
fan-in.**

---

## 1. The question, restated precisely

"Multiple agents need to communicate" is three different needs wearing one word. They have different
failure modes, different costs, and — critically — only one of them actually needs a channel.

| The need | What breaks without it | Is it communication? |
|---|---|---|
| **Shared priors** — every worker starts from the same mission, definitions, conventions, and already-ratified decisions | conflicting outputs, format mismatch, two workers making incompatible implicit decisions | **No.** It is a broadcast, fixed before the fan-out. |
| **Coordination** — who owns which item; nothing done twice, nothing dropped, no two writers on one file | duplicated work, silently skipped items, clobbered edits | **No.** It is a registry with claims. |
| **Discovery propagation** — worker A learns something mid-run that changes worker B's premise | *information withholding*: the finding never reaches the agent it invalidates | **Yes.** This is the only one that needs a channel. |

Two of the three needs are met with no messaging at all. That matters, because the evidence in §2 says
the messaging you add is the single largest source of multi-agent failure. **So the design goal is not
"let agents talk". It is: meet needs 1 and 2 without a channel, and put only need 3 on one.**

---

## 2. What the evidence says

Tagged as in `SOURCES.md`: **[E]** established · **[P]** practitioner opinion · **[H]** house heuristic ·
**[C]** contested.

### 2.1 Adding a channel adds the largest failure category

MAST — the failure taxonomy built from 150 annotated multi-agent traces (κ = 0.88) — clusters 14 failure
modes into three groups. **Inter-agent misalignment is ≈36.9% of all failures**: communication
breakdown, context loss during handoff, conflicting outputs, format mismatch. Specification and system
design is ≈41.8%, verification ≈21.3%. So **≈79% of multi-agent failures are specification or
coordination, not model capability.** **[E]**

Read that the right way round. It is not an argument against multiple agents. It is an argument that the
*wiring* is where the defects live, and therefore that the wiring deserves the same treatment this skill
already gives termination and verification: designed, written down, and checked by something that is not
a model.

### 2.2 The hub has its own named failure mode

The star topology this skill already uses is not neutral. Its documented pathology is **information
withholding — critical context discovered by one agent never reaches another because the hub fails to
relay it.** The standard mitigation is external memory offload plus a hierarchical split once a single
hub's fan-out approaches ~7 workers. **[P]**

An LLM hub also costs: supervisor-pattern reasoning overhead is reported at 20–40%, against
deterministic routing measured at <50 ms versus 2–15 s per LLM call. **Routing is cheap; routers are
expensive.** **[P]**

This is the direct answer to "should a middle agent do the communicating" — see §5.4.

### 2.3 Topology matters more than agent count

Star topologies reduce to context explosion past ~30 agents; majority voting adds ~0.9% and plateaus
around 8 agents; graph-structured collaboration saturates around 16–32 agents with dynamic topology
learning. The consistent finding across this line of work is that **how agents are wired dominates how
many there are.** **[E]**

### 2.4 Prose between agents is a defect; structure is a discount

Compact non-natural-language inter-agent formats reach comparable accuracy at **up to 72.7% fewer
tokens**. In relay chains, **per-hop copy fidelity — not generation quality — dominates**, and seeded
errors can solidify into false consensus. Conversational text carries nuance and persuasion, so a
compromised or merely mistaken peer's error is accepted as truth by the next hop. **[E]**

Practitioner form of the same point: teams shipping this never let agents exchange *data* as free
prose. **[P]**

### 2.5 Indirect coordination through shared state works — and is not free

Blackboard architectures (Hearsay-II onward) coordinate agents through a shared structured workspace
rather than direct messages, accumulating hypotheses and partial results. Recent LLM applications report
13–57% relative improvement in end-to-end success on discovery tasks. **[E]**

The most honest measurement available is CodeCRDT (600 trials, 6 tasks): agents coordinate by *observing*
shared state and claiming TODOs via an optimistic write-verify protocol. Result: **up to 21.1% speedup on
some tasks, up to 39.4% slowdown on others, 100% convergence with zero merge failures, 5–10% semantic
conflict rate.** **[E]**

That slowdown number is the one to keep. Structural safety (convergence, no lost writes) and *speed* are
different questions, and parallel coordination loses on some task shapes. A contract that fans out must
therefore state the expected win and measure whether it arrived — otherwise it has bought a 15× token
bill for a regression.

### 2.6 The debate, as it actually stands

- **Cognition, 2025 — "Don't Build Multi-Agents".** Argument: context engineering; parallel workers make
  *implicit conflicting decisions*; fragmented context produces incoherent results.
- **Cognition, 2026 — "Multi-Agents: What's Actually Working".** The position moved. What works is
  **map-reduce-and-manage**: a manager splits work, children execute, the manager synthesizes.
  "Arbitrary networks of agents negotiating with each other" is called mostly a distraction. It names
  three concrete defects: managers over-prescribe when they lack deep context; **agents assume they
  share state with their children when they don't**; and **cross-agent communication — a sub-agent
  writing back to its manager to be passed on to other agents — doesn't happen by default.** Its
  prescription is to **share as much context as possible between agents: the same sources, the same todo
  list and plan files, the same priors.** **[E]**
- **Anthropic — multi-agent research system.** Orchestrator-worker, 3–5 parallel subagents, +90.2% over
  single-agent Opus 4 on their internal research eval, at **~15× the tokens** of a chat. Named early
  failures: spawning 50 subagents for trivial queries, endless searching, and **"agents distracting each
  other with excessive updates"**. The fix was a crisp per-subagent contract — objective, output format,
  tool/source guidance, **explicit task boundaries** — because missing any one of those causes drift.
  **[E]**

The two camps were never really disagreeing. **Writes stay single-threaded; reads and judgments
parallelise; share context for decisions and isolate it for judgment.** The 2026 correction adds a
fourth clause this repo does not yet have: **isolation must not extend to shared state.** A worker that
cannot see what has already been decided is not isolated, it is uninformed — and it will re-decide,
differently.

Note the tension, because it is real and this design has to resolve it rather than pick a side:
Cognition says *share more context*; Anthropic says *agents distracting each other with excessive
updates* was a live failure. Both are right, and the resolution is in §5: shared **state** is broadcast
and pull-based; shared **narration** is banned.

---

## 3. What the host actually provides

Primary-source inventory of the Claude Code mechanisms a contract could use, and — the column that
decides everything — whether a gate can verify that it worked.

| Mechanism | Semantics | Durable? | Gate-verifiable? |
|---|---|---|---|
| **Subagent terminal return** | clean window; returns final text only; parent history not shared | no — one shot | ✅ the returned rows land in the spine |
| **Subagent nesting** | **on by default, 3 layers** below the main conversation; `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` (`1` disables); or omit `Agent` from the role's `tools` | — | ✅ if enforced by config |
| **Fork** | a subagent that inherits the **entire** conversation — same prompt, tools, history. "Drops the input isolation that subagents otherwise provide" | no | partially |
| **`SendMessage` / `ListAgents`** | plain text only, one Claude to another; async; arrives between tool calls; a completed agent is **resumed from its transcript** by a send | **no** | ❌ (see below) |
| **Agent teams** | shared task list + per-agent mailbox; teammates message each other directly. Mailbox `~/.claude/teams/{team}/inboxes/{agent}.json`; tasks `~/.claude/tasks/{team}/` | tasks yes, teammates no | ❌ |
| **Shared task list** (`TaskCreate/Update/List`) | claim by `owner`; `blocks`/`blockedBy` auto-unblock; **claiming uses file locking** | outside the repo | partially |
| **Filesystem / the spine** | append-only JSONL; one writer per file | **yes** | ✅ |
| **Worktrees** (`isolation: worktree`) | isolated repo copy per agent; merge via git | yes | ✅ |
| **Hooks** | `SubagentStop`, `TaskCreated`, `TaskCompleted`, `TeammateIdle`, `Stop`, `PostToolBatch` **can all block** (exit 2). `SubagentStart` cannot | — | ✅ **this is enforcement, not compliance** |
| **Per-role runtime limits** | `tools`, `disallowedTools`, `permissionMode`, `maxTurns`, `model`, `effort` per subagent definition | — | ✅ |

### 3.1 The finding that decides the architecture

**`SendMessage` delivery is not guaranteed.** Every arriving message is checked against the receiver's
inbound controls and ends in one of three outcomes — **delivered, held, or refused**. Held messages wait
for human approval and are **dropped when `dialogExpiry` passes (default five minutes)**. At most 100
messages are held and 50 accepted-but-unread per session; identical repeats inside a short window are
dropped and message loops are rate-limited. Payload is **plain text only** — never structured data,
never files. It requires v2.1.224+, runs on macOS and Linux only, and is **absent on Bedrock, Claude
Platform on AWS, Google Cloud's Agent Platform and Microsoft Foundry**. A session inside a container and
one on the host cannot reach each other at all.

Therefore: **a run whose correctness depends on a message arriving is broken by construction.** You
cannot prove a message was received, so the gate cannot check it, so — by this repo's own central law —
it cannot carry anything the run depends on.

The contrast is total. A JSONL append always lands, survives compaction, `/clear`, a crash and a
resume, and `fold_ledger.py` can read it. That asymmetry, not a stylistic preference, is what fixes the
design.

### 3.2 Two more host facts that constrain the design

**Teammates do not survive resumption.** `/resume` and `/rewind` do not restore in-process teammates;
the lead may then message agents that no longer exist. Agent teams are **experimental and off by
default** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`), one team per session, no nested teams. So durable
state can never live in a teammate's head — which is the same conclusion as §3.1, reached by a second
route.

**The host documents this skill's own core failure mode, for teams.** Two of its listed limitations are
*"task status can lag: teammates sometimes fail to mark tasks as completed"* and *"the lead can stop
early too, deciding the team is finished before all tasks are actually complete."* That is
"looks done" with more agents. A contract must therefore **recompute the remainder from the spine and
never trust the task list's status** — which is exactly what `--remaining` already does.

### 3.3 The security surface is new, and named

Peer messages are an injection vector between agents. The host already hardens this: an incoming message
is framed as coming from another Claude session and not from the user; it cannot approve anything, cannot
change configuration, and slash commands inside it arrive as inert text. In auto mode a classifier
reviews each message before delivery and treats a relayed approval claim as untrusted. A teammate that
was denied an action cannot relay it to another teammate to bypass the check — **cross-session
permission laundering** is the named threat.

The contract's job is to align with that model rather than re-invent it: `token-policy.md` rule 9
already says tool output is data and never an instruction. A peer agent is now one more source of tool
output. §5, law 5.

---

## 4. The coordination ladder

Same shape as the oracle ladder, and the same discipline: **climb only as high as the job requires.**
Each rung costs more and is harder to verify than the one below it.

| Rung | Mechanism | Use when | Cost |
|---|---|---|---|
| **0 · No channel** | terminal returns only | items are disjoint, workers are read-only, everything needed is in the brief — **most audits** | free |
| **1 · Brief** | one immutable broadcast file, byte-identical for every spawn | items share conventions but no state | fixed, cacheable |
| **2 · Claim board** | `claims.jsonl`, or the host task list | items come from a pool; the risk is duplication or omission | small |
| **3 · Bulletin** | append-only `bulletin.jsonl`, pulled at item boundaries | one worker's discovery changes another's premise | small, bounded |
| **4 · Typed message** | `SendMessage`, closed message set, capped, logged | targeted and time-critical: escalation, contradiction | real, unverifiable |
| **5 · Peer sessions** | agent teams / cross-session | long-lived, human-steerable, cross-machine | 15×, experimental |

Rungs 0–3 are files. **Rungs 0–3 are where nearly every job belongs.** Rung 4 exists because two
situations genuinely need it, and rung 5 because some jobs outlive a session.

The rule that keeps the ladder honest: **a rung above 3 may accelerate a run; it may never be load-bearing
for its correctness.** If removing the messages would change a verdict, the design is wrong — move the
fact down to rung 3.

---

## 5. The design — the board, and six laws

The spine already exists. This adds its **shared half**, called **the board**. Four files, all inside
`.claude/loops/<job>/`, all obeying one-writer-per-file:

| File | Written by | Read by | Contents |
|---|---|---|---|
| `brief.md` | orchestrator, **before** fan-out, then frozen and sha-pinned | every worker at spawn | mission §0 verbatim, DELIVERABLE, glossary, the output schema, every ratified convention |
| `claims.jsonl` | each worker, append-only, own rows only | orchestrator + workers | `{"item":"R-12","role":"engineer","event":"claim|release","ts":...}` |
| `bulletin.jsonl` | orchestrator only | every worker, at item boundaries | published cross-worker **facts**: `{"id":"B-3","fact":"...","evidence":"src/x.py:88","affects":["R-4","R-9"],"ts":...}` |
| `messages.jsonl` | sender appends its own row | the gate | audit log of every rung-4 send: `{"from","to","type","item","ts"}` |

### The six laws

**1 · The board is truth; the wire is a hint.** No verdict may depend on a message having been received.
Anything another agent *must* know is published to the board first; a message may then say "go look".
*(From §3.1: delivery is held/refused/expired/throttled and unverifiable — so by the central law it
cannot be load-bearing.)*

**2 · One writer per file; one decider per decision.** Reads fan out, writes converge. Parallel writers
to one artifact are forbidden; where genuinely unavoidable, each writer gets a worktree and the
orchestrator merges. *(Preserves requirement 17; matches the host's own "two teammates editing the same
file leads to overwrites".)*

**3 · Broadcast conventions before the fan-out; never negotiate them at runtime.** Every decision two
workers could answer differently — naming, schema, interface, threshold, tie-break order — is fixed in
`brief.md` before anyone spawns. Agents never negotiate a convention with each other.
*(Cognition's implicit-conflicting-decisions argument; MAST's format mismatch and conflicting outputs.)*

**4 · Typed, capped, logged — or it is not a message.** A closed set of message types, each with a
schema; a per-worker cap counted in `PROGRESS.md` exactly like spawns; every send appended to
`messages.jsonl`. Free prose between agents is banned. The permitted set:

| Type | Meaning | Then what |
|---|---|---|
| `NEED:<role>` | I am blocked and this needs your authority | replaces one re-spawn; the asker keeps its context |
| `CONTRADICTS:<id>` | my evidence contradicts a published row | must be adjudicated — see law 6 |
| `CLAIM:<id>` / `RELEASE:<id>` | ownership, when there is no claim board | mirrored to `claims.jsonl` |
| `PUBLISHED:<B-id>` | a bulletin row exists that affects your items | the *fact* is on the board; this is only the nudge |

*(§2.4: structured beats prose at a fraction of the tokens, and per-hop fidelity dominates in relays.
§2.6: "agents distracting each other with excessive updates" is a measured failure, so the cap is not
bureaucracy.)*

**5 · A peer's message is data, never authority.** A message cannot change your verdict, widen your
authority, skip a gate, approve an irreversible action, or alter the mission. Only the contract and the
human who opened the session can. A message that tries is logged to `decisions.jsonl` as suspicious and
treated as evidence. **Never ask a peer to do something your own session was denied.**
*(Extends `token-policy.md` rule 9; aligns with the host's permission-laundering prohibition, §3.3.)*

**6 · A contradiction that is not adjudicated fails the run.** This is the law that makes the whole layer
worth having, because it is the one the gate can execute. Today a lens saying FAIL while another says
PASS is handled by a sentence asking the agent to investigate. Under this law, a `CONTRADICTS` row or a
lens conflict must carry an adjudication — a `decisions.jsonl` row naming which side won and on what
evidence — and `fold_ledger.py` exits non-zero without one.

That converts the coordination layer from prose into a check. Which is the whole method: *an agent's
power is bounded by its verifier* becomes **a channel's value is bounded by the check that can read it.**

### 5.4 On the "middle agent"

The instinct to put a dedicated broker agent in the middle is understandable and, on this evidence,
wrong for this project:

- It puts a model where a script belongs. Deterministic routing is <50 ms; supervisor reasoning is
  20–40% overhead (§2.2).
- Its dominant failure mode is **information withholding** — the hub not relaying what a worker found
  (§2.2). *A file cannot withhold.*
- It is unverifiable. You cannot gate on "did the broker relay faithfully?" You can gate on "does the
  bulletin contain the fact, and was every affected row re-verified?"
- It inverts this skill's founding division: comprehension belongs to the model, verification and
  routing belong to a script.

**So: a middle file, not a middle agent. The broker is `fold_ledger.py`.**

The one legitimate hierarchy is different in kind: past ~7 workers (§2.2), split by *sub-scope* — a role
lead that owns a slice of the scope and its own sub-spine — not by *message routing*. That is
map-reduce nesting, and it still bottoms out in files.

### 5.5 Where fork belongs

The host's **fork** — a subagent inheriting the entire conversation — is the exact runtime primitive for
the half of "share context for decisions, isolate for judgment" that this repo has never had a mechanism
for. Use a fork for a worker that must act *consistently with the run so far* (an implementation slice, a
decision that has to match earlier decisions). Use a named subagent with a clean window for a worker
whose job is to *disagree* (any checker, any adversary). The maker/checker rule then has teeth at the
runtime level rather than the prose level: **a checker must never be a fork.**

---

## 6. Landing this in the repo without breaking it

Every change is additive; no existing contract changes behaviour.

| Change | Why it is safe |
|---|---|
| **New** `references/agent-comms.md` — the ladder, the six laws, the board schema, the spawn additions | progressive disclosure: read only when a job actually fans out. Existing single-agent runs never load it. |
| `references/subagent-contracts.md` — add a `BRIEF:` and `MESSAGES:` block to the spawn contract; extend the escalation section with the rung-4 option | appends to an existing block. `NO-SPAWN` and the one-re-spawn cap stay exactly as they are. |
| `references/contract-template.md` §2 — list the four board files as **optional, multi-agent only** | §2 already enumerates spine files; a single-agent job simply has none of these. |
| `scripts/fold_ledger.py` — new flags `--claims`, `--bulletin`, `--messages`, `--require-adjudication`, `--max-messages-per-agent` | **all default off.** Absent the flags the gate behaves byte-identically, so every existing fixture keeps passing. |
| `docs/REQUIREMENTS.md` — a new **Coordination** section, requirements 33–38 | the matrix is explicitly designed to be re-audited "whenever the canon moves". |
| `docs/SOURCES.md` — a new **Multi-agent coordination** block, tagged | same discipline as every other claim; §2 above is already in that format. |
| `docs/LOOP-ENGINEERING.md` §3 — a sixth failure mode: **coordination loss** | genuinely new: it cannot occur in a single loop, so it is an addition rather than a correction. |

### 6.1 Proposed requirements 33–38

| # | Requirement | Why |
|---|---|---|
| 33 | Shared priors broadcast before fan-out, frozen and sha-pinned | two workers otherwise make incompatible implicit decisions |
| 34 | Item ownership recorded, so nothing is done twice or dropped | duplicated work and silent omission are distinct MAST modes |
| 35 | Discovery propagation is pull-based from an append-only board, not pushed as narration | "excessive updates" is a measured failure; a pull survives compaction |
| 36 | The direct channel is typed, capped and logged, never load-bearing | delivery is unverifiable, so nothing checkable may depend on it |
| 37 | Every inter-agent contradiction carries an adjudication, or the gate fails | the only part of coordination a script can actually verify |
| 38 | Coordination rules the host can enforce are enforced by the host, not requested in prose | capability lives in the runtime — already this repo's position on credentials |

### 6.2 Requirement 38, concretely — and a bonus that closes an open item

Three rules this repo currently *asks* for can be *enforced* today:

- **`NO-SPAWN` (requirement 19) is currently fighting the runtime default.** Subagents can nest three
  layers deep unless told otherwise. Setting `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` to `1`, or omitting
  `Agent` from a role's `tools`, makes the flat spawn ceiling real instead of conventional.
- **Role authority becomes a tool allowlist.** "Read only your authority source" is prose; a
  `disallowedTools` list on a read-only reviewer is enforcement. Denying `SendMessage` for roles that
  must not talk makes law 4's cap structural.
- **A malformed worker return can be rejected at the boundary.** `SubagentStop` can block (exit 2) and
  receives `last_assistant_message` — so a schema check on the returned JSONL can bounce a worker back
  to fix its own output instead of the orchestrator repairing it downstream.

And the bonus, adjacent but earned by the same research: **`REQUIREMENTS.md`'s first known open item is
closable.** It says "the gate is opt-in… a host-level stop-hook that blocks turn-end until the gate
passes would close it." The `Stop` hook **can** block with exit 2. So can `TaskCompleted`. The gate can
stop being compliance and start being enforcement. That is a separate change from this one and should be
scoped on its own — but it is no longer hypothetical.

---

## 7. Honest limitations

- **Rungs 4 and 5 are not portable.** Cross-session messaging needs v2.1.224+, macOS or Linux, and is
  absent on Bedrock, AWS, Google Cloud and Foundry; agent teams are experimental and off by default.
  Any contract using them must degrade to rung 3 — which is why rung 3 has to be sufficient alone.
- **Parallel coordination is not reliably faster.** CodeCRDT measured up to 39.4% slowdown on some task
  shapes alongside 21.1% speedup on others (§2.5). A fan-out must state its expected win and record in
  `metrics.jsonl` whether it materialised.
- **The board costs context.** Every worker reading `brief.md` and `bulletin.jsonl` pays for them on
  every spawn. Both need hard caps (a bulletin of 30 rows, a brief that fits one screen) and must be
  read at item boundaries, never continuously.
- **Adjudication could produce false failures.** Law 6 must require a contradiction to be *recorded and
  adjudicated*, never *absent* — the existing rule that a dissenting lens is a finding, not a rubric
  defect, stands. Tightening a rubric until lenses agree is precisely the anti-pattern.
- **Not measured here.** The 36.9%, the 72.7%, the 21.1%/39.4% and the ~15× are other people's numbers on
  other people's systems. The ladder, the six laws and the board schema are **[H]** — this repo's
  synthesis, unproven end-to-end, exactly like the rest of the behavioural half.

---

## 8. The one-paragraph answer

Do not build a chat network, and do not build a broker agent. **Promote the spine to a blackboard**:
broadcast the shared priors before the fan-out so no two workers can decide the same thing differently,
record ownership so nothing is done twice or dropped, publish mid-run discoveries as append-only facts
that peers pull at item boundaries, and keep the direct channel for a closed set of typed, capped, logged
messages that may accelerate a run but may never be load-bearing for its correctness. Then extend the
gate so an unadjudicated contradiction between two agents exits non-zero — because the reason this layer
is worth adding at all is that it is the first version of inter-agent communication a script can check.

---

## 9. Sources

**Failure data and taxonomies**
- MAST — *Why Do Multi-Agent LLM Systems Fail?* — https://arxiv.org/abs/2503.13657 (NeurIPS 2025 D&B)
- CodeCRDT — *Observation-Driven Coordination for Multi-Agent LLM Code Generation* — https://arxiv.org/abs/2510.18893
- *LLM-based Multi-Agent Blackboard System for Information Discovery* — https://arxiv.org/abs/2510.01285
- *Scaling Large Language Model-based Multi-Agent Collaboration* (MacNet) — https://arxiv.org/abs/2406.07155
- MetaGPT — shared message pool and role-based subscription — https://arxiv.org/abs/2308.00352
- *Faithful, Not Corrective: Message-Format Effects in Multi-Hop Agent Relays* — https://arxiv.org/abs/2607.09678

**Position pieces**
- Cognition — *Don't Build Multi-Agents* (2025) — https://cognition.com/blog/dont-build-multi-agents
- Cognition — *Multi-Agents: What's Actually Working* (2026) — https://cognition.com/blog/multi-agents-working
- Anthropic — *How We Built Our Multi-Agent Research System* — https://www.anthropic.com/engineering/multi-agent-research-system

**Host mechanisms (primary)**
- Subagents, nesting depth, fork — https://code.claude.com/docs/en/sub-agents
- Cross-session messaging, inbound controls, limits — https://code.claude.com/docs/en/cross-session-messaging
- Agent teams, mailboxes, shared task list, limitations — https://code.claude.com/docs/en/agent-teams
- Hook events and blocking semantics — https://code.claude.com/docs/en/hooks
- Worktrees — https://code.claude.com/docs/en/worktrees

> Two caveats on sourcing, kept visible rather than tidied away: `anthropic.com`, `arxiv.org` and
> `cognition.com` were unreachable from this session's network, so those four items were read through
> search summaries and secondary coverage rather than fetched directly. Verify the exact figures against
> the primary text before they are promoted into `SOURCES.md` as **[E]**. The `code.claude.com` pages
> were fetched directly and are quoted as read.
