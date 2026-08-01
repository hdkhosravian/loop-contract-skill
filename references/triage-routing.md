# Triage: Route, Else Design

The front-door. Given a **raw need** in any domain, decide the right response instead of reflexively
writing a contract: route to a capability that already exists, or — only when none fits — design one.

This is loop engineering applied to the *choice of response*. The same law governs it: a response is
bounded by the verifier that checks it, so the order is **oracle → route (cheap) → design (dear)**, and
the cheapest response a verifier can still check wins.

## What an explicit job does and does not skip

An explicit job ("audit PR #128", "migrate auth to X") fixes the **shape and the intent** — carry those
forward instead of re-deriving them. It does **not** exempt §3: survey the live inventory once before
designing. The user cannot see that inventory, and on a request like "audit PR #128" an existing
capability often covers the job outright — writing a bespoke contract instead is the most expensive
way to start.

Skip triage entirely only when the user names the path themselves: "write me a contract for…",
"use skill X".

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

## 1b. Confirm the inputs exist before anything else

Name the concrete inputs the §1 oracle consumes — the holdings file, the three CSVs, the API, the repo
path — and **check each is actually reachable**. "Analyse my portfolio" with no holdings file in the
working directory should not proceed on whatever the agent infers and hand back confident numbers
wrapped in full loop-eng ceremony; the ceremony makes an ungrounded answer look verified.

A missing required input is the best possible use of the one permitted question. Record the result on
the `INPUTS:` line of the mini-contract (§5), including anything you had to substitute.

## 2a. Split a bundle before classifying it

A single message often carries **several needs with different intents** — "here are two bug reports, a
few feature ideas, the app feels slow, and is the architecture right?" is four: two DONE fixes, some
maybe-DONE features, a DONE-but-unmeasured perf item, and a KNOWN architecture question.

Steps 2b and 3 assume *one* intent and *one* oracle. Forcing a bundle through them picks whichever
intent you noticed first and silently drops the rest — which reads to the user as guessing.

So: **before classifying, list the distinct needs.** Each gets its own line, its own intent, its own
oracle, its own path. Then:

- Ask **one** question — the only one worth spending: show the numbered list with your proposed
  intent and path per item and ask which to do now, in what order, and what to drop. This is not
  interrogation; it is the split you cannot infer. (It is exempt from the one-question cap in the same
  way an APPROVAL gate is.)
- If the user said "don't ask": order them yourself — **safety-affecting first, then explicitly
  reported defects, then measurable work, then open questions, then speculative ideas** — state the
  order plainly, and proceed.
- **Never freeze speculative items into scope without confirmation.** An idea floated while thinking
  aloud must not become work the run is contractually forbidden from abandoning (see the scope-freeze
  rule for inferred scope in `contract-template.md` P1-SCOPE).

Work the resulting needs as separate sub-jobs in order, each with its own oracle — not as one blurred
job with one oracle that fits none of them.

## 2b. Classify the intent — DONE or KNOWN

Shape sizes the loop; **intent decides what the run must end with**. Ask:

> *"If the run returns a perfect report and changed nothing, is the user happy?"* — **No → DONE.**

| Job type | Intent | Deliverable | Oracle default |
|---|---|---|---|
| verify / audit / review-for-conformance | KNOWN | verdict + evidence | every row verdicted; gate exits 0 |
| research / investigate-only | KNOWN | cited findings | a sample re-verified |
| implement / build | **DONE** | working code in the repo | acceptance test written **red** first, then green + suite green |
| fix-all | **DONE** | the problem gone everywhere | the detector that found them now returns 0 + regression green |
| investigate-then-fix | **DONE** | the diagnosis **and** the applied fix | repro fails for the right reason, then goes green |
| produce-artifact (plan, design, curriculum) | **DONE** | the artifact itself | ratified acceptance criteria per component |

A DONE job that fits one session is simply **done here** — write the failing check, make the change,
re-run it. A DONE job too big for one session gets a **DONE-mode contract**, never an audit-shaped one.

## 2c. A review that finds issues proceeds to fix

