# ElevareAI — Architecture

*Lift your learning, gently.*

## 1. What ElevareAI Is

ElevareAI is an AI-powered study-companion platform that helps students learn between tutoring sessions. Students get adaptive practice problems, conversational Q&A with an AI tutor, plain-language session summaries, confidence-scored answers, progress tracking, and goal-setting. The product supports three roles — student, tutor, and parent — each with a distinct view into a student's learning journey: students practice and ask questions, tutors review session history and assign practice, and parents track progress and goals from the sidelines.

The backend exposes a REST API (FastAPI) with routers for authentication, Q&A, practice, session summaries, progress, goals, nudges, messaging, dashboards, analytics, integrations, and background jobs. The frontend is a single-page React application that consumes this API.

## 2. Architecture & Tech Stack

At a glance:

| Layer | Technology |
|---|---|
| Backend framework | FastAPI + uvicorn (ASGI) |
| ORM / database | SQLAlchemy 2.x over PostgreSQL |
| Config | pydantic-settings (env-var driven, `.env` locally) |
| AI provider | OpenRouter, model `openai/gpt-oss-20b:free`, via the `openai` Python SDK pointed at OpenRouter's base URL |
| Math generation | SymPy (deterministic, no LLM) |
| Auth | Self-hosted JWT — bcrypt (passlib) + HS256 (python-jose) |
| Email | Disabled (log-only no-op) |
| Frontend | React 18 + Vite SPA |
| Frontend data/state | React Query, React Router, react-markdown, recharts, axios |
| Hosting | Render (free tier), deployed via a `render.yaml` blueprint |
| CI | GitHub Actions (tests, lint/format, security scan) |

**Backend.** The FastAPI app (`src/api/main.py`) wires up CORS, structured error handlers, request-logging and metrics middleware, and fourteen routers under `/api/v1`. On startup it verifies the database connection and fails fast if `JWT_SECRET` is not configured — there is no silent insecure fallback. Settings (`src/config/settings.py`) are loaded from environment variables via `pydantic-settings`, covering database connection, OpenRouter credentials/model/timeout, JWT, CORS, rate limits, and feature flags such as `enable_ai_practice_generation`.

**AI integration.** All five AI-touching surfaces flow through a single `OpenAIClient` wrapper (`src/services/ai/openai_client.py`) constructed from `settings.openrouter_*` fields — API key, model, temperature, max tokens, base URL, and a 60-second request timeout. Because it uses the OpenAI SDK's `base_url` parameter rather than a provider-specific SDK, the app is provider-neutral: swapping models or providers is a config change, not a code change. The five surfaces are:

1. **QA answering** — student questions are answered with an educational, encouraging tone, with edge-case handling for ambiguous, multi-part, and out-of-scope queries.
2. **Confidence scoring** — merged into the QA call itself. The prompt asks the model to end its answer with a trailing `CONFIDENCE: 0.NN` line, so one LLM call produces both the answer and its self-assessed confidence (the confidence result also factors in context availability, answer length, and expressed uncertainty).
3. **Session summarization** — turns a tutoring-session transcript into a warm narrative summary plus 2–3 actionable next steps.
4. **Practice-question generation (non-math)** — produces multiple-choice questions as JSON via the model, with a validation layer that checks structure.
5. **Practice quality-check/improvement** — a follow-up pass that reviews and improves generated non-math practice items.

Math practice is the exception: it is generated **deterministically with SymPy**, not the LLM, so answers are correct by construction and verifiable rather than merely plausible.

**Auth.** Authentication is entirely self-hosted: passwords are hashed with bcrypt via `passlib`, and sessions are HS256 JWTs signed via `python-jose`. There is no external identity provider. The app refuses to start if `JWT_SECRET` is unset.

**Email.** Outbound email is a log-only no-op — no email actually leaves the system.

**Frontend.** The frontend (`examples/frontend-starter/`) is a React 18 + Vite SPA using React Query for server-state, React Router for navigation, react-markdown for rendering AI responses, recharts for progress visualizations, and axios for HTTP.

**Hosting.** The app is deployed on Render's free tier using a `render.yaml` Blueprint (infrastructure-as-code) that provisions three resources: a free Postgres database (`elevareai-db`), the FastAPI backend as a Python web service (`elevareai-api`), and the React frontend as a static site (`elevareai-frontend`). The database is wired to the backend via `DATABASE_URL` (Render's `connectionString` property), which the app normalizes from `postgres://` to `postgresql://` for SQLAlchemy 2.x. Two secrets — `OPENROUTER_API_KEY` and `DEMO_PASSWORD` — must be entered manually in the Render dashboard after the first deploy; `JWT_SECRET` is auto-generated by Render; CORS is controlled via `ALLOWED_ORIGINS`. Free-tier caveats are documented directly in `render.yaml`: web services spin down after ~15 minutes of inactivity (cold starts up to ~1 minute), and free Postgres databases are deleted 30 days after creation.

