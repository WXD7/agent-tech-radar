# Codex execution policy for Agent Tech Radar

## Objective

Maintain a reviewable, evidence-backed technology radar for AI agent development.

## Write boundaries

- Codex may create or update files in `proposals/`, `inbox/`, `experiments/`, `reports/`, `.radar/`, `knowledge/conversations/`, and `knowledge/nodes/`.
- `knowledge/conversations/` and `knowledge/nodes/` may only be written when the user explicitly imports or synchronizes a Codex conversation, or explicitly asks Codex to save a learning note.
- Codex must not directly change accepted files in `knowledge/claims/`, `knowledge/decisions/`, or `knowledge/reviews/` unless the user explicitly asks it to apply an approved review decision.
- The web review action counts as explicit human approval for the single proposal submitted by that form.
- Never delete review records or rewrite historical experiment outputs.
- A Codex conversation is provenance for how the user learned something; it is not primary evidence that an external technical claim is true.

## Evidence rules

- Prefer official repositories, documentation, release notes, package registries, standards, and papers.
- Search is for discovery. Once a candidate is known, switch to primary evidence.
- Keep official claims, source-code observations, experiment results, user outcomes, and AI inference visibly separate.
- Every material claim must reference evidence IDs and include a confidence score and update time.
- Confidence is an assessment, not a fact.
- If evidence conflicts, preserve both sides and mark the claim `contested`.

## Collection rules

- Do not build or operate a general web crawler.
- Use documented APIs, release feeds, package registries, RSS/Atom, and bounded on-demand retrieval.
- Compare version identifiers and content hashes before requesting deep analysis.
- A package version change is a fact, not proof that a technology decision should change.

## Experiment rules

- Save the hypothesis, dependencies, model identifier, inputs, random seed where applicable, metrics, raw logs, and result.
- Do not claim an experiment ran if credentials, dependencies, or source data were unavailable.
- Prefer the smallest experiment that can falsify a claim.

## Reporting

- Daily runs should report only material changes and pending review items.
- Weekly runs may add at most ten discovery candidates and should recommend at most three deep experiments.
- Decisions remain `watch`, `assess`, `trial`, `adopt`, or `hold` until a human approves a change.
