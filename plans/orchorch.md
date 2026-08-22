# Orchorch — campaign orchestration design

## Status

**Phase 1 and the display-only overview are implemented:** pure campaign-contract simulation, an explicitly selected separate append-only campaign ledger, and a one-shot `campaign status`/`campaign watch` projection. The overview reads ledger references and child SQLite authority read-only, labels missing/stale/mismatched authority as blocking, and never dispatches, schedules, retries, merges, inspects tmux, copies child runtime records, or claims completion.

`orchorch` is the proposed higher-order orchestration practice and capability for coordinating multiple durable task-dispatch workflows toward one bounded outcome. It is not a general control plane and must preserve child workflow SQLite databases and artifacts as their respective authorities.

## Glossary

| Term | Meaning |
| --- | --- |
| Campaign | A bounded, durable coordination of phases and child workflows toward one outcome. |
| Design / simulate | A dry run: strategy and predicted execution only; creates no workflow, tmux, or mutable runtime state. |
| Scout | The discovery stage that maps unknowns, risks, interfaces, evidence, and user decisions before commitment. |
| Strategy | The approved campaign plan: phases, workflows, model policy, budgets, gates, integration ownership, and acceptance checks. |
| Phase | An ordered outcome boundary inside a campaign. |
| Workflow | A child task-dispatch DAG with its own SQLite database and artifact root. |
| Task / attempt | Existing task-dispatch meanings: a DAG node and one concrete execution of it. |
| Integration checkpoint | Mandatory review, verification, and Git-recording boundary after a writer workflow. |
| Consolidation | The terminal campaign report of outcome, evidence, incidents, opportunities, and required attention. |
| Attention event | A deduplicated, actionable event for the user rather than raw runtime telemetry. |
| Wisdom set | Curated, versioned institutional knowledge: policies, scrolls, and precedents. |
| Policy | A binding, scoped rule using must/must-not/requires-approval language. |
| Scroll | Evidence-backed advisory guidance or pattern using prefer/consider/observed language. |
| Harvest | Candidate knowledge extracted from campaign consolidation. |

## Approved first slice

`campaign simulate --file campaign.json` is a read-only contract check. It validates versioned campaign JSON, ordered acyclic phases, unique child references and hashes, existing child-workflow validation findings, phase-level advancement/integration gates, explicit bounded delegations, and one explicit integration declaration with complete evidence for every writer. Required integration evidence is base SHA, resulting commit SHA, verification references/hashes/results, owner, integrator, and timestamp. Its canonical output contains predicted phases, hashes, findings, and required approvals. It creates no SQLite, tmux, artifacts, child workflows, processes, dispatches, integrations, commits, or records.

Integration follows the approved lifecycle:

```text
preparer → authority → integrator → recorder
```

User approval is the default. Delegation is permitted only when it is granted by the user and names its authority, actions, bounded scope, and expiry; it cannot be implicit or re-delegated. Explicit delegations may authorize dispatch, integration, recording, or writer retry. A writer-retry delegation additionally binds one exact attempt and workflow revision and declares idempotency. Writer patches are never auto-integrated or auto-retried.

## Lifecycle

```text
design/simulate → scout → strategy → dispatch → integrate → consolidate → harvest/review
```

Design is intentionally distinct from dispatch. A campaign cannot advance past a writer workflow merely because a worker settles: it enters `awaiting-integration`. It becomes eligible only after an approved integration, Git commit, and recorded verification evidence. Campaign gates are phase-level advancement/integration decisions; workflow task gates retain their existing child-workflow readiness meaning.

## Authority and durable state

A future campaign registry may persist campaign intent, immutable revisions, phase/workflow references, approvals, integration commits, and campaign events. It must not replace child workflow authority:

| Concern | Authority |
| --- | --- |
| Child tasks/attempts/events | Child workflow SQLite database |
| Child evidence | Child artifact root |
| Integrated product behavior | Git plus verification |
| Campaign intent, gates, integration records | Campaign registry |
| Presentation | Campaign overview and child boards are non-authoritative views |

