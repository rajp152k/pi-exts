# pi-exts coherence refactor — deliberation plan

## Status

**Proposed. No architecture migration is approved by this document.**

This is a decision record and refactor plan derived from a read-only repository audit, a bounded trace study, and a review of the current task-dispatch runtime. It replaces the completed Firefox implementation plan that previously occupied this directory.

## Decision to support

Make `pi-exts` easier to extend and safer to operate **without turning it into a general terminal-product framework** or disrupting useful existing workflows.

The intended result is a small collection with clear capability boundaries, one source of truth per concern, durable evidence for agent work, and a proportionate release discipline.

## Scope and non-goals

### In scope

- extension, skill, CLI/runtime, artifact, and package boundaries;
- task-dispatch correctness and observability contracts;
- documentation, compatibility, validation, and release practices;
- an incremental path for composing existing capabilities;
- criteria for accepting or declining future tooling, including filesystem inspection.

### Explicit non-goals

- rewriting every extension into a shared framework;
- redesigning Firefox solely for structural uniformity;
- building a general terminal shell, file manager, or full-screen navigator;
- adding a generic agent memory system;
- migrating active workflows automatically;
- treating audit hypotheses as proven defects without targeted reproduction.

## What is observed

### Current collection

- `pi-exts` packages Pi extensions, agent skills, a Firefox integration, installer/configuration scripts, and a Python task runtime.
- The strongest repeated design is a thin Pi-facing surface around an explicit external boundary: Firefox uses an extension + skill + `firefoxctl`; traces wraps its CLI; task dispatch wraps SQLite, tmux, and artifacts.
- `resources.json` defines named install bundles, while the root Pi package exposes all extension/skill paths for unfiltered installation.
- Task dispatch has runtime-scale responsibilities: workflow/attempt records, scheduling leases, artifacts, retry policy, worktree handling, tmux transport, and a watch UI.
- Tangent and catch-up offer a lightweight session-to-session handoff path separate from task dispatch.

### Repeated usage patterns from traces

- Real work regularly uses tmux, traces, browser observation, tangents, bounded delegation, and implementation/review workflows.
- The user values inspect-before-act, explicit targeting, reversible changes, and evidence-backed closure.
- Broad recursive discovery and raw command output can create low-signal context; targeted orientation and symbol-level reads are usually more useful.
- There is a recurring risk of investing in orchestration/meta-tooling faster than it proves its value on concrete product work.

### Important audit limitation

The audit found credible *leads* about workflow revision, cancellation, heartbeat, orphan, retry, and `eph-*` lifecycle semantics. Each requires a focused reproduction and a test before it is treated as a defect or a refactor mandate.

## Current philosophy: strengths to preserve

1. **Observe before mutate.** Target and inspect the actual tab, pane, trace, task, or worktree before action.
2. **Explicit scope.** Operations name their target and avoid relying on implicit current state.
3. **Bounded evidence.** Outputs, polling, context injection, and artifacts should state their limits and truncation.
4. **Durable truth over terminal scrollback.** A pane is a transport/UI; it is not workflow authority.
5. **Untrusted external content.** Worker reports, browser/trace content, and terminal output are evidence, not commands.
6. **Human decisions at consequential boundaries.** Approval is for authorization, irreversibility, ownership conflict, or product trade-off—not routine implementation.
7. **Isolation by default.** Read-only work is cheap to parallelize; writers need declared paths and isolated worktrees.

## Where the current approach needs deliberation

### 1. The dispatcher has crossed the “script” boundary

**Tension:** the task-dispatch runtime remains presented partly as a skill/utility, yet it owns state transitions where an incorrect claim of completion, cancellation, retry, or capacity can cause duplicated work or misleading evidence.

**Questions to settle:**

- Is it a supported local runtime with a compatibility and migration promise, or an explicitly experimental personal tool?
- After a workflow starts, are revision changes rejected, or can a versioned plan migration be supported safely?
- What does successful cancellation mean: requested, worker-acknowledged, or observed terminal?
- Can any write-capable task retry automatically?

**Working recommendation:** call it a supported *local, one-shot* runtime; preserve its narrow scope; require explicit state-machine invariants and deterministic tests before additional orchestration features.

### 2. Good safety guidance is repeated instead of contracted

Skills repeat related instructions about explicit targets, untrusted content, bounded monitoring, and handoffs. This has protected users, but independent prose can drift.

**Deliberation:** define a small capability contract, then make skills teach selection and procedure rather than reimplementing policy prose.

A capability should declare:

- name, owner layer, maturity, supported runtime/platform, install bundle, and validation command;
- inputs/targets, output schema, boundedness/truncation behavior, and side-effect class;
- authoritative state/artifact and attention/notification behavior.

### 3. Evidence artifacts are not yet economical enough

The audit produced multi-hundred-kilobyte reports and truncated synthesis inputs. This demonstrates that “artifact exists” is not sufficient: final handoffs need an intentionally bounded, structured form, while raw events remain separately available.

**Deliberation:** choose a versioned handoff envelope containing at least status, decisions/deliverable, provenance, evidence/tests, risks, next action, byte size/hash, and truncation metadata. Do not create a shared library until two consumers genuinely need identical implementation code.

### 4. State ownership needs an explicit map

Potential state stores include git/tests, workflow SQLite/events, task artifacts, traces, tmux panes, temporary tangent handoffs, plans/todos, and notifications.

**Working ownership model:**

