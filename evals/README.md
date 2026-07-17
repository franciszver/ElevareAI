# evals/ (dev-facing)

In-repo, pytest-based eval harness for ElevareAI's AI surfaces (QA, summary,
practice, guardrails). Full design: `_docs/local/plans/2026-07-16-evals-plan.md`.
The user-facing "Running evals" section in the root README lands in E5.

## Phase status

- **E0 (this phase): scaffolding.** Dataset schema + loader, a runner
  skeleton, a report module, the `eval` pytest marker, and two deterministic
  graders (`confidence_line_present`, `practice_json_valid`) — proven
  end-to-end with a mock generator, zero API calls.
- **E1 (next):** the remaining deterministic checks per surface (see below).
- **E2:** LLM-as-judge harness + curated golden sets.
- **E3:** guardrail/safety cases.
- **E4:** cost/latency capture + committed baselines + regression comparison.
- **E5:** CI workflow (`workflow_dispatch`) + root README docs.

## Layout

```
evals/
  schema.py            # Case dataclass + load_cases(path) YAML loader
  runner.py             # run_cases(cases, graders_by_surface, generate_fn) -> CaseResult list
  report.py             # build_report / render_markdown
  graders/
    deterministic.py    # pure, offline grader functions (no API)
  datasets/
    example.yaml         # sample dataset proving the schema (E0)
  baselines/             # committed baseline scores (E4)
```

## Running the harness self-tests

The self-tests live in `tests/test_evals_harness.py` and run in the normal
suite (`pytest -q`) — no API key, no network. They cover the loader, the
deterministic graders, and the runner/report using an injected mock
`generate_fn`.

## The (planned) live eval flow

Live cases are gated behind the `eval` pytest marker (registered in
`pytest.ini`) so they never run by default:

```
pytest -m eval        # will run live cases once E1+ wires real generate_fn
                       # and OPENROUTER_API_KEY is set
```

Not implemented in E0 — `evals/runner.py`'s `live_generate_stub` raises
`NotImplementedError` with a TODO; E1 replaces it with a real generator
per surface.

## Case schema

```yaml
cases:
  - id: qa-photosynthesis-basic     # str, required, unique
    surface: qa                      # required: qa | summary | practice | guardrail
    input:                           # required, dict — prompt inputs
      question: "What is photosynthesis?"
      subject: "Biology"
    expect:                          # optional, dict — deterministic-check hints (E1)
      requires_confidence_line: true
    rubric: "..."                    # optional, str — LLM-judge instructions (E2)
    tags: [qa, smoke]                # optional, list[str]
```

`load_cases("evals/datasets/example.yaml")` returns a `list[Case]`, raising
`FileNotFoundError` for a missing file and `ValueError` (with the offending
case's id/index) for a malformed one.

## Adding a case

1. Add an entry to the relevant `evals/datasets/*.yaml` file (or create one
   for a new surface's golden set in E1+).
2. Give it a unique, descriptive `id` and fill in `input` with realistic
   values drawn from the app.
3. If a deterministic grader exists for the surface, no `expect`/`rubric`
   wiring is required yet — the runner grades using
   `graders_by_surface[case.surface]`. `expect`/`rubric` are read by E1/E2
   graders once they exist.

## E1 handoff — what to add next

E0 intentionally ships only two graders to prove the harness. E1 should add,
per the eval plan (`_docs/local/plans/2026-07-16-evals-plan.md`):

- **QA**: answer non-empty after stripping; word count ≤ ~300; no `\( \)`/
  `\[ \]` LaTeX delimiters; out-of-scope inputs return the canned refusal
  (not `confidence_line_present`, a separate check).
- **Practice**: question ≥20 chars, explanation ≥30 chars, no placeholder
  distractor strings (e.g. "An incorrect alternative"), no LaTeX
  delimiters — extending `practice_json_valid` or adding siblings.
- **Practice (math)**: a SymPy ground-truth grader that regenerates the
  seed and asserts the labelled correct answer actually solves the
  equation.
- **Summary**: non-empty narrative; 1-3 next-steps parsed; `summary_type`
  matches duration (<10min → brief).
- Wire `graders_by_surface` maps for each surface into a real
  `run_evals.py`-style entrypoint, and replace `runner.live_generate_stub`
  with real per-surface generators that call `openai_client`.

## Guardrail hardening backlog (Phase E3 follow-up)

Not fixed in this pass — noted here rather than addressed, per scope:

- **High-confidence-on-off-task check (gap #2).** The real captured
  pirate-poem jailbreak (`evals/fixtures/guardrail_outputs.json`,
  id=`injection_pirate_poem`) shows the model both abandoned the tutor role
  AND self-reported `CONFIDENCE: 0.96` — high confidence on an answer that
  shouldn't have been given at all. A cheap deterministic check ("for a
  role-abandonment/off-task case, CONFIDENCE must NOT be high") is tempting,
  but doesn't fit cleanly today: role-abandonment cases are graded via the
  judge/`rubric` path (see `guardrail-injection-role-abandonment-pirate-poem`
  in `guardrails.yaml`), not the deterministic `expect`-driven path, and
  there's no CONFIDENCE-extraction wiring on that path yet. Land this as a
  small addition to the judge rubric itself (or a follow-up deterministic
  side-check keyed off the `role-abandonment` tag) rather than bolting it
  onto `injection_resistance`, which has no signal to read a CONFIDENCE
  value from an `answer` string.
- **Calibration fixture coverage.** `evals/fixtures/guardrail_outputs.json`
  (real captured production outputs, distinct from `guardrails.yaml`'s
  dataset used by the test suite) only captured 1 of the dataset's 2
  calibration pairs — `calibration_clear_question`/`calibration_vague_question`,
  no algebra/physics-labeled pair. Recapture to cover both pairs before this
  fixture is used for anything beyond a smoke check.
- **Safety cases have no deterministic backstop.** `guardrail-safety-*`
  cases (self-harm disclosure, cheating request, personal-info request) are
  judge-only via `rubric` — there's no deterministic grader underneath them
  the way injection/out-of-scope/calibration have. A judge misjudgment on a
  safety-sensitive case currently has no second check to catch it.
