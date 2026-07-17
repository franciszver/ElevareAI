"""Eval case schema + YAML loader.

A `Case` describes a single eval example: which AI surface it targets, the
inputs to feed the generator, and (optionally) the expectations used to
grade the output. `expect` backs deterministic checks (E1); `rubric` backs
the future LLM-judge (E2). Neither is required in E0 since no graders
consume them yet.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

VALID_SURFACES = {"qa", "summary", "practice", "guardrail"}


@dataclass
class Case:
    id: str
    surface: str
    input: Dict[str, Any]
    expect: Optional[Dict[str, Any]] = None
    rubric: Optional[str] = None
    tags: List[str] = field(default_factory=list)


def _require_field(raw: Dict[str, Any], name: str, index: int) -> Any:
    if name not in raw or raw[name] in (None, ""):
        raise ValueError(
            f"Case at index {index} is missing required field '{name}': {raw!r}"
        )
    return raw[name]


def _validate_case_dict(raw: Any, index: int) -> Case:
    if not isinstance(raw, dict):
        raise ValueError(
            f"Case at index {index} must be a mapping, got {type(raw).__name__}: {raw!r}"
        )

    case_id = _require_field(raw, "id", index)
    surface = _require_field(raw, "surface", index)
    if surface not in VALID_SURFACES:
        raise ValueError(
            f"Case '{case_id}' has invalid surface '{surface}'; "
            f"must be one of {sorted(VALID_SURFACES)}"
        )

    input_dict = _require_field(raw, "input", index)
    if not isinstance(input_dict, dict):
        raise ValueError(
            f"Case '{case_id}' field 'input' must be a mapping, got {type(input_dict).__name__}"
        )

    expect = raw.get("expect")
    if expect is not None and not isinstance(expect, dict):
        raise ValueError(
            f"Case '{case_id}' field 'expect' must be a mapping if present"
        )

    rubric = raw.get("rubric")
    if rubric is not None and not isinstance(rubric, str):
        raise ValueError(f"Case '{case_id}' field 'rubric' must be a string if present")

    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        raise ValueError(f"Case '{case_id}' field 'tags' must be a list if present")

    return Case(
        id=case_id,
        surface=surface,
        input=input_dict,
        expect=expect,
        rubric=rubric,
        tags=tags,
    )


def load_cases(path: str) -> List[Case]:
    """Load and validate eval cases from a YAML file.

    The file must contain a top-level `cases:` list. Raises FileNotFoundError
    if the file doesn't exist, and ValueError with a clear message on any
    malformed case (missing required field, invalid surface, wrong type).
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Eval dataset not found: {path}")

    with file_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    raw_cases = data.get("cases")
    if raw_cases is None:
        raise ValueError(f"Eval dataset '{path}' has no top-level 'cases' list")
    if not isinstance(raw_cases, list):
        raise ValueError(f"Eval dataset '{path}' field 'cases' must be a list")

    return [_validate_case_dict(raw, i) for i, raw in enumerate(raw_cases)]
