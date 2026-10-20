from pathlib import Path

import pytest

from fynn.skills import SkillFormatError, SkillLibrary, parse_skill
from tests.conftest import write_skill


def test_parse_topic_skill(tmp_path: Path) -> None:
    skill = parse_skill(write_skill(tmp_path, "secured-card", "topic", "credit-products"))
    assert skill.name == "secured-card"
    assert skill.type == "topic"
    assert skill.domain == "credit-products"
    assert skill.body.startswith("## Facts")
    assert "Use when" in skill.description


def test_content_hash_changes_when_file_changes(tmp_path: Path) -> None:
    path = write_skill(tmp_path, "utilization", "topic", "score-and-reports", body="v1")
    first = parse_skill(path).content_hash
    write_skill(tmp_path, "utilization", "topic", "score-and-reports", body="v2")
    assert parse_skill(path).content_hash != first


def test_body_edit_changes_only_the_body_hash(tmp_path: Path) -> None:
    path = write_skill(tmp_path, "utilization", "topic", "score-and-reports", body="v1")
    before = parse_skill(path).hashes
    write_skill(tmp_path, "utilization", "topic", "score-and-reports", body="v2")
    after = parse_skill(path).hashes
    assert after.body != before.body
    assert (after.description, after.meta) == (before.description, before.meta)


def test_description_edit_changes_only_the_description_hash(tmp_path: Path) -> None:
    path = write_skill(tmp_path, "utilization", "topic", "score-and-reports")
    before = parse_skill(path).hashes
    path.write_text(path.read_text().replace("Covers utilization.", "Covers utilization and score drops."))
    after = parse_skill(path).hashes
    assert after.description != before.description
    assert (after.body, after.meta) == (before.body, before.meta)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("no frontmatter", "frontmatter"),
        ("---\nname: other\ndescription: d\ntype: topic\ndomain: credit-products\n---\nbody\n", "file name"),
        ("---\nname: bad\ndescription: d\ntype: sometimes\n---\nbody\n", "type"),
        ("---\nname: bad\ndescription: d\ntype: topic\n---\nbody\n", "domain"),
        ("---\nname: bad\ndescription: d\ntype: topic\ndomain: nowhere\n---\nbody\n", "domain"),
        ("---\nname: bad\ndescription: d\ntype: always_on\ndomain: credit-products\n---\nbody\n", "no domain"),
        ("---\nname: bad\ndescription: \ntype: always_on\n---\nbody\n", "description"),
        ("---\nname: bad\ndescription: d\ntype: always_on\n---\n\n", "body"),
    ],
)
def test_invalid_skill_files_are_rejected(tmp_path: Path, text: str, message: str) -> None:
    path = tmp_path / "bad.md"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(SkillFormatError, match=message):
        parse_skill(path)


def test_library_groups_skills(mini_library: SkillLibrary) -> None:
    assert [s.name for s in mini_library.always_on] == ["guardrails", "tone"]
    assert mini_library.topic_names == ["collections", "rent-reporting", "score-changes", "secured-card", "utilization"]
    assert [s.name for s in mini_library.domain_skills("score-and-reports")] == ["score-changes", "utilization"]
    assert set(mini_library.fingerprint()) == {s.name for s in mini_library.all}


def test_empty_directory_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        SkillLibrary.load(tmp_path)
