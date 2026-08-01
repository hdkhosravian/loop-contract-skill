# Recurring Jobs — the same contract, run on a schedule

Everything else in this skill designs **one** run. This file covers a job that repeats: a weekly audit,
a nightly test-gap sweep, a monthly reconciliation. Recurrence is the cheapest form of Loop 4 — the
value is not the individual run, it is the **delta between runs**.

A recurring job is a normal contract with three additions: a fixed oracle, a comparable ledger, and a
report that says *what changed*. Without those it degenerates into the same findings re-printed forever,
which trains everyone to ignore it — the failure mode is alert fatigue, not incorrectness.

## Standard jobs

Each is a contract with a real oracle, not a prompt. Adopt the shape; set the interval per §Interval.

| Job | MODE | Oracle | Deliverable |
|---|---|---|---|
| `audit` | KNOWN | scanner exit code + each finding's reachability verdict | new findings since last run |
| `testgaps` | KNOWN | coverage delta **+ mutation score** on changed lines | uncovered branches that are newly reachable |
| `deps` | DONE | lockfile diff + build + suite green | upgraded lockfile, or a blocked list with reasons |
| `optimize` | DONE | benchmark vs a **committed** baseline, threshold fixed first | measured improvement, or "no regression found" |
| `reconcile` | KNOWN | control totals tie to zero, or each variance explained | exceptions list (finance: see oracle-catalog) |
| `docdrift` | KNOWN | every documented claim resolves to a `path:line` that still exists | claims that no longer match the code |
| `dataquality` | KNOWN | schema, volume, freshness, uniqueness, referential integrity | rows or invariants that broke since last run |
| `benchmark` | KNOWN | numbers vs committed thresholds, run on fixed hardware | regressions beyond noise |

`consolidate`, `map`, `predict` and similar housekeeping jobs are deliberately **not** here: they have
no oracle, so they cannot report a trustworthy delta. Run them if they help, but not through this skill
— dressing an unverifiable chore in loop machinery only makes it look verified.

## Interval — derive it from the change rate, never from a cache TTL

Ask: **how fast can the thing being measured actually change?** A dependency audit on a repo with three
commits a week has nothing new to say every fifteen minutes. Pick the interval so that a typical run
finds *something*; if most runs find nothing, the interval is too short and you are training the reader
to skim.

- tied to commits → run on the commit, not on a clock (a hook or CI, not a timer);
- tied to the outside world (CVE feeds, market data, vendor prices) → its publication cadence;
- tied to accumulation (coverage drift, doc drift) → weekly or per-release;
- tied to a closing period (reconciliation) → the period boundary.

Do **not** set the interval from a prompt-cache TTL. That is a real pattern in other loop tools —
wake every 270s to stay under a 5-minute cache window — and it is backwards: it optimises the cost of
*asking* while ignoring whether there is anything to ask about. Cache TTLs differ per host and change
over time; change rates do not.

## `/loop` versus `CronCreate`

- **`/loop`** — in-session, self-pacing, dies with the session. Use while you are actively working:
  a sweep that should keep running for the next few hours.
- **`CronCreate`** — persistent, survives restarts, runs unattended. Use for genuine monitoring.

The rule that matters: an **unattended** recurrence needs a *stronger* oracle than an attended one,
because nobody is reading the transcript. If the oracle is rung 6 or lower (`oracle-catalog.md`), keep
it attended, or have it produce a diff for a human rather than take action.

Never let a recurring job perform an irreversible action unattended. The APPROVAL gate does not weaken
because the job is routine — it is *more* important, since routine is exactly when nobody looks.

## The delta is the deliverable

A recurring run must answer **"what changed since last time?"**, and that requires comparability:

1. **Keep the oracle and the scope fixed** between runs. Changing either makes runs incomparable, and
   a "new" finding is then indistinguishable from a redefined one. If you must change them, say so
   loudly in that run's report and treat it as a new baseline.
2. **Keep the previous ledger.** Store runs as `.claude/loops/<slug>/runs/<date>/`, with `latest`
   pointing at the newest. Diff this run's ledger against the previous one by row id.
3. **Report three buckets, not one list**: **new** (absent last run), **fixed** (present last run, gone
   now — worth celebrating and worth checking the fix was real), and **persisting** (with an age: "open
   14 runs" is a much stronger signal than "open").
4. **Suppress with a reason, never silently.** A finding ruled out-of-scope goes to
   `decisions.jsonl` with its rationale and stops appearing as new. An un-suppressible finding that
   nobody will fix is how a report becomes noise.
5. **Escalate on trend, not on instance.** One flaky test is a finding; the same test flaking for six
   runs is a different, larger problem. Only a persistent ledger can see that.

## Guardrails

- **A recurring job without an oracle is a scheduled opinion.** It will be right often enough to be
  trusted and wrong often enough to hurt.
- **Same findings every run = the job is failing**, even when each finding is individually correct.
  Fix the suppression path or the interval.
- **Budget applies per run.** A cheap job on a tight timer is more expensive than an expensive job on a
  sensible one; multiply before scheduling.
- **A recurrence that never terminates needs an owner.** Record who reads it in the contract. An
  unread recurring job should be deleted, not muted.