Finding an issue is not the deliverable unless findings-only was asked. Three authorization modes:

- **autonomous-remediate** (default for reversible, in-sandbox fixes; any "fix everything" phrasing) →
  find → fix → verify each → regression, without stopping.
- **gated-remediate** (large blast radius, or "show me what you find first") → stop after find, present
  ranked findings **plus proposed fixes**, resume on the user's word.
- **findings-only** (explicitly asked) → this is a KNOWN job; the report is the deliverable.

Fix in severity order; verify each fix on its own. If one is out of scope or too risky, say so per item
— never silently downgrade the whole job to a report.

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
| DONE intent, fits one session | **do it** | write the failing check, make the change, re-run it; the artifact is the deliverable |
| long job, no single fit, KNOWN intent | **contract (KNOWN mode)** | `SKILL.md` steps 1–5, then execute it in this session until the named DELIVERABLE exists and the gate exits 0 |
| long job, no single fit, DONE intent | **contract (DONE mode)** | `SKILL.md` steps 1–5 + the DONE blocks in `contract-template.md`; the run's output is the artifact, not `REPORT.md` |
| trivial one-shot | **inline** | do it now; a contract is overhead |
| novel / no fit | **bespoke** | components + its oracle + first step (§5) |

A partial fit is not a fit. If one capability covers 60% of the need, say which 40% it misses and design
for that remainder — do not route the whole need to it and hope.

## 5. The recommendation (a mini-contract)

Emit exactly this, and stop — triage is a decision, not a deliverable:

```
NEED:         <one line>
DELIVERABLE:  <the concrete thing the user receives — src/… passing tests | every issue fixed+verified | MARKETING-PLAN.md | REPORT.md>
MODE:         DONE (change the world) | KNOWN (establish the truth)
INPUTS:       <every input the oracle consumes, and whether each is reachable — path found / API reachable / table pasted / MISSING>

ORACLE:       <how we'll know it's met, without a human — for DONE, the check that is red right now>
PATH:         route → <capability>  |  do it  |  inline  |  contract  |  bespoke
WHY:          <one line — names the verifiability, not just the topic match>
FIRST ACTION: <the exact next step>
RUN?          <the offer; and what confirmation is needed before anything irreversible>
```

For **route**: name the capability and its exact invocation, then offer to run it — never auto-run.
For **route**: the offer is not the end of your responsibility. When the routed capability returns,
**check its output against the oracle you fixed in §1** and report that result alongside it. A routed
capability inherits none of this skill's machinery — no frozen scope, no per-item proof, no gate — so
the oracle is the only protection the user still has; skipping it means routing quietly opts them out
of the one guarantee they came for. If the output cannot be checked against that oracle, it was a weak
fit by this file's own definition (§3) — say so and design instead. For a **multi-item** need, add a
fourth scoring axis: does the candidate enumerate the full item set and give each a terminal verdict?
If not, it is at most a partial fit and the contract branch wins.

For **do it** / **inline**: you already have the ask. Do **not** emit the `RUN?` offer and do not stop —
name the check in one line, do the work, report the result. The stop-and-offer discipline exists for
handing someone else's capability the wheel, not for work you were plainly asked to do.

For **contract**, either mode: write it per `SKILL.md` steps 1–5, then **execute it in this session**
until the named DELIVERABLE exists — the document is the spine, not the finish line. A KNOWN review
whose deliverable is `REVIEW.md` is not finished until `REVIEW.md` exists. The single exception lives in
`SKILL.md` §5: the user explicitly asked for a contract to run elsewhere. For **bespoke**: the components, the oracle, and the first step are the whole output;
if it turns out to be a long job, fold it back into a contract.

## Guardrails — the loop-eng failure modes, applied to routing

- **Document-instead-of-deliverable (the DONE-side silent success).** Handing back a report, a plan, or
  a contract *about* the work when the user asked for the work — the exact mirror of "doing the job
  instead of writing the contract". Both are failures; which one you are committing depends on the
  intent you classified in §2b.
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
