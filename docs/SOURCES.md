# Sources

> For what these sources add up to, see [LOOP-ENGINEERING.md](LOOP-ENGINEERING.md); for how this skill
> measures against them, [REQUIREMENTS.md](REQUIREMENTS.md).
Every empirical claim this skill makes, and where it comes from. Claims are tagged:

- **[E]** established — primary source: a paper, official documentation, or an engineering write-up by
  people who shipped the system
- **[P]** practitioner opinion — widely held, not measured
- **[H]** house heuristic — *our* rule of thumb, stated here so it is never mistaken for a measurement
- **[C]** contested — the literature disagrees, or the position has been superseded

A claim with no tag in the skill text and no row here is a bug. Say "we estimate", not a number, when
you do not have a source.

---

## Canonical writing on agent loops

| Source | URL |
|---|---|
| Anthropic — Building Effective Agents | https://www.anthropic.com/engineering/building-effective-agents |
| Anthropic — Effective Context Engineering for AI Agents | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents |
| Anthropic — Writing Tools for Agents | https://www.anthropic.com/engineering/writing-tools-for-agents |
| Anthropic — How We Built Our Multi-Agent Research System | https://www.anthropic.com/engineering/multi-agent-research-system |
| Anthropic — Claude Code Best Practices | https://code.claude.com/docs/en/best-practices |
| Anthropic — Agent Skills | https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview |
| Anthropic — Context editing & memory tool | https://platform.claude.com/docs/en/build-with-claude/context-editing |
| Manus — Context Engineering: Lessons from Building Manus | https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus |
| Cognition — Don't Build Multi-Agents (2025) | https://cognition.com/blog/dont-build-multi-agents |
| Cognition — Multi-Agents: What's Actually Working (2026) | https://cognition.com/blog/multi-agents-working |
| OpenAI — A Practical Guide to Building Agents | https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf |
| OpenAI Agents SDK — Running agents (termination semantics) | https://openai.github.io/openai-agents-python/running_agents/ |
| LangChain — Context Engineering for Agents | https://www.langchain.com/blog/context-engineering-for-agents |
| LangChain — Introducing Ambient Agents (HITL primitives) | https://www.langchain.com/blog/introducing-ambient-agents |
| ReAct — Synergizing Reasoning and Acting | https://arxiv.org/abs/2210.03629 |
| Reflexion — Language Agents with Verbal Reinforcement Learning | https://arxiv.org/abs/2303.11366 |
| Voyager — An Open-Ended Embodied Agent (skill library) | https://arxiv.org/abs/2305.16291 |
| MAST — Why Do Multi-Agent LLM Systems Fail? | https://arxiv.org/abs/2503.13657 |
| LLMs Get Lost in Multi-Turn Conversation | https://arxiv.org/abs/2505.06120 |
| Willison — The Lethal Trifecta | https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/ |

## Verification and evaluation

| Claim used in this skill | Tag | Source |
|---|---|---|
| Judges score near chance on *objective correctness* (~56%), unlike on preference | **[E]** | JudgeBench — https://arxiv.org/abs/2410.12784 |
| LLM-judge biases: position, verbosity, self-enhancement; mitigations incl. reference-guided grading | **[E]** | MT-Bench / Chatbot Arena — https://arxiv.org/abs/2306.05685 |
| A panel of diverse smaller judges beats one large judge | **[E]** | PoLL — https://arxiv.org/abs/2404.18796 |
| Binary checklist decomposition beats scalar scoring | **[E]** | TICK — https://arxiv.org/abs/2410.03608 |
| Self-correction without external feedback *degrades* reasoning — the producer cannot grade itself | **[E]** | https://arxiv.org/abs/2310.01798 |
| `pass^k` (all k runs agree) is the production bar, not `pass@k` | **[E]** | τ-bench — https://arxiv.org/abs/2406.12045 |
| Fewer than half of LLM-generated unit tests are fully correct | **[E]** | https://arxiv.org/abs/2305.00418 |
| LLM-written oracles often encode *actual* rather than *expected* behaviour — they rubber-stamp the bug | **[E]** | https://arxiv.org/abs/2410.21136 |
| LLM-generated executable oracles from documentation are largely correct when the property is stated | **[E]** | https://arxiv.org/abs/2411.01789 |

