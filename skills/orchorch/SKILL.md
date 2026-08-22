---
name: orchorch
description: Design and simulate a bounded, reviewable multi-workflow campaign without dispatching it.
---

# Orchorch

Use `/skill:orchorch` to design a campaign before any child workflow is created or dispatched. This first slice is **simulation only**:

```bash
skills/pi-task-dispatch/scripts/task-dispatch campaign simulate --file campaign.json
```

It reads the campaign and referenced child workflow JSON files, validates them, and prints a canonical JSON projection. It does **not** create SQLite state, tmux windows, artifacts, child workflows, processes, dispatches, or retries.

## Campaign schema version 1

```json
{
  "schemaVersion": 1,
  "id": "release-prep",
  "approvals": {"default": "user", "delegations": []},
  "models": {"executor": {"model": "opaque-name", "thinking": "adaptive"}},
  "phases": [
    {
      "id": "prepare",
      "dependsOn": [],
      "gates": ["strategy-review"],
      "childSpecs": [
        {
          "ref": "workflows/prepare.json",
          "sha256": "<sha256 of canonical child JSON (sorted keys, compact separators)>",
          "integrations": [
            {"writer": "implement", "owner": "maintainer", "checkpoint": "prepare-integration"}
          ]
        }
      ]
    }
  ]
}
```

Phases are emitted in declared order and their `dependsOn` graph must be acyclic. Every child reference and declared SHA-256 is globally unique. Every referenced child workflow is validated through existing `workflow validate` rules. Each `default-tools` child task is a writer and needs exactly one integration declaration with an explicit owner and checkpoint. Every phase needs explicit gates.

The projection contains predicted phases, computed and declared child hashes, child validation findings, and user-required gate approvals. A nonzero exit means any error finding exists; warnings from child workflow validation remain visible in the projection.

Model roles are opaque declarations only. `adaptive` is a policy: it resolves later to a provider-qualified, explicit thinking level. It is not a runtime routing value and simulation does not resolve or route models.

## Approval and integration policy

The integration lifecycle is always:

```text
preparer → authority → integrator → recorder
```

User approval is the default. Any delegation must name its authority, actions, and bounded scope. Dispatch, integration, and recording are protected actions and cannot be delegated. Simulation does not execute approvals, integration, recording, or any protected action.

Do not add a campaign registry, dispatch operation, TUI, attention delivery, wisdom engine, model routing, extension alias, auto-integration, or retry behavior to this slice.
