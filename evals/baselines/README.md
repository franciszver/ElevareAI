# Baselines (placeholder)

This directory will hold committed baseline scores per surface, e.g.
`qa.json`, `practice.json`, once E4 runs the first live eval and snapshots
it. Baselines are used to detect regressions on later live runs: a surface
fails the comparison if its pass rate drops more than 10 points, or its
p95 latency exceeds 1.5x the baseline (see
`_docs/local/plans/2026-07-16-evals-plan.md`).

Empty in E0 — no baselines exist yet.