## Verification without ground truth

| Claim | Tag | Source |
|---|---|---|
| Metamorphic testing finds real defects in shipped financial software | **[E]** | Metamorphic Testing of Tax Preparation Software — https://arxiv.org/abs/2205.04998 |
| Independently written versions fail *together* far more than independence predicts | **[E]** | Knight & Leveson 1986 — http://sunnyday.mit.edu/critics.pdf |
| …replicated with coding agents: 429 coincident failures where independence predicts 115 | **[E]** | https://arxiv.org/abs/2606.20158 |
| Property-based testing as an answer to the oracle problem | **[E]** | https://hypothesis.works/articles/what-is-property-based-testing/ |
| Reconciliation as a first-class automated check | **[E]** | https://docs.soda.io/data-testing/data-reconciliation |
| Backtest overfitting: the number of trials must be logged or the threshold is meaningless | **[E]** | Deflated Sharpe Ratio — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551 |
| Continuous peeking inflates false positives far above the nominal rate | **[E]** | Standard sequential-testing result; see also alpha-spending / always-valid CIs |
| Groundedness/faithfulness checks decompose claims to atomic units | **[E]** | RAGAS — https://docs.ragas.io · SelfCheckGPT — https://arxiv.org/abs/2303.08896 |

## Context and cost

| Claim | Tag | Notes |
|---|---|---|
| Cost grows with the square of turn count because history is re-sent, `≈ Δ·n(n+1)/2` | **[P]** | A modelling convention, **not** a cited result. Stated in practitioner writing only. Caching changes the constant, not the order. |
| Quality degrades because attention is quadratic in pairwise token relations ("context rot", attention budget) | **[E]** | Anthropic context-engineering (above). **Distinct from the cost claim — do not merge them.** |
| Multi-turn performance drops sharply vs the same task stated once (~-39% across tasks) | **[E]** | https://arxiv.org/abs/2505.06120 |
| KV-cache hit rate is the dominant cost lever; stable prefix, append-only, deterministic serialization | **[E]** | Manus (above) |
| Prefer masking a tool to removing it — removal rewrites the prefix and voids the cache | **[E]** | Manus (above) |
| Keep the error signal in context; recovery is the clearest sign of a working loop | **[E]** | Manus (above) |
| …but clear the bulk payload; runtimes now evict stale tool results automatically | **[C]** | Manus vs Anthropic context-editing. Our reconciliation — keep signal, drop payload — is **[H]**. |
| Recitation of the goal at the tail of context counters drift | **[E]** | Manus (above) |
| Progressive tool disclosure sharply reduces at-rest token cost | **[E]** | Anthropic tool-writing + Agent Skills (above) |

## House heuristics — ours, not measurements

| Claim | Tag |
|---|---|
| "Typical audits are 60–70% deterministic" | **[H]** — our observation across audits we have run; no study behind it |
| "A sub-agent is roughly a thousand times the cost of a grep" | **[H]** — order-of-magnitude illustration, not a benchmark |
| Compact at 60% rather than 90% | **[H]** — informed by context-rot findings; the specific threshold is ours |
| `k=3` as the default agreement bar | **[H]** — a convention; τ-bench establishes `pass^k` matters, not the value of k |
| The eight-rung oracle ladder and its ordering | **[H]** — our synthesis of the sources above |

## Contested — where we took a side

| Question | Our position | Why |
|---|---|---|
| Multi-agent: never, or fine? | Writes single-threaded; read-only/advisory sub-agents fine; share context for decisions, isolate for judgment | The 2025 "never" was partly withdrawn in 2026; the disagreement was always about write concurrency |
| Cache-warming wake intervals | Reject. Choose the interval from the change rate | Tuned to a 5-minute TTL that no longer holds everywhere; optimises the cost of asking, not whether there is anything to ask |
| LLM-as-judge | Triage signal only, never a gate | Near-chance on objective correctness (JudgeBench) |
| RAG vs long context | Retrieve, then reason over the retrieved set | Context rot: long windows degrade non-linearly |
| "Keep everything in context" | Keep the signal, drop the payload | Manus and context-editing collide; neither states the reconciliation |
