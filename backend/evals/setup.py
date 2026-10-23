"""Fingerprints of what shapes a run besides the skills, so a baseline can tell when every case must rerun.

The skills have their own fingerprint (fynn.skills). This covers the rest:

| Part       | What is hashed                                                                  |
|------------|---------------------------------------------------------------------------------|
| bot_code   | fynn/prompts.py, routers.py, bots.py, llm.py, personas.py (prompts and calls)   |
| judge_code | evals/judge.py, checks.py (how a reply is graded)                               |
| settings   | the config values those modules read during an eval run, and the regex flags    |

Code is hashed from its syntax tree without docstrings, so comments, formatting and docstrings
do not count as a change; the tree is dumped the same way on every Python version from 3.12 on.
The models are compared separately, from the results' `models`. The case files are not covered:
reports compare the facts the judge graded instead.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from evals.cases import REGEX_FLAGS
from fynn import config

BACKEND = Path(__file__).resolve().parents[1]
PARTS: dict[str, tuple[str, ...]] = {
    "bot_code": ("fynn/prompts.py", "fynn/routers.py", "fynn/bots.py", "fynn/llm.py", "fynn/personas.py"),
    "judge_code": ("evals/judge.py", "evals/checks.py"),
}
# Read by the bots during an eval run. The skill cap is recorded on its own (skill_cap), and the carry
# limit is left out because eval cases are single-turn.
SETTINGS = (
    "ROUTER_EFFORT",
    "AGENT_EFFORT",
    "ROUTER_MAX_TOKENS",
    "AGENT_MAX_TOKENS",
    "ROUTER_CONTEXT_MESSAGES",
    "DOMAINS",
)
# Python 3.13 stopped printing empty fields in ast.dump; asking for them keeps hashes equal across versions.
DUMP_OPTIONS: dict[str, Any] = {"show_empty": True} if sys.version_info >= (3, 13) else {}
PART_LABELS = {"bot_code": "the bot code", "judge_code": "the judge code", "settings": "the bot settings"}


def _short(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    node.body = body[1:] or [ast.Pass()]
    return tree


def code_hash(paths: tuple[str, ...], root: Path = BACKEND) -> str:
    """One hash over the syntax trees of `paths` (relative to backend/), docstrings removed."""
    trees = [_strip_docstrings(ast.parse((root / p).read_text(encoding="utf-8"))) for p in paths]
    dumps = [ast.dump(tree, **DUMP_OPTIONS) for tree in trees]
    return _short("\n".join(dumps))


def setup_fingerprint() -> dict[str, str]:
    # A list, not sorted keys: the order of DOMAINS is the order of the Before router's catalog.
    settings = [[name, getattr(config, name)] for name in SETTINGS] + [["REGEX_FLAGS", int(REGEX_FLAGS)]]
    return {
        **{part: code_hash(paths) for part, paths in PARTS.items()},
        "settings": _short(json.dumps(settings, default=str)),
    }


def setup_changes(baseline: Mapping[str, Any], models: Mapping[str, str], fingerprint: Mapping[str, str]) -> list[str]:
    """What differs between a baseline results file and this run, as phrases for a selection rule.
    A baseline written before setup fingerprints were recorded can only be checked for models."""
    changes: list[str] = []
    base_models = baseline.get("models")
    if isinstance(base_models, Mapping) and dict(base_models) != dict(models):
        moved = [f"{role} {base_models.get(role)} to {model}" for role, model in models.items() if base_models.get(role) != model]
        changes.append(f"the models ({', '.join(moved)})")
    base_fp = baseline.get("setup_fingerprint")
    if isinstance(base_fp, Mapping):
        changes += [PART_LABELS.get(part, part) for part, value in fingerprint.items() if base_fp.get(part) != value]
    return changes
