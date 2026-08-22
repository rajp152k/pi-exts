# Orchorch — campaign orchestration design

## Status

**Phase 1, explicit child context binding, and the display-only overview are implemented:** pure campaign-contract simulation, an explicitly selected separate append-only campaign ledger, immutable opt-in campaign child context preparation/binding, and a one-shot `campaign status`/`campaign watch` projection. The overview reads ledger references and child SQLite authority read-only, labels missing/stale/mismatched authority as blocking, and never dispatches, schedules, retries, merges, inspects tmux, copies child runtime records, or claims completion.

`orchorch` is an experimental, higher-order practice for coordinating multiple durable task-dispatch workflows toward one bounded outcome. Its current runtime is a separate campaign ledger and read-only projections, not a general control plane; child workflow SQLite databases and artifacts remain authoritative.

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

User approval is the default. The implemented approval check accepts the user directly, or an unexpired delegation JSON naming the actor, relevant action, and a scope containing the campaign ID. It does not enforce phase/workflow/path scope, required checks, or revocation conditions; document and review those constraints separately. A `writer-retry` delegation is schema-checked for one attempt, one workflow revision, and `idempotency: true`, but campaign commands never retry work. Writer patches are never auto-integrated or auto-retried.

## Lifecycle

```text
design/simulate → scout → strategy → dispatch → integrate → consolidate → harvest/review
```

Design is intentionally distinct from dispatch. The ledger records integration evidence after a writer settles, but does not implement campaign advancement or state transitions. For an explicitly opted-in child, `prepare-child-context` creates a bounded immutable hand-off of approved ancestor gates and hash-checked selected artifact references. The child stores that binding in its own SQLite authority; creation and start must both name the same context, and missing, stale, modified, or revision/hash-mismatched context blocks worker dispatch. This is evidence binding, not parent scheduling. Treat `awaiting-integration` and eligibility as review policy: require an approved integration, Git commit, and recorded verification evidence before a human starts a dependent child workflow. Campaign gates are phase-level records; workflow task gates retain their child-workflow readiness meaning.

## Authority and durable state

The implemented campaign ledger persists campaign intent, immutable revisions, phase/workflow references, approvals, integration commits, and campaign events. It does not replace child workflow authority:

| Concern | Authority |
| --- | --- |
| Child tasks/attempts/events | Child workflow SQLite database |
| Child evidence | Child artifact root |
| Integrated product behavior | Git plus verification |
| Campaign intent, gates, integration records | Campaign registry |
| Presentation | Campaign overview and child boards are non-authoritative views |

Missing, stale, or ambiguous child state blocks the campaign; no UI/pane output may imply completion.

## Route-preflight pilot

Campaigns do not dispatch or select models. `campaign route-preflight` records an operator-supplied task locator, one explicit provider-qualified `{provider, model, thinking}` route, availability list, cost, latency, escalation source, and outcome. It fails closed when that exact route is absent and never substitutes or invokes a model. Treat any role policy as planning guidance until a separately reviewed runtime implements it.

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

## Implementation notes and remaining boundaries

The simulation contract, separate ledger, explicit records, and display-only overview are implemented. They remain intentionally narrow and do not schedule child workflows.

### 1. Persistent campaign ledger — implemented

The separate, explicitly selected SQLite ledger is never the default child-workflow database. It is an append-only record of campaign actions over time, not a second scheduler.

It persists only:

- immutable campaign revisions and canonical plan hashes;
- phase intent and gate/approval decisions;
- child workflow locators (workflow ID, database/root path, spec/revision/hash) and observation timestamps;
- integration proposals, approvals, applied commits, verification evidence, and recorder attestations;
- source-linked campaign events and terminal consolidation records.

It must not copy child task/attempt state, reports, raw events, leases, retries, Git working-tree state, or tmux-derived completion. Child observations are refreshed from their authority and fail closed when missing, stale, or revision-mismatched.

The intended review lifecycle is:

```text
draft → approved → running → awaiting-integration → blocked | completed | cancelled
```

It is not a ledger state machine. The ledger can record the evidence needed for a reviewer to apply that lifecycle: child observations, gate/proposal approvals, resulting commit SHA, verification evidence, recorder attestation, and timestamps.

### 2. Campaign ledger commands — implemented

The ledger provides narrow explicit commands to create, inspect, approve/reject gates, observe child authority, propose/approve/record integration, pause/resume, and consolidate a campaign. No command auto-dispatches a child, integrates, merges, retries, or infers completion from tmux. Child workflow start remains outside campaign commands.

Default authority is the user. A non-user integration or recording actor must supply a delegation recognized by the runtime: a user grant naming the actor, relevant action, scope containing the campaign ID, and unexpired expiry. It is authorization evidence, not an action; it cannot dispatch, integrate, record, or retry on its own. Operational path scope, checks, and revocation conditions must be recorded and reviewed outside the current runtime check. A `writer-retry` delegation is additionally schema-checked for the exact attempt, pinned revision, and `idempotency: true`, but campaign commands never retry work.

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
