# Coordinated AI Coding Workers — Research Findings

## Conclusion

There is a substantial body of work on multi-agent software engineering, but most of it coordinates **roles and dialogue**, rather than independently writing into one shared checkout. A robust implementation should combine agent-specific coordination mechanisms with established workflow and distributed-systems controls.

## Evidence-backed design principles

1. **Use explicit task contracts and a dependency DAG.**
   A coordinator turns project intent into bounded tasks with objective, inputs pinned to a revision, acceptance evidence, dependency IDs, declared write scope, retry class, and approval requirement. A dependency's accepted artifact—not a worker's claim that it is done—unblocks later work.

2. **Give writers isolated worktrees/branches.**
   Each implementation task operates in its own Git worktree. This prevents uncommitted filesystem collisions, but does not eliminate semantic/API/merge conflicts; ownership and integration controls are still required.

3. **Make state durable and artifacts structured.**
   The coordinator should own an append-only event history and immutable artifacts: task status, decisions, interface contracts, patches, test results, review evidence, and handoffs. Messages should reference task and artifact IDs/hashes instead of serving as the sole source of truth.

4. **Lease scarce resources and declared ownership.**
   Path, lockfile, migration, generated-manifest, environment, or browser ownership needs explicit leases. Leases should expire and be heartbeated so a lost worker does not block the system forever.

5. **Separate completion from integration.**
   A worker may propose a result, but independent validation, approval, and serialized integration decide whether it is accepted. One integration owner rebases/checks the current base, resolves conflicts, and runs the integrated acceptance suite.

6. **Retry only safe, classified failures.**
   Apply bounded retry/backoff only to transient, idempotent infrastructure failures. Do not automatically retry destructive work, authorization failures, merge conflicts, test regressions, or repeated substantive failures; escalate those as new tasks or human decisions.

## Suggested minimum viable protocol

```text
intent
  -> parallel read-only discovery / design / review
  -> coordinator synthesis or human gate
  -> isolated writer tasks (worktree + declared write paths)
  -> validation and review tasks
  -> one integration task
  -> full acceptance checks
```

Task state should distinguish at least:

```text
proposed -> ready -> assigned -> running -> submitted
         -> validated -> approved -> integrated
```

Terminal exceptions include `failed`, `blocked`, `cancelled`, and `lost`. A worker's terminal message alone is not authoritative.

### Compact worker handoff

- status and confidence;
- decisions and rationale;
- source/base revision and artifacts produced;
- files changed, declared scope, and test commands/results;
- risks, assumptions, conflicts, and a recommended next action.

## Main failure modes and controls

| Failure mode | Control |
| --- | --- |
| Stale context | Pin inputs/base SHA; invalidate submissions after relevant upstream changes; re-read before integration. |
| Concurrent/conflicting edits | Isolated worktrees, declared path/API ownership, preflight merge/conflict checks, explicit reconcile task. |
| False completion | Artifact validation and gate evidence, not self-reported completion. |
| Lost worker / split brain | Expiring leases, heartbeats, fencing/attempt tokens, event-log reconciliation. |
| Unsafe retries | Failure taxonomy, idempotency, bounded backoff, approval-required external effects. |
| Shared/global files | Assign a single owner for lockfiles, migrations, generated outputs, and central manifests. |

## What existing work supports

- **Task graphs / role decomposition:** [CodeR](https://arxiv.org/abs/2406.01304), [MAGIS](https://arxiv.org/abs/2403.17927), [AgileCoder](https://arxiv.org/abs/2406.11912), [MetaGPT](https://arxiv.org/abs/2308.00352), and [ChatDev](https://arxiv.org/abs/2307.07924).
- **Repository-level evaluation:** [SWE-bench](https://arxiv.org/abs/2310.06770) and [SWE-bench Verified](https://openai.com/index/introducing-swe-bench-verified/). These measure issue resolution but not concurrent merge safety.
- **Multi-agent orchestration evidence:** Anthropic's [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) describes parallel subagents, context compression, checkpoints, and deterministic safeguards.
- **Workflow durability and retries:** [Temporal workflow execution](https://docs.temporal.io/workflow-execution) and [retry policies](https://docs.temporal.io/encyclopedia/retry-policies).
- **Leases/coordination primitives:** [Kubernetes Leases](https://kubernetes.io/docs/concepts/architecture/leases/) and [etcd transactions, watches, leases, and locks](https://etcd.io/docs/v3.5/learning/api/).
- **Git isolation and merge control:** [Git worktree](https://git-scm.com/docs/git-worktree), [Git merge-tree](https://git-scm.com/docs/git-merge-tree), and [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

## Validation plan

Start small: compare a one-agent baseline against a coordinator with two disjoint writer tasks and one deliberately conflicting task. Record acceptance-test pass rate, conflict/rework rate, review burden, wall-clock latency, and token/cost usage. Do not infer safety from benchmark pass rate alone.

## Research artifacts

The completed four-task research workflow is stored outside the repository at `/tmp/worker-coordination-research-runs/`; its synthesis report is in `20260821-032120-synthesize-coordination-research-eb5978/report.md`.
