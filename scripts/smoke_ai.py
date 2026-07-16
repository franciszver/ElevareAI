"""
Manual live smoke test for OpenRouter AI integration.

NOT collected by pytest (scripts/ is outside testpaths). Run manually:
    .venv/Scripts/python.exe scripts/smoke_ai.py [--model MODEL_ID]

Exercises all 4 prompt templates against the real OpenRouter API and
prints PASS/FAIL per check, exiting nonzero if any check fails.
"""

import argparse
import json
import re
import sys
import time

# Windows console default encoding (cp1252) can't render all model output
# (e.g. non-breaking hyphens, minus signs). Force UTF-8 with a safe fallback.
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

from src.services.ai.openai_client import openai_client
from src.services.ai.prompts import PromptTemplates

results = []  # list of (name, "PASS"/"WARN"/"FAIL", detail)


def record(name, status, detail=""):
    results.append((name, status, detail))
    print(f"[{status}] {name}: {detail}")


def show_metadata(meta):
    usage = meta.get("usage", {})
    print(f"    model={meta.get('model')} total_tokens={usage.get('total_tokens')}")


def excerpt(text, n=150):
    text = (text or "").replace("\n", " ")
    return text[:n]


def check_qa():
    try:
        prompt = PromptTemplates.qa_answer_prompt(
            query="What is the Pythagorean theorem?",
            context={"subject": "Math"},
        )
        meta = openai_client.chat_completion_with_metadata(prompt)
        answer = meta["content"] or ""
        show_metadata(meta)
        print(f"    excerpt: {excerpt(answer)!r}")
        if answer and len(answer.strip()) >= 20:
            record("QA answer", "PASS", f"len={len(answer)}")
        else:
            record("QA answer", "FAIL", f"response too short: {answer!r}")
    except Exception as e:
        record("QA answer", "FAIL", f"{type(e).__name__}: {e}")


def check_confidence():
    try:
        prompt = PromptTemplates.confidence_assessment_prompt(
            query="What is the Pythagorean theorem?",
            answer="a^2 + b^2 = c^2 for right triangles.",
        )
        meta = openai_client.chat_completion_with_metadata(
            prompt, temperature=0.3, max_tokens=400
        )
        raw = meta["content"] or ""
        show_metadata(meta)
        print(f"    finish_reason={meta.get('finish_reason')}")
        print(f"    excerpt: {excerpt(raw)!r}")
        match = re.search(r"0?\.\d+|1\.0|0", raw.strip())
        if match:
            score = float(match.group())
            if 0.0 <= score <= 1.0:
                record("Confidence assessment", "PASS", f"score={score}")
            else:
                record("Confidence assessment", "FAIL", f"score out of range: {score}")
        else:
            record("Confidence assessment", "FAIL", f"no number found in: {raw!r}")
    except Exception as e:
        record("Confidence assessment", "FAIL", f"{type(e).__name__}: {e}")


def check_summary():
    try:
        prompt = PromptTemplates.session_summary_prompt(
            transcript="Student worked through solving quadratic equations by factoring.",
            session_duration_minutes=30,
            subject="Math",
            topics_covered=["quadratic equations", "factoring"],
            student_name="Alex",
        )
        meta = openai_client.chat_completion_with_metadata(prompt)
        summary = meta["content"] or ""
        show_metadata(meta)
        print(f"    excerpt: {excerpt(summary)!r}")
        if summary and len(summary.strip()) >= 20:
            has_next_steps = bool(re.search(r"next step", summary, re.IGNORECASE))
            record(
                "Session summary",
                "PASS",
                f"len={len(summary)} next_steps_marker={has_next_steps}",
            )
        else:
            record("Session summary", "FAIL", f"response too short: {summary!r}")
    except Exception as e:
        record("Session summary", "FAIL", f"{type(e).__name__}: {e}")


def check_practice_json(n=3):
    successes = 0
    for i in range(1, n + 1):
        try:
            prompt = PromptTemplates.practice_generation_prompt(
                subject="Math",
                topic="quadratic equations",
                difficulty_level=3,
            )
            meta = openai_client.chat_completion_with_metadata(
                prompt, response_format={"type": "json_object"}
            )
            ai_response = meta["content"] or ""
            show_metadata(meta)
            print(f"    [{i}/{n}] excerpt: {excerpt(ai_response)!r}")

            json_match = re.search(
                r'\{[^{}]*(?:"question_text"|"choices")[^{}]*\}', ai_response, re.DOTALL
            )
            if not json_match:
                print(f"    [{i}/{n}] no JSON object found")
                continue
            try:
                item = json.loads(json_match.group())
            except json.JSONDecodeError as e:
                print(f"    [{i}/{n}] json.JSONDecodeError: {e}")
                continue

            required_keys = {"question_text", "choices", "correct_answer"}
            if not required_keys.issubset(item.keys()):
                print(f"    [{i}/{n}] missing keys: {required_keys - item.keys()}")
                continue
            if not isinstance(item["choices"], list) or len(item["choices"]) != 4:
                print(f"    [{i}/{n}] choices not a 4-item list: {item.get('choices')}")
                continue

            print(f"    [{i}/{n}] parsed OK with 4 choices")
            successes += 1
        except Exception as e:
            print(f"    [{i}/{n}] {type(e).__name__}: {e}")

        if i < n:
            time.sleep(3)

    if successes == n:
        record("Practice generation JSON", "PASS", f"{successes}/{n}")
    elif successes == n - 1:
        record("Practice generation JSON", "WARN", f"{successes}/{n}")
    else:
        record("Practice generation JSON", "FAIL", f"{successes}/{n}")


def main():
    parser = argparse.ArgumentParser(
        description="Live smoke test for OpenRouter AI integration"
    )
    parser.add_argument("--model", help="Override the OpenRouter model for this run")
    args = parser.parse_args()

    if args.model:
        openai_client.model = args.model

    print(f"Using model: {openai_client.model}\n")

    start = time.time()

    print("--- Check 1: QA answer ---")
    check_qa()
    time.sleep(3)

    print("\n--- Check 2: Confidence assessment ---")
    check_confidence()
    time.sleep(3)

    print("\n--- Check 3: Session summary ---")
    check_summary()
    time.sleep(3)

    print("\n--- Check 4: Practice generation JSON (3 calls) ---")
    check_practice_json(n=3)

    elapsed = time.time() - start

    print("\n=== Summary ===")
    for name, status, detail in results:
        print(f"  [{status}] {name}: {detail}")
    print(f"Elapsed: {elapsed:.1f}s")

    if any(status == "FAIL" for _, status, _ in results):
        print("\nRESULT: FAILURE")
        sys.exit(1)
    print("\nRESULT: SUCCESS")
    sys.exit(0)


if __name__ == "__main__":
    main()