Missing, stale, or ambiguous child state blocks the campaign; no UI/pane output may imply completion.

## Model policy

Campaign configuration names roles rather than hard-coding a provider:

```json
{
  "models": {
    "campaign": {"model": "gpt-5.6-sol", "thinking": "adaptive"},
    "commander": {"model": "gpt-5.6-terra", "thinking": "adaptive"},
    "executor": {"model": "gpt-5.6-luna", "thinking": "adaptive"}
  }
}
```

- Campaign role: scout synthesis, strategy, cross-workflow risk analysis, consolidation.
- Commander role: workflow decomposition, gate checking, evidence review, and integration coordination.
- Executor role: bounded research, implementation, and verification tasks.

Dispatch validates that configured models and thinking modes are available. Adaptive thinking is bounded by campaign policy. Model escalation, a consequential model switch, or a writer retry is recorded; it is never silent. Select roles by ambiguity, coordination cost, and risk—not model prestige.

## Scout and strategy requirements

Every non-trivial campaign begins with a bounded scout stage. Its output records observed facts, assumptions, unknowns, interface boundaries, risks, estimated work, candidate phases, and decisions that require the user. Strategy creates all reviewed child workflow JSON specifications before child dispatch and declares dependencies, resources, model roles, integration owners, acceptance checks, budgets, monitoring cadence, and autonomy boundaries.

## Attention events

Raw telemetry remains in child SQLite/event logs. An attention event is emitted only when the user can act and carries:

```text
kind: decision | approval | integration | blocked | incident | opportunity
authority: Git / child SQLite / artifact / external system
impact: what cannot safely proceed
options: bounded actions
recommendation: one proposed action with rationale
confidence: observed | inferred
deadline: optional explicit deadline
```

Events are deduplicated and coalesced, always link to authority, and never notify merely because information exists.

## Wisdom set

The wisdom set is a curated institutional-memory corpus, not unconstrained agent memory. Proposed records are bounded, attributable, scoped, and versioned. They contain provenance, applicability, exclusions, confidence, owner/reviewer, status (`proposed`, `reviewed`, `adopted`, `superseded`, `retired`), review date, and evidence links/hashes. It stores no secrets, raw pane scrollback, or unbounded transcripts.

Instruction precedence is:

```text
current user instruction > campaign charter > recorded campaign decision
> adopted scoped policy > workflow contract > scroll/precedent > default guidance
```

Scouts retrieve only relevant entries. Commanders record overrides. Executors receive a minimal scoped slice. Workers cannot promote their own output to binding policy. Consolidation harvests candidate scrolls; reviewed, repeated, evidence-backed practices may later be promoted to policies. Stale, contradictory, or high-override entries are reviewed or retired.

## Interface

The initial skill is `skills/orchorch/SKILL.md`, invoked as `/skill:orchorch`. A plain `/orchorch` alias requires a separate Pi extension and remains deferred. `campaign status` and `campaign watch` are display-first, one-shot JSON projections; actions remain explicit CLI operations.

## Non-negotiable constraints

- Child SQLite/artifacts remain authoritative and replayable.
- Every child spec is reviewed/validated before campaign dispatch.
- Writers are isolated and never auto-integrated or auto-retried.
- Cross-workflow advancement requires recorded integration evidence.
- The overview cannot infer completion from panes.
- Attention events are actionable, bounded, and source-linked.
- Wisdom retrieval is scoped, attributable, and non-binding unless a reviewed policy applies.

## Approved completion plan

The simulation contract is implemented. The remaining work is deliberately sequential: campaign runtime code and its tests share the task-dispatch boundary, and each writer change requires an explicit integration checkpoint before the next phase starts.

### 1. Persistent campaign ledger

