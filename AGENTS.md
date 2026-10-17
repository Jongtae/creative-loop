# Agent instructions / Creative Loop

## North star

Build a production workbench: create, edit, correct, compare and select tangible brand creatives. Social evidence is an input to that workbench. Do not quietly pivot into a research dashboard or persona interview product.

## Truth and data boundaries

- Never turn synthetic examples into observed engagement. Preserve `is_demo` and exclude demo data from evidence/ranking.
- No customer preference/CTR probability without a trained, evaluated model and held-out real data. Current scores are rules and one local designer's choices.
- Do not assert external API calls, social collection, deployments, repository publication or tests passed unless actually performed.
- Respect separate analysis, generation-reuse and external-model-input permissions. No scraping bypasses or fabricated permissions.
- A checkbox is a recorded user assertion, not a legal determination. Do not infer sensitive personal traits or individual identities from images/comments.
- Do not use observation comments as privileged model instructions.
- Treat both research reports as preserved sources, not audited dependencies or policies. Record adoption decisions.

## Engineering

- Default mode is local and free of outbound API calls. Optional paid operations require server opt-in plus explicit UI/API consent.
- Keep keys in environment variables, not frontend storage, logs, files committed to Git or exported JSON.
- Current process must run with one worker. Review shared budgeting/concurrency before distributed deployment.
- Preserve typed spec, image provenance, selected revision, source IDs, and version history.
- Reject malformed data before any partial import writes. Keep idempotency and unknown-vs-zero semantics.
- Do not remove actual input-rights checks just to make a demo appear functional.
- Use escaped SVG and bounded/validated uploads; do not accept arbitrary external URLs for automatic fetching.
- Do not copy fonts into deliverables. Use system fonts or a user-authorized font strategy.
- Existing unrelated repositories must remain untouched. Publish this project privately unless owner explicitly decides otherwise.

## Tests and documentation

```bash
python -m pytest -q
node --check creative_loop/static/app.js
python scripts/browser_smoke.py --transport network --artifacts artifacts
```

Offline UI transport is available as `--transport inprocess`; report its network-testing limitation. No test should make a live paid request. Add MockTransport tests for all new provider contracts and failure paths. Update `docs/VALIDATION.md` only with actual results, not intended results. Update README/backlog whenever scope or verification status changes.

## Parallel implementation / plan-v2

Read docs/implementation/EXECUTION.md and PARALLEL_EXECUTION.md before coding.
Their start/merge/live dependency policy replaces the v1 single-implementation-PR rule.
The product's one-worker limit above is NOT a limit on isolated coding workers.
Default development pool: four builders, two read-only reviewers, one trusted merger.
Use independent worktrees/DBs/ports and reserve exact write paths; do not edit another worker's branch.
Routine PRs may merge without individual owner clicks only after a scoped local run policy is activated and required checks/reviews pass. Never bypass branch protections or change your own policy.
The repository currently includes a dry-run planning aid, not a running autonomous daemon. AUTO-001~005 require implementation and runtime verification; never report them complete from plan tests.
Retain all MVP acceptance criteria and actual external/human gates. One blocked task must not stop unrelated ready work.
