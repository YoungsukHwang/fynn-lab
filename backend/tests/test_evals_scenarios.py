"""Scenario loading and overlay, on temporary files and on the real scenarios/."""

from pathlib import Path

import pytest
import yaml

from evals.scenarios import SCENARIOS_DIR, ScenarioError, load_scenario, scenario_library
from fynn.skills import SkillLibrary
from tests.conftest import MINI_SKILLS, write_skill


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "skills"
    directory.mkdir()
    for name, skill_type, domain in MINI_SKILLS:
        write_skill(directory, name, skill_type, domain)
    return directory


def make_scenario(
    root: Path, skills_dir: Path, *, scenario_id: str = "s9", kind: str = "body", skill: str = "score-changes",
    replace_from: str = "score-changes fact", replace_to: str = "score-changes fact\n- per-card utilization",
    extra_skills: tuple[str, ...] = (),
) -> Path:
    directory = root / scenario_id
    (directory / "skills").mkdir(parents=True)
    meta = {
        "id": scenario_id,
        "title": "Test scenario",
        "kind": kind,
        "skill": skill,
        "change": "One edit.",
        "motivation": "Testing.",
        "hypothesis": {"expected": "improve", "detail": "Better."},
    }
    (directory / "scenario.yaml").write_text(yaml.safe_dump(meta), encoding="utf-8")
    for name in (skill, *extra_skills):
        text = (skills_dir / f"{name}.md").read_text(encoding="utf-8")
        (directory / "skills" / f"{name}.md").write_text(text.replace(replace_from, replace_to), encoding="utf-8")
    return directory


def test_body_overlay_leaves_skills_dir_untouched(tmp_path: Path, skills_dir: Path) -> None:
    original = (skills_dir / "score-changes.md").read_text(encoding="utf-8")
    make_scenario(tmp_path / "scenarios", skills_dir)

    scenario = load_scenario("s9", tmp_path / "scenarios")
    assert scenario.kind == "body" and scenario.hypothesis.expected == "improve"
    library = scenario_library(scenario, skills_dir)

    assert "per-card utilization" in library.get("score-changes").body
    assert library.get("utilization") == SkillLibrary.load(skills_dir).get("utilization")
    assert (skills_dir / "score-changes.md").read_text(encoding="utf-8") == original


def test_description_scenario(tmp_path: Path, skills_dir: Path) -> None:
    make_scenario(
        tmp_path, skills_dir, kind="description", skill="utilization",
        replace_from="asks about utilization.", replace_to="asks about utilization or a score drop.",
    )
    library = scenario_library(load_scenario("s9", tmp_path), skills_dir)
    assert "score drop" in library.get("utilization").description


def test_always_on_scenario(tmp_path: Path, skills_dir: Path) -> None:
    make_scenario(tmp_path, skills_dir, kind="always_on", skill="tone", replace_from="tone fact", replace_to="terse")
    assert "terse" in scenario_library(load_scenario("s9", tmp_path), skills_dir).get("tone").body


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"kind": "description"}, "must change only the description"),
        ({"kind": "always_on"}, "always-on"),
        ({"extra_skills": ("collections",), "replace_from": "fact"}, "must touch only score-changes"),
    ],
)
def test_overlay_must_match_kind(tmp_path: Path, skills_dir: Path, kwargs: dict, message: str) -> None:
    make_scenario(tmp_path, skills_dir, **kwargs)
    with pytest.raises(ScenarioError, match=message):
        scenario_library(load_scenario("s9", tmp_path), skills_dir)


def test_id_must_match_directory(tmp_path: Path, skills_dir: Path) -> None:
    make_scenario(tmp_path, skills_dir)
    (tmp_path / "s9").rename(tmp_path / "s8")
    with pytest.raises(ScenarioError, match="must equal the directory name"):
        load_scenario("s8", tmp_path)


def test_missing_skill_file(tmp_path: Path, skills_dir: Path) -> None:
    directory = make_scenario(tmp_path, skills_dir)
    (directory / "skills" / "score-changes.md").unlink()
    with pytest.raises(ScenarioError, match="missing skills/score-changes.md"):
        load_scenario("s9", tmp_path)


def test_unknown_field_is_rejected(tmp_path: Path, skills_dir: Path) -> None:
    directory = make_scenario(tmp_path, skills_dir)
    meta = yaml.safe_load((directory / "scenario.yaml").read_text(encoding="utf-8"))
    (directory / "scenario.yaml").write_text(yaml.safe_dump({**meta, "owner": "x"}), encoding="utf-8")
    with pytest.raises(ScenarioError, match="owner"):
        load_scenario("s9", tmp_path)


# --- The real scenarios/ -----------------------------------------------------------------------

REAL = {
    "s1": ("body", "score-changes", "improve"),
    "s2": ("always_on", "response-rules", "regress"),
    "s4": ("body", "credit-builder-account", "improve"),
}


@pytest.mark.skipif(not SCENARIOS_DIR.exists(), reason="scenarios/ not written yet")
@pytest.mark.parametrize("scenario_id", sorted(REAL))
def test_real_scenarios(scenario_id: str) -> None:
    scenario = load_scenario(scenario_id)
    assert (scenario.kind, scenario.skill, scenario.hypothesis.expected) == REAL[scenario_id]
    if scenario.shipped:
        # Its edit is in skills/ now, so the overlay changes nothing and the scenario refuses to run.
        with pytest.raises(ScenarioError, match="shipped to skills/"):
            scenario_library(scenario)
        skill = SkillLibrary.load().get(scenario.skill)
    else:
        skill = scenario_library(scenario).get(scenario.skill)  # also checks the overlay changes only `kind`
    base = SkillLibrary.load().get(scenario.skill)
    if scenario_id == "s2":
        assert "120 words" in skill.body and "250 words" not in skill.body
        assert base.body.replace("250 words", "120 words") == skill.body
    if scenario_id == "s4":
        assert "up to 10 years" in skill.body and "see score-changes" not in skill.body