Implement a separate, explicitly selected SQLite ledger (never the default child-workflow database). It is an append-only record of campaign actions over time, not a second scheduler.

It persists only:

- immutable campaign revisions and canonical plan hashes;
- phase intent and gate/approval decisions;
- child workflow locators (workflow ID, database/root path, spec/revision/hash) and observation timestamps;
- integration proposals, approvals, applied commits, verification evidence, and recorder attestations;
- source-linked campaign events and terminal consolidation records.

It must not copy child task/attempt state, reports, raw events, leases, retries, Git working-tree state, or tmux-derived completion. Child observations are refreshed from their authority and fail closed when missing, stale, or revision-mismatched.

The ledger state model is:

```text
draft → approved → running → awaiting-integration → blocked | completed | cancelled
```

`awaiting-integration` is entered after a writer child reaches its authoritative terminal result. It may advance only after a valid integration record identifies base SHA, resulting commit SHA, verification references/hashes/results, owner/integrator, authority approval, and timestamp.

### 2. Campaign execution commands

Add narrow explicit commands to create, inspect, approve/reject gates, observe child authority, propose/approve/apply/record integration, pause/resume, and consolidate a campaign. No command may auto-dispatch a child, auto-integrate, auto-merge, auto-retry, or infer completion from tmux. Child workflow start remains an explicit, recorded protected action.

Default authority is the user. Delegation is valid only when it names an authority, allowed actions, bounded campaign/phase/workflow/path scope, expiry, required checks, and revocation condition. It is not transitive. Delegated writer retries additionally require the exact failed attempt, pinned revision, and declared idempotency.

### 3. Display-only campaign overview — implemented

`campaign status` and its `campaign watch` alias emit a one-shot display-only overview from the selected ledger and its child authority locators. It shows declared/observed phase state, freshness, child board/artifact links, gates, integration state/commit, recorded incidents, and a conservative next action. The projection reads child SQLite with a read-only URI, does not refresh observations, and labels missing, stale, unreadable, or revision/hash-mismatched authority as blocking. It cannot schedule, retry, integrate, or make a completion claim.

### 4. Campaign consolidation

Implement a deterministic terminal consolidation record/report with outcome, planned-versus-observed phase progress, authority-linked evidence, incidents and dispositions, decisions still required, opportunities, measured delivery metrics, and recommended next campaign. Consolidation may harvest wisdom candidates but cannot promote them.

### 5. Wisdom-set pilot

Start with Git-versioned, human-reviewable records and deterministic scoped tag retrieval. Add policy/scroll/precedent lifecycle, provenance, expiry, supersession, application/override ledger, and review gates. Do not add a centralized service, embeddings/RAG, automatic extraction, autonomous promotion, or policy enforcement until measured retrieval failures justify it.

### 6. Attention and routing pilots

Only after ledger/overview events are authoritative, pilot opt-in calm attention: deduplicated `decision`, `approval`, `integration`, `blocked`, and `incident` events with source links and resolution lifecycle. Replace routine settled popups only after measuring missed decisions, blocked time, action rate, coalescing, dismissal, and staleness.

Treat adaptive model selection as a policy resolver from task/campaign difficulty to a preflight-validated provider-qualified model and explicit thinking level. Establish baseline routes first; record every selection/escalation, cost, latency, quality, and failure. Do not silently substitute unavailable models or adopt routing without evidence against the baseline.

## Completion criteria

Orchorch is complete only when all of the following are true:

1. Simulation, ledger, command boundaries, and overview have deterministic tests proving no duplicate/split authority or forbidden side effects.
2. Every campaign action is replayable from immutable revisions, ledger events, child authority references, integration commits, and evidence hashes.
3. Integration cannot be bypassed and delegation is bounded, auditable, and revocable.
4. Consolidation reports expose evidence, incidents, opportunities, and attention requiring user action.
5. Wisdom, attention, and routing remain measured pilots with explicit defer/remove criteria rather than assumed permanent infrastructure.
