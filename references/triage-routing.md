# Triage: Route, Else Design

The front-door. Given a **raw need** in any domain, decide the right response instead of reflexively
writing a contract: route to a capability that already exists, or — only when none fits — design one.

This is loop engineering applied to the *choice of response*. The same law governs it: a response is
bounded by the verifier that checks it, so the order is **oracle → route (cheap) → design (dear)**, and
the cheapest response a verifier can still check wins.

## When to skip triage

If the user handed an explicit long-running job ("audit PR #57", "migrate auth to X"), they have already
triaged — go straight to `SKILL.md` step 1 and write the contract. Triage is for a *raw need*, not a
specified job.

## 1. Oracle first

Answer, before anything else: **"how will the user know this need is met, without asking a human?"**
(`oracle-catalog.md`). The oracle does double duty — it filters candidate capabilities and becomes the
success test of whichever path you choose. If you genuinely cannot name one, stop: this is a
checkpointed collaboration, not an autonomous anything, and say so plainly.

## 2. Classify the need's shape

Shape, not domain, picks the path. Domain only sharpens matching.

| Shape | The tell | Default path |
|---|---|---|
| One-shot task | a single verifiable action | do it inline / one tool call |
| Long-running job | many steps; needs a spine + termination | contract (`SKILL.md` steps 1–5) |
| Question / advice | the deliverable is an answer + citations | answer directly, or route to a research capability |
| Novel build | nothing existing covers it | bespoke design |

## 3. Route — score the live inventory

**Source: the inventory already in context** — the skills listing, the agent-type roster, plugin/MCP
tool names. Never a hardcoded catalog; it rots and binds the skill to one host. Re-read it fresh each
time, at zero token cost. If the host surfaces no such listing, there is nothing to survey — treat it
as no fit and design.

Score each candidate on three axes, in this order:

1. **Purpose-match** — does its stated purpose cover this need's shape + domain?
2. **Verifiability** — can its output be checked against the oracle (§1)? An unverifiable match is a weak
   match, no matter how on-topic it reads. This axis is decisive: it is the guard against false-fit.
3. **Cost fit** — is it proportionate? A heavy sub-agent or skill for a trivial task fails the
   `execution-protocol.md` net-token test (a call must remove more from context than it adds).

**Strong fit** = clears purpose-match AND verifiability. Break ties by **specificity** (the most
specific capability that still covers the need) then lowest cost. If the best candidate is weak on
verifiability, treat it as no fit and go design.

Survey **once**. Rank, decide, move. Re-scoring the same inventory in circles is the routing form of a
dead loop.

## 4. Decision table

| Need shape × inventory | Path | Then |
|---|---|---|
| strong capability fit | **route** | recommend it; offer to run (gated, §5) |
| long job, no single fit | **contract** | `SKILL.md` steps 1–5; do not execute |
| trivial one-shot | **inline** | recommend doing it now; a contract is overhead |
| novel / no fit | **bespoke** | components + its oracle + first step (§5) |

A partial fit is not a fit. If one capability covers 60% of the need, say which 40% it misses and design
for that remainder — do not route the whole need to it and hope.

## 5. The recommendation (a mini-contract)

Emit exactly this, and stop — triage is a decision, not a deliverable:

```
NEED:         <one line>
ORACLE:       <how we'll know it's met, without a human>
PATH:         route → <capability>  |  inline  |  contract  |  bespoke
WHY:          <one line — names the verifiability, not just the topic match>
FIRST ACTION: <the exact next step>
RUN?          <the offer; and what confirmation is needed before anything irreversible>
```

For **route**: name the capability and its exact invocation, then offer to run it — never auto-run.
For **contract**: hand off to `SKILL.md` steps 1–5; "run" means writing the contract, still not
executing the job. For **bespoke**: the components, the oracle, and the first step are the whole output;
if it turns out to be a long job, fold it back into a contract.

## Guardrails — the loop-eng failure modes, applied to routing

- **False-fit (silent success).** Never recommend a capability whose output you can't check against the
  oracle. "Sounds relevant" is the routing form of a false PASS.
- **Over-routing (waste).** A heavy skill/sub-agent for a trivial task fails the net-token test. Inline it.
- **Analysis paralysis (budget/stall).** Survey once, threshold, decide. No re-scoring loops.
- **Domain-keyword drift.** Match the need's *shape*, not its buzzwords. "It mentions crypto" is not
  "it needs the crypto plugin."
- **Auto-run (irreversibility).** Recommend, then offer. Routing may invoke a capability once the user
  confirms; an irreversible action still waits for explicit human confirmation — the standing rule the
  contract's §1 APPROVAL gate encodes. Routing never commits the user.

## Anti-patterns

- Writing a contract for a need one existing skill already covers — the most expensive way to skip triage.
- Routing to a capability because its name matches a keyword, without checking its output is verifiable.
- A hardcoded list of "known good skills" — it rots, and it makes the skill host-specific.
- Turning the mini-contract into a report. It is five lines and an offer.