**Cost.** Running cost is effectively $0/month. A one-time $10 OpenRouter credit raises the free-tier request cap to roughly 1,000 requests/day, comfortably covering normal usage.

## 3. Domain Logic & Data Model

**Adaptive practice (Elo rating).** Each student has a per-subject Elo rating (`StudentRating`, default 1000, clamped to 400–2000) that drives practice difficulty. `AdaptivePracticeService` (`src/services/practice/adaptive.py`) updates it after every completed item using the standard Elo formula — `expected_score = 1 / (1 + 10^((question_rating - student_rating)/400))`, `new_rating = current + K * (performance - expected)` with `K=32` — where `performance_score` blends accuracy (70%), speed (20%), and hints used (10%). The rating maps onto a 1–10 difficulty scale, and practice-bank items are selected from within a ±1 difficulty band of the student's current level.

**Confidence scoring, in detail.** Beyond the single-call LLM self-assessment described in §2, `calculate_confidence()` (`src/services/ai/confidence.py`) is a weighted blend: LLM self-assessment 40%, conversation-context relevance 30%, domain-expertise/uncertainty-language check 20%, and answer-length/completeness 10%. A `QueryAnalyzer` (`src/services/ai/query_analyzer.py`) flags ambiguous, multi-part, and out-of-scope queries ahead of the LLM call; out-of-scope queries are forced to zero confidence, and ambiguous ones have their score halved.

**Conversation history.** `ConversationHistory` (`src/services/qa/conversation_history.py`) retrieves a student's recent Q&A interactions (last 10 within a 24-hour window) to give the QA prompt context and to detect follow-up questions via keyword overlap and phrase heuristics ("what about", "tell me more", etc.).

**Nudges.** `NudgeEngine` (`src/services/nudges/engine.py`) evaluates three trigger types — inactivity (signed up ≥7 days ago with fewer than 3 sessions completed), goal completion, and login — and suppresses new nudges while an existing one is unopened or the daily frequency cap (default 1/day) has been hit. Messages are personalized by `NudgePersonalization` (`src/services/nudges/personalization.py`) using 30-day activity stats: preferred subjects, learning pace, engagement level, and time-of-day preference.

**Tutor overrides.** An `Override` model (`src/models/override.py`) records every time a tutor overrides an AI-generated summary, practice assignment, or QA answer, storing both the original and new content (JSONB) plus a reason — giving tutors a human-in-the-loop check on AI output with a full audit trail.

**Data model conventions.** All tables use UUID primary keys. Several use PostgreSQL `JSONB` for flexible fields (e.g. `users.profile`) and `ARRAY(String)` columns for tag-like data (`goal_tags`, `topic_tags`, `next_steps`, `subjects_covered`).

**QA daily question cap.** Within a goal, a student is capped at 20 QA questions per day (`src/api/handlers/qa.py`); exceeding it returns HTTP 429 pointing the student to their tutor for further help. (The generic `rate_limit_per_minute`/`rate_limit_per_hour` settings in `src/config/settings.py` are defined but not currently wired into any enforcement middleware.)

## 4. Key Architectural Decisions

The current design reflects a deliberate migration away from a broken, AWS-coupled state toward a self-hosted, free-tier-friendly stack:

- **De-AWS'd entirely.** Access to the original AWS account/API credentials was lost, so Cognito-based auth, SES-based email, and the AWS-hosted deployment were all replaced: self-hosted JWT auth, a log-only email no-op, and Render hosting. This removed the project's dependency on any AWS account existing at all.
- **Provider-neutral AI via OpenRouter.** Using the OpenAI SDK's `base_url` parameter to point at OpenRouter (rather than a bespoke client) means the model or provider can be changed by editing a setting, not by rewriting integration code.
- **Single-call QA + confidence.** Confidence scoring was folded into the same request as the answer (a trailing `CONFIDENCE: 0.NN` line) instead of a second, separate LLM call — halving API usage against the free-tier request cap for the QA surface.
- **Concise answers, generous timeouts, non-blocking calls.** Prompts explicitly ask for concise (~250-word) plain-text answers; the OpenRouter client has a 60-second timeout; and blocking LLM calls are offloaded off the async event loop (`run_in_threadpool`) in the QA, practice, and summarizer code paths, keeping the API responsive under concurrent load and avoiding upstream proxy timeouts.
- **Deterministic math generation.** Math practice items are generated with SymPy rather than the LLM — correct-by-construction, free, and independently verifiable, with no risk of a hallucinated wrong answer being presented as correct.
- **No credentials in the repo.** All secrets are supplied via `.env` locally or the Render dashboard in production; nothing sensitive is committed.
- **Idempotent demo-seed script.** A seed script using deterministic UUIDs can turn an empty database into a fully demo-ready state in one command. This directly mitigates Render's free-tier Postgres 30-day deletion — there is a documented runbook for recreating and reseeding the database when it expires.