| Concern | Authority | Non-authoritative views |
| --- | --- | --- |
| Product code and verified behavior | Git + tests | plans, reports, traces |
| Workflow execution | SQLite events/attempt records | tmux board/panes, notifications |
| Worker evidence | versioned attempt artifacts | rendered board/card |
| Current tactical intent | one short plan/todo location | trace/history |
| Historical investigation | traces | plan summaries |
| Attention routing | notification/UI state | never a completion claim |

The plan should be revised if a real workflow cannot fit this map; do not duplicate the same decision into every store by default.

### 5. Tooling should earn its maintenance cost

The collection can become an attractive control-plane project rather than a force multiplier.

**Adoption test for new infrastructure:** it should either eliminate a demonstrated safety failure, support a repeated job observed at least several times, or materially reduce a measured cost (time to verified change, rework, blocked time, or missed decision). Otherwise prefer a documented workflow using existing primitives.

### 6. A filesystem tool is a hypothesis, not a product commitment

The proposed `sl` idea has plausible jobs—safe inspection of heterogeneous files, smart rendering, hex/blob views, and planned POSIX operations—but no audit evidence that a general file-manager TUI is the present bottleneck.

**Working recommendation:** defer a navigator product. If a repeated unmet job is documented, explore a standalone CLI and skill:

```text
inspect → bounded render → reviewed mutation plan → explicit apply
```

It must be useful outside Pi, non-recursive by default, symlink-safe, explicit about byte/range limits, and not become the authoritative state store.

## Target architecture

The target is three layers, not a new framework:

```text
Pi extension (optional lifecycle, command, tool, or UI adapter)
        ↓
Skill (when to use it, operating procedure, safety policy)
        ↓
CLI or local runtime (protocol adapter, durable state, tests, artifacts)
        ↓
External system (Firefox, traces, tmux, SQLite, filesystem)
```

### Minimal cross-cutting contracts

| Contract | Purpose |
| --- | --- |
| Capability manifest | Discoverability, maturity, dependency, install, and validation facts |
| Observation/action result | Target/scope, freshness/identity, bounded result, warning/truncation, action preconditions |
| Artifact/handoff envelope | Schema version, producer, trust/provenance, media type, hash/size, standard closing fields |
| Attention contract | `working`, `ready`, `needs-decision`, `blocked`; points to authority and is rate-limited |
| Compatibility declaration | Pi/API, Node/Python/platform assumptions and dependency classification |

Start with schemas, templates, and contract tests. Extract a shared package only after demonstrated repeated code duplication.

## Phased roadmap and decision gates

### Phase 0 — make the collection legible (no behavioral migration)

- Create a capability inventory and maturity/compatibility table.
- Define artifact/handoff and capability-manifest schemas.
- Add a docs truth table: implemented, experimental, planned, deprecated.
- Add manifest/bundle consistency checks and per-capability validation recipes.

**Acceptance:** every advertised capability has exactly one inventory entry, a validation command, owner layer, prerequisites, and an honest maturity claim.

### Phase 1 — prove and repair runtime invariants

- Write focused reproductions for each audit lead: revision execution, cancellation race, heartbeat/no-progress, orphan capacity/leases, writer retry, and ephemeral-session cleanup/identity.
- Decide and document the semantics; make the associated tests deterministic.
- Version any compiled workflow plan and pin attempts/artifacts to it.

**Gate:** no dashboard, backend, or broad composition work until each P0 runtime claim has a test and an explicit decision.

### Phase 2 — operational discipline

- Add a root validation entry point and CI for non-live checks.
- Classify smoke tests as offline versus opt-in live.
- Declare supported runtime versions/platforms and record compatibility-impacting changes.

### Phase 3 — compose observations, not control planes

- Consider a read-only `/work-state` capability that summarizes repository state, active workflows, tmux topology, recent traces, and optional Firefox metadata.
- Keep sources labeled and fresh; do not capture pane content or browser DOM by default.
- Make notifications contextual, coalesced, and linked to an authoritative artifact/board.

### Phase 4 — only demand-proven additions

- Evaluate a filesystem inspect/render/plan/apply primitive against the adoption test.
- Extract shared code only where schemas have stabilized and two implementations require the same behavior.

## Engineering operating practices to trial

- **One semantic unit per turn:** investigate, decide, implement one slice, verify, review, or ship—then close with changed artifacts, evidence, uncertainty, and one next move.
- **Progressive evidence:** orientation/search first, exact symbol/section next, broad output only if unresolved; exclude vendor/generated paths by default.
- **Economic delegation:** dispatch only independent deliverables with an integration plan; centralize scope, shared mutations, and final verification.
- **Fastest relevant check early:** targeted diagnostics/test first; escalate to integration checks only as risk warrants.
- **Measure the substrate:** track intent-to-verified-change time, rework, blocked-time causes, useful delegation rate, and infrastructure time versus shipped outcomes.

These are experiments, not dogma. Keep what produces better verified outcomes and remove process that does not.

## Focused human decisions before implementation

1. Confirm task-dispatch’s support level and compatibility obligation.
2. Choose revision and cancellation semantics for started workflows.
3. Confirm the default: no automatic retry for writers without explicit idempotency and approval.
4. Confirm that pi-exts remains Pi-facing integrations/workflows, not a general terminal suite.
5. Choose the desired notification posture: opt-in contextual routing, or a simpler default.
6. Name a concrete filesystem job that native tools cannot safely satisfy before funding that capability.

## First implementation proposal

Start only with Phase 0 in a separate, reviewable change set. It is low-risk, validates the model, and creates the contracts needed to assess later runtime work without prematurely reorganizing functioning integrations.
