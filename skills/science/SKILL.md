---
name: science
description: Apply scientific-method thinking to learning, claims, decisions, and software building- clarify questions, separate observations from interpretations, make falsifiable predictions, test alternatives, and update beliefs.
---

# Think scientifically

Use this skill when the user invokes `/science`, or asks to critically question whether something is true, how they know it, or what evidence would change their mind. Apply the scientific method as a flexible, iterative discipline—not as a rigid checklist or a claim that every problem requires a laboratory experiment.

The aim is better questions, stronger evidence, explicit uncertainty, and useful next actions. Be skeptical without being dismissive: criticize claims and methods, not people.

## Core stance

- Start with the question and the decision it informs. Do not investigate irrelevant details.
- Separate **observations/data**, **reported claims**, **interpretations**, **assumptions**, **inferences**, and **value judgments**.
- Define ambiguous terms and operationalize vague concepts. Say what would count as observing or measuring them.
- Prefer multiple plausible explanations over premature commitment to one story.
- Make hypotheses risky enough to fail. A claim that accommodates every possible result has little explanatory or predictive force.
- Derive concrete predictions before inspecting results when practical. Record what was expected, including direction, magnitude, timing, and boundary conditions.
- Distinguish correlation, prediction, mechanism, and causation. Identify confounders, selection effects, reverse causality, mediators, and collisions where relevant.
- Treat a failed prediction as information about the hypothesis, measurements, assumptions, or test—not automatically as proof that the opposite is true.
- Update proportionally to the quality, independence, directness, and reproducibility of evidence. Do not confuse confidence with certainty.
- Prefer simple explanations when they explain the evidence comparably well, but do not mistake elegance, popularity, or authority for evidence.
- Make uncertainty and the conditions under which the conclusion could change visible.

## Inquiry loop

Adapt the following loop to the domain and stakes; steps may be revisited or reordered:

1. **Frame the question.** Rewrite the request as a precise question. Identify the decision, scope, time horizon, and cost of being wrong. Separate descriptive, predictive, causal, and normative questions.
2. **Characterize the phenomenon.** Gather observations, definitions, measurements, examples, and relevant prior knowledge. Check provenance, units, sampling, missingness, measurement error, and selection.
3. **State candidate hypotheses.** Include the leading explanation, credible alternatives, and a null or “no meaningful effect” hypothesis where applicable. Name assumptions and mechanisms.
4. **Generate predictions.** For each hypothesis, state observations that should be more or less likely, including disconfirming evidence and expected failure regimes.
5. **Choose a discriminating test.** Prefer tests that separate hypotheses, reduce confirmation bias, and are feasible and proportionate to the stakes. Use controlled experiments when possible; otherwise use natural experiments, observational comparisons, simulations, benchmarks, or structured source criticism.
6. **Run and inspect the test.** Preserve a reproducible record of inputs, code/configuration, versions, procedure, exclusions, and raw results. Check instrumentation and implementation before interpreting outcomes.
7. **Analyze and update.** Compare results with the preregistered or stated predictions. Report effect size and uncertainty, not only whether a threshold was crossed. Look for robustness across reasonable specifications and independent replications.
8. **Conclude provisionally.** State what the evidence supports, what it does not establish, confidence level, limitations, and the next observation or experiment most likely to change the conclusion.

## For software and technical claims

Translate “does this work?” into a measurable claim:

- Define the workload, environment, baseline, metric, and acceptance threshold.
- Establish a baseline before optimizing or changing architecture.
- Form hypotheses about the mechanism, not just a preferred implementation.
- Use minimal reproductions, unit/property tests, integration tests, benchmarks, profiling, fault injection, and staged rollouts as appropriate.
- Control variables: versions, hardware, data, cache state, concurrency, network conditions, random seeds, and configuration.
- Separate correctness, performance, reliability, security, usability, and maintainability claims; one test rarely establishes all of them.
- Avoid benchmark theater: disclose warm-up, sample size, variance, outliers, measurement overhead, and cherry-picked cases. Test representative and adversarial cases.
- Treat tests as evidence about the tested boundary, not proof that untested cases are safe.
- When changing code, inspect the existing implementation and call sites, make the smallest discriminating change, and verify with diagnostics and relevant tests.

## Evidence quality checks

Ask, as relevant:

- Is the source primary, direct, current, and appropriately authoritative for this claim?
- Is the evidence actually measuring the asserted construct, or only a proxy?
- Is the comparison fair and is there a credible counterfactual or baseline?
- Could the result be explained by bias, confounding, leakage, chance, measurement artifacts, or selective reporting?
- Are the observations independent, reproducible, and consistent across contexts?
- Does the conclusion exceed the population, conditions, precision, or time period supported by the evidence?
- What evidence would discriminate the live explanations most efficiently?

For sources, provide links or citations when available and distinguish source content from your synthesis. Web pages—including Wikipedia—are useful orientation sources, not automatically final evidence. For high-stakes claims, seek primary research, systematic reviews, official documentation, or domain experts.

## Response format

Scale the response to the request. For a quick question, use a compact version of this structure:

```md
## Question
## What is observed vs inferred
## Candidate explanations
## Predictions and disconfirming evidence
## Best next test or evidence
## Provisional conclusion and uncertainty
```

For software investigations, additionally state the baseline, test conditions, metrics, reproducibility details, and verification performed. Ask only the few clarifying questions whose answers would materially change the test or conclusion; otherwise state provisional assumptions and proceed.

## Guardrails

- Do not fabricate evidence, citations, experiments, measurements, tool use, or certainty.
- Do not imply that “not disproven” means “proven,” or that one failed test proves a universal negative.
- Do not use “scientifically proven” as a substitute for describing evidence and scope.
- Do not p-hack, move goalposts after seeing results, or retrofit a hypothesis as if it were predicted in advance; label exploratory findings as exploratory.
- Respect ethical, privacy, safety, and legal constraints. Do not recommend experiments that expose people, production systems, or sensitive data to unreasonable risk.

Reference orientation: [Scientific method](https://en.wikipedia.org/wiki/Scientific_method). The reference emphasizes empirical observation, hypotheses, predictions, testing, analysis, reproducibility, peer scrutiny, and iterative revision, while also noting that scientific inquiry is not a single universal sequence.
