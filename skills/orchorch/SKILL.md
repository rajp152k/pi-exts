---
name: orchorch
description: Design and simulate a bounded, reviewable multi-workflow campaign without dispatching it.
---

# Orchorch

Use `/skill:orchorch` to design a campaign before any child workflow is created or dispatched:

```bash
skills/pi-task-dispatch/scripts/task-dispatch campaign simulate --file campaign.json
```

`campaign simulate` remains read-only. The approved Phase 1 ledger commands below create records only in an explicitly selected separate SQLite file; they do not dispatch, schedule, retry, merge, or inspect tmux.

## Explicit Phase 1 ledger

Use a dedicated ledger, never a child workflow database:

```bash
task-dispatch campaign create --ledger /tmp/campaign-ledger.sqlite --file campaign.json
task-dispatch campaign inspect --ledger /tmp/campaign-ledger.sqlite release-prep
task-dispatch campaign gate --ledger /tmp/campaign-ledger.sqlite release-prep --phase prepare --gate strategy-review --decision approved --actor user --rationale reviewed
task-dispatch campaign observe --ledger /tmp/campaign-ledger.sqlite release-prep --phase prepare --workflow child-id --child-database /path/child.sqlite --artifact-root /path/artifacts --revision 1 --sha256 <revision-hash>
```

`propose-integration`, `approve-integration`, and `record-integration` are separate explicit records. Recording requires a fresh matching child revision/hash, an approved integration gate and proposal, complete commit/verification evidence, and user (or unexpired bounded) authority. `pause`, `resume`, and `consolidate` only append campaign events/records. Consolidation is deterministic from campaign references and never infers child completion; an optional reviewed input can list only proposed wisdom candidates.

## Measured, constrained pilots

All pilots require the explicit ledger and record observations only. They never dispatch children, control a model, send an alert, or promote a rule.

- **Wisdom:** Store Git-versioned JSON policy, scroll, or precedent records with lifecycle status, scoped tags, provenance, expiry, owner, and reviewer. `campaign wisdom retrieve --tag <tag> --at <ISO-8601>` uses deterministic tag matching and returns reviewed/adopted non-expired entries only. `apply` records an attributed application or override. No service, RAG/embeddings, automatic harvest, promotion, or enforcement exists.
- **Attention:** `campaign attention record` accepts only actionable source-linked event JSON and deduplicates an open fingerprint; `resolve` closes it. It is opt-in, produces no notification, and excludes routine settled or merely informational events.
- **Routing:** `campaign route-preflight` accepts an explicit provider-qualified model and thinking level plus an operator-supplied available-route list. It fails closed for any mismatch, never substitutes or dispatches a model, and only records an explicit selection/escalation with cost, latency, and supplied outcome for baseline review.

## Display-only overview

```bash
task-dispatch campaign status --ledger /tmp/campaign-ledger.sqlite release-prep
# `watch` is the same one-shot, display-only overview.
task-dispatch campaign watch --ledger /tmp/campaign-ledger.sqlite release-prep
```

The overview reads the ledger and named child SQLite authorities read-only. It labels missing, stale, unreadable, and revision/hash-mismatched authority as **BLOCKED** and shows child board/artifact links, gates, integrations, incidents, and a conservative next action. It does not refresh observations, schedule, dispatch, retry, integrate, or claim campaign completion.

## Campaign schema version 2

```json
{
  "schemaVersion": 2,
  "id": "release-prep",
  "approvals": {
    "default": "user",
    "delegations": []
  },
  "phases": [
    {
      "id": "prepare",
      "dependsOn": [],
      "gates": [
        {"id": "strategy-review", "decision": "advance"},
        {"id": "prepare-integration", "decision": "integrate"}
      ],
      "childSpecs": [
        {
          "ref": "workflows/prepare.json",
          "sha256": "<sha256 of canonical child JSON>",
          "integrations": [
            {
              "writer": "implement",
              "owner": "maintainer",
              "checkpoint": "prepare-integration",
              "evidence": {
                "baseSha": "<40-64 lowercase hex Git SHA>",
                "resultingCommitSha": "<40-64 lowercase hex Git SHA>",
                "verification": [
                  {"reference": "ci://build/42", "sha256": "<64 lowercase hex hash>", "result": "passed"}
                ],
                "integrator": "maintainer",
                "recordedAt": "2026-01-01T00:00:00Z"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

Phases are in declared order and `dependsOn` must form an acyclic graph. Each child reference and declared hash is globally unique, and each referenced workflow is validated by existing `workflow validate` rules. Every `default-tools` child task is a writer and needs exactly one integration declaration.

Campaign gates are phase-level decisions: `advance` permits movement to the next lifecycle phase and `integrate` authorizes the integration checkpoint. They are not workflow task gates: workflow task gates retain their existing child-workflow readiness meaning. A phase that contains writer integrations requires an `integrate` gate.

The evidence contract is required for every writer integration: base SHA, resulting commit SHA, verification references/hashes/results, integration owner, named integrator, and timestamp. Simulation validates only the shape and deterministic identifiers; it does not perform or record Git integration.

## Advancement and authority policy

The campaign lifecycle is:

```text
writer settled → awaiting-integration → approved integration
→ Git commit plus verification evidence recorded → eligible
```

The user is the default authority. For this repository, the user permits the primary assistant to receive campaign-specific, explicitly recorded `integrate` approval delegations. A delegation is valid only when it explicitly has `grantedBy: "user"`, named `authority`, non-empty `actions`, bounded `scope`, ISO-8601 `expiresAt`, required checks, and a revocation condition. It cannot be implicit or re-delegated. Dispatch, recording, and writer retry remain user-controlled unless separately delegated. The only delegation actions are `dispatch`, `integrate`, `record`, and `writer-retry`.

A `writer-retry` delegation is additionally bound to one `attemptId`, one positive `workflowRevision`, and `idempotency: true`. Declaring a delegation does not execute it. There is no auto-integration and no retry behavior in this slice.

The projection contains predicted phases, computed and declared child hashes, child validation findings, and user-required gate approvals. A nonzero exit means any error finding exists; child-workflow warnings remain visible.

Do not add scheduling, dispatch operations, retries, integration actions, pane-derived completion, attention delivery, wisdom retrieval, model routing, extension aliases, or auto-integration to the display-only overview. The pilots above are explicit ledger commands, not overview behavior.
