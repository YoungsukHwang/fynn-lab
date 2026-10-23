"""Setup fingerprints: what besides the skills makes every case rerun."""

import ast
from pathlib import Path

import pytest

from evals.setup import BACKEND, PARTS, code_hash, setup_changes, setup_fingerprint
from fynn import config

MODELS = {"router": "r", "agent": "a", "judge": "j"}


def _module(tmp_path: Path, text: str) -> str:
    (tmp_path / "m.py").write_text(text, encoding="utf-8")
    return code_hash(("m.py",), root=tmp_path)


def test_code_hash_ignores_comments_formatting_and_docstrings(tmp_path: Path) -> None:
    base = _module(tmp_path, 'def f():\n    return "Choose at most 3"\n')
    assert _module(tmp_path, '"""Module."""\n\n# a comment\ndef f( ):\n    """Doc."""\n    return "Choose at most 3"  # why\n') == base
    assert _module(tmp_path, 'def f():\n    return "Choose at most 4"\n') != base


def test_code_hash_is_pinned(tmp_path: Path) -> None:
    # A literal, so a Python release that dumps syntax trees differently fails here instead of
    # silently changing every fingerprint (and rerunning every case).
    assert _module(tmp_path, 'def f(x: int = 1) -> str:\n    return f"Choose at most {x}"\n') == "50c5bf567083"


def test_settings_keep_the_order_of_domains(monkeypatch: pytest.MonkeyPatch) -> None:
    before = setup_fingerprint()["settings"]
    monkeypatch.setattr(config, "DOMAINS", dict(reversed(list(config.DOMAINS.items()))))
    assert setup_fingerprint()["settings"] != before


def test_setup_fingerprint_covers_bot_code_judge_code_and_settings() -> None:
    fingerprint = setup_fingerprint()
    assert set(fingerprint) == {*PARTS, "settings"}
    assert fingerprint == setup_fingerprint()  # stable between calls


def test_every_module_that_builds_a_prompt_is_hashed() -> None:
    # The modules that define the prompt builders, and every backend module that imports one of them,
    # must sit in a fingerprinted part, or an edit to a prompt would not rerun anything.
    hashed = {p for paths in PARTS.values() for p in paths}
    builders = {"render_profile", "render_skill", "render_transcript", "before_system_prompt", "after_system_prompt"}
    for path in [*BACKEND.glob("fynn/*.py"), *BACKEND.glob("evals/*.py")]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        imported = {a.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for a in node.names}
        uses_builder = bool(defined & builders) or bool(imported & builders)
        if uses_builder and path.name not in ("run.py", "report.py"):  # they only pass replies through
            assert str(path.relative_to(BACKEND)) in hashed, path


def test_setup_changes_names_what_differs() -> None:
    fingerprint = {"bot_code": "b", "judge_code": "j", "settings": "s"}
    same = {"models": MODELS, "setup_fingerprint": fingerprint}
    assert setup_changes(same, MODELS, fingerprint) == []

    moved = {**same, "models": {**MODELS, "agent": "old"}, "setup_fingerprint": {**fingerprint, "judge_code": "x"}}
    assert setup_changes(moved, MODELS, fingerprint) == ["the models (agent old to a)", "the judge code"]


def test_a_baseline_without_a_setup_fingerprint_is_checked_for_models_only() -> None:
    fingerprint = {"bot_code": "b", "judge_code": "j", "settings": "s"}
    assert setup_changes({"models": MODELS}, MODELS, fingerprint) == []
    assert setup_changes({"models": {**MODELS, "router": "old"}}, MODELS, fingerprint) == ["the models (router old to r)"]
