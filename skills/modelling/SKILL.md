---
name: modelling
description: Frame, build, critique, compare, validate, or use a model of a system, claim, or decision. Use for systems, causal, statistical, optimization, simulation, ontology, uncertainty, or decision-modelling work.
---

# Model a system or decision

Turn the supplied context into a **bounded, inspectable, revisable model specification** that serves a stated decision or question. A model is purpose-bound and partial: do not imply that it captures the whole world.

Optimize for clarity, decision relevance, and calibrated uncertainty—not mathematical sophistication or false precision.

## Operating rules

1. Establish the decision, purpose, audience, time horizon, stakes, and cost of error before selecting a model.
2. State the unit of analysis, level of abstraction, system boundary, and exclusions. Most apparent model disagreements are boundary or definition disagreements.
3. Define terms operationally. Distinguish entities, types, attributes, relations, events, states, units, and latent constructs. Do not treat an ambiguous label or proxy as a well-defined variable.
4. Label **observations**, **assumptions**, **estimates**, and **value judgments** separately.
5. Distinguish association, prediction, causal explanation, and intervention. Do not infer causal effects from observational correlation without a causal identification argument.
6. Separate hard constraints/invariants from preferences, forecasts, and policy choices. Do not hide normative objectives or distributional trade-offs inside an "optimal" result.
7. Use probability only where a variable, evidence base, and defensible distribution or model class exist. Do not turn ambiguity or deep uncertainty into precise probabilities merely because a decision is needed.
8. Prefer the simplest model that retains the mechanisms material to the decision. Add complexity only when it can change a decision, prediction, or safety conclusion.
9. State the model's expected failure regimes, validation plan, and triggers for revision. For high-consequence domains, flag the need for domain expertise, governance, and appropriate validation.
10. Ask focused clarifying questions when answers would materially change scope, stakes, authority, model class, or recommended action. Otherwise make assumptions explicit and proceed with a provisional model.

## Workflow

### 1. Frame the task

Identify whether the user needs explanation, prediction, intervention, optimization, control, diagnosis, monitoring, communication, or exploration.

Record:

- decision owner/audience and decision to support;
- objectives, success criteria, and non-goals;
- time horizon and spatial, organizational, or population scope;
- consequences of error, delay, and abstention.

### 2. Set boundary and ontology

Define what is inside and outside the system, its interfaces, its resolution/granularity, and the unit of analysis.

Specify only the concepts needed for the purpose:

- actors/entities and their identity criteria;
- resources, attributes, and units;
- relations, dependencies, events, processes, stocks, flows, and states;
- observable variables, latent variables, and proxies;
- controllable inputs, exogenous conditions, outputs, and outcomes.

Surface overloaded terms and propose operational definitions before reasoning from them.

### 3. Map structure

Identify applicable structure; omit irrelevant lenses rather than fabricating them.

- **Constraints and invariants:** physical, logical, accounting, legal, safety, capacity, or policy limits.
- **Causality:** candidate mechanisms, causal directions, confounders, mediators, colliders, and feasible interventions.
- **Dynamics:** state transitions, rates, delays, accumulation, feedback loops, thresholds, path dependence, and regime shifts.
- **Agency and strategy:** actors' information, actions, incentives, institutional rules, adaptation, gaming, and reflexivity.

### 4. Build an uncertainty register

Classify each material uncertainty by its treatment, not merely its subject matter.

| Class | Meaning | Appropriate treatment |
| --- | --- | --- |
| Deterministic/discrete structure | Rules, identities, constraints, or fixed-but-unknown inputs | Logic, verification, sensitivity bounds, optimization |
| Probabilistic inference | Repeatable variation with defensible variables, evidence, and distributions | Statistics, Bayesian inference, forecasting, calibration |
| Ambiguity | Multiple plausible distributions, priors, parameters, or structural models | Sensitivity analysis, ensembles, robust or imprecise methods |
| Deep uncertainty | No credible probability model due to novelty, missing observability, unstable regimes, or unknown futures | Scenarios, stress tests, reversible actions, monitoring, robust decisions |

Use *chaotic dynamics* only for the technical case of deterministic sensitivity to initial conditions; do not use it as a catch-all for ignorance.

### 5. Audit evidence and measurement

For each decision-relevant claim, variable, or parameter, record its source/provenance, date/context, definition/unit, transformations, and quality limitations. Mark it as observed, estimated, assumed, elicited, or unknown.

Check for sampling and selection bias, missingness, measurement error, proxy mismatch, data leakage, aggregation errors, latency, and limited external validity.

### 6. Compare model forms

Generate a small purpose-matched set before recommending one. Possible forms include:

- decision tables, rules, formal logic, constraint or accounting models;
- causal DAGs and structural causal models;
- optimization and control models;
- regression, Bayesian, time-series, Markov, or state-space models;
- stock-flow/system-dynamics models;
- network, game-theoretic, or agent-based models;
- Monte Carlo/discrete-event simulation;
- scenario ensembles and robust decision frameworks.

For every candidate, explain what it captures, the assumptions/evidence it needs, what it omits, and why it is or is not proportionate to the purpose.

### 7. Specify, validate, and use the model

For the selected minimal viable model, define inputs, outputs, rules/equations, parameters, initial conditions, interventions, implementation method, and traceability from assumptions to outputs.

Use applicable validation:

- dimensional, accounting, logic, and invariant checks;
- domain-expert face validity;
- calibration, fit, holdout, or historical checks;
- causal/mechanism and counterfactual checks;
- sensitivity and uncertainty propagation;
- extreme-case, adversarial, and out-of-distribution tests;
- robustness across assumptions, model forms, and scenarios.

Translate the result into options, trade-offs, thresholds, reversible next actions, monitoring indicators, and the evidence that would change the recommendation.

## Deliverable

Scale the depth to the context, but use this structure for a full analysis:

```md
## Decision and purpose
## Scope, boundary, and non-goals
## Ontology and variables
## Assumptions and constraints
## Causal, dynamic, and strategic structure
## Uncertainty register
## Evidence and measurement ledger
## Candidate model forms
## Recommended minimal viable model
## Validation and stress tests
## Decision analysis and monitoring
## Open questions and next evidence/actions
```

For a small or underspecified request, return an **initial frame**: the apparent purpose/system, material ambiguities, provisional assumptions, and the few questions whose answers would change the model.