## 5. Testing Approach

The backend has a 203-test pytest suite that runs green with **no database, no `.env`, no cloud credentials, and no network access**. This is achieved by pointing SQLAlchemy at an in-memory SQLite database for the test session, monkeypatching the app's startup database-connectivity check so the FastAPI lifespan doesn't attempt a real Postgres connection, and mocking the AI client via a `mock_ai` fixture that returns deterministic canned responses for confidence, summarization, practice generation, and Q&A. `pytest.ini` restricts collection to the `tests/` directory. Development follows a test-driven rhythm: fixes and changes are made red-to-green, with the failing test written first.

Static quality is enforced with pinned tool versions kept identical between local development and CI: `black`, `isort`, and `flake8` for the backend; `eslint` and a `vite build` for the frontend.

Beyond the unit-test suite, two live-verification tiers exist for catching what mocks can't:

- **`scripts/smoke_ai.py`** — a real-API smoke script that exercises every prompt template against the live OpenRouter endpoint.
- **Browser-driven end-to-end walkthroughs** — manual (Chrome DevTools-assisted) exercising of the full stack, frontend through backend through live AI, for changes that need to be seen working, not just asserted.

CI (`.github/workflows/ci.yml`) runs three jobs on every push/PR to `main`/`develop`: **Run Tests** (pytest against a real Postgres service container, with coverage uploaded to Codecov), **Lint and Format Check** (black/isort/flake8, plus a non-blocking mypy pass), and **Security Scan** (`safety check` against `requirements.txt`). Deployment is not part of this CI pipeline — Render's own Git integration handles it directly from the `main` branch; the legacy AWS ECR/ECS deploy workflow has been removed.

Every non-trivial change is also expected to pass pre-merge quality gates: automated simplify, security-review, and code-review passes with findings resolved before merge, plus a pre-push secret scan.

## 6. Evals (Planned)

An in-repo, pytest-based eval harness for the five AI surfaces is planned but not yet implemented (see `_docs/local/plans/2026-07-16-evals-plan.md`). It targets four goals: a regression safety net for prompt/model changes, guardrails/safety coverage, absolute quality scoring, and cost/latency tracking.

Grading is hybrid:

- **Deterministic checks** (free, offline-capable, run every time) — valid JSON with exactly 4 choices for practice items, no placeholder distractor text, plain-text output with no stray LaTeX delimiters, a present and parseable `CONFIDENCE: 0.NN` line on QA answers, and SymPy-verified correctness for generated math answers.
- **LLM-as-judge** (curated golden sets of ~10–15 cases per surface, costs live API calls) — scores open-ended quality such as QA correctness/pedagogy, summary faithfulness to the transcript, and practice-question plausibility. The judge deliberately uses a **different** free model (`google/gemma-4-31b-it:free`) than the generator (`openai/gpt-oss-20b:free`) to avoid self-judging bias.

Golden datasets live as YAML files, bootstrapped from existing seed data and hand-written edge cases. Guardrail cases cover out-of-scope refusal, prompt-injection resistance, confidence calibration (harder questions should score lower confidence than clear ones), and a light safety smoke set. Cost and latency (tokens, wall-clock time, truncation via `finish_reason`) are captured for every live case and aggregated per surface.

Evals run on-demand (`pytest -m eval`) and via a manually-triggered (`workflow_dispatch`) CI job — deliberately **not** on every PR, to stay within the free-tier request budget and avoid flaky red builds from model variance. Regression detection compares a live run against committed baselines and fails if a surface's pass rate drops more than 10 points or its p95 latency exceeds 1.5x the baseline. The work is scoped into six phases (E0 scaffolding through E5 CI + docs) and has not yet started implementation.

---

*ElevareAI is deployed and running on Render.*
