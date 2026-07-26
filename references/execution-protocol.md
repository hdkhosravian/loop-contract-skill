# Executing a Loop Contract (Claude Code host)

For the **fresh session that runs a contract** — not the session that writes one. The contract is the
spine; this is how to run it well on a host that has sub-agents, skills, and plugins: advanced, and cheap.

## The prime constraint

A loop runs as long as its verifier is good **and its token curve stays flat**. Every rule here serves
that. "Use the best tools" never means "spend more" — it means route work so the orchestrator's own
context stays small. When in doubt, fewer better tokens beats more agents.

## Kickoff

1. The contract is a file in the repo. Read it **once**, fully. After that never read it whole again —
   orient from `PROGRESS.md` (§2). Do not summarise it back to the user. Do not plan out loud.
2. If `<dir>/PROGRESS.md` already exists, this is a **resume**: continue from its "Next action". Else
   first action = §7.

## Host capabilities — for isolation, not flex

Sub-agents / skills / plugins earn their cost by keeping bulky reading **out of your window**, not by
looking busy:

- **Read-heavy phases** (P1 harvest, P3 judgement, research sweeps, large-surface search) → dispatch
  to sub-agents (Task/Agent tool, `Explore` agent) under §Sub-agents: batch by role, strict schema,
  hard token cap, store only the structured return. Their reading never enters your context.
- **A grep or a test settles it?** Do it inline. A sub-agent is ~1000× the cost of a grep for the same
  answer — never spawn for what a deterministic check answers.
- **A skill/plugin already encodes the domain step?** Invoke it (`Skill` tool, relevant MCP/plugin)
  instead of hand-rolling — that spends its budget, not yours. But only when it maps the actual step;
  a wrong skill is pure overhead.

Reconciliation, stated plainly: every spawn/skill call must **remove more tokens from your context than
it adds**. If it doesn't, do it inline.

**The harvest is the clearest case of the trade.** Sub-agents let the corpus be read exhaustively while
your window grows only by JSONL — a 500k-token doc set harvested inside a small orchestrator context.
That is what buys recall the old pattern-matching extractor could not have, and it is worth paying for
in exactly one phase. Send shards, not files; receive rows, not reasoning. See
`references/harvest-protocol.md`.

## Make the gates non-bypassable (hooks)

A gate the agent runs voluntarily is a gate the agent can forget under budget pressure — at the exact
moment forgetting is most tempting. On a Claude Code host, wire it into the harness instead. A `Stop`
hook runs when the agent tries to end its turn, and a non-zero exit blocks the stop and feeds stderr
back to the model:

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command",
                     "command": "python scripts/fold.py --ledger audit/ledger.jsonl --verdicts audit/verdicts.jsonl --out audit/REPORT.md >&2 || exit 2" } ] }
    ]
  }
}
```

Exit 2 blocks; the gate's own error list becomes the agent's next instruction. Now "done" is enforced
by the runtime rather than asserted by the thing being judged — the same reason §1's APPROVAL gate is
scoped at the session, not promised in prose. Keep the hook cheap: it fires on every stop, so it must
be a script exit code, never a model call.

## Token discipline is non-negotiable (§4)

- **Deterministic before expensive.** Settle every gettable item with `rg` / test / typecheck before any
  model judgement — 60–70% of most jobs, at near-zero tokens and zero hallucination.
- Evidence is `path:line`. Big output → disk, `head -30`, cite the path. Query the spine (`jq`/`grep`),
  never `cat` it whole.
- Compact at 60%, not 90%. Append-only spine; never rewrite history (it also preserves the KV-cache).

## Remember across compaction

The contract file + `PROGRESS.md` survive `/clear` and compaction — that is why the contract is on disk,
not in chat. On any drift, re-read only §0 (mission) and §4 (token policy), not the whole document.

## Stop honestly

BLOCKED with a reason beats a fabricated PASS. Completion is `fold.py` exit 0 — a fact, never your
judgement. Irreversible writes wait for the §1 APPROVAL gate.
