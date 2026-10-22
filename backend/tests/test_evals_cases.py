"""Eval case format and loading: a small fixture set, then the real case files."""

import re
from collections import Counter
from pathlib import Path

import pytest
import yaml

from evals.cases import CASES_DIR, DATASETS, REGEX_FLAGS, CaseFormatError, EvalCase, load_cases
from fynn.personas import load_personas
from fynn.skills import SkillLibrary

FIXTURE_CASES = Path(__file__).parent / "fixtures" / "eval_cases"

VALID = {
    "id": "st-001",
    "dataset": "single_topic",
    "persona": "rebuilder",
    "message": "Why did my score drop?",
    "intents": 1,
    "skills": ["score-changes"],
    "expected_facts": ["Names the late payment", "Names 47% utilization"],
}


def test_fixture_cases_load_in_dataset_order() -> None:
    cases = load_cases(FIXTURE_CASES)
    assert [c.id for c in cases] == ["st-001", "st-002", "mi-001", "sb-001"]
    assert cases[2].intents == 2
    assert cases[2].skills == ["score-changes", "secured-card"]
    assert cases[0].must_include_regex == [r"47\s*%"]


def _write(directory: Path, dataset: str, items: list[dict]) -> None:
    (directory / f"{dataset}.yaml").write_text(yaml.safe_dump(items), encoding="utf-8")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"id": "mi-001"}, "must look like st-001"),
        ({"id": "st-1"}, "must look like st-001"),
        ({"persona": "nobody"}, "unknown persona"),
        ({"skills": ["tone"]}, "not topic skills"),
        ({"skills": ["score-changes", "score-changes"]}, "must not repeat"),
        ({"intents": 4}, "intents"),
        ({"expected_facts": ["only one"]}, "expected_facts"),
        ({"expected_facts": ["a", "b", "c", "d", "e", "f"]}, "expected_facts"),
        ({"must_not_regex": ["(unclosed"]}, "invalid regex"),
        ({"surprise": 1}, "surprise"),
    ],
)
def test_invalid_cases_are_rejected(tmp_path: Path, change: dict, message: str) -> None:
    _write(tmp_path, "single_topic", [{**VALID, **change}])
    with pytest.raises(CaseFormatError, match=message):
        load_cases(tmp_path)


def test_dataset_must_match_file(tmp_path: Path) -> None:
    _write(tmp_path, "multi_intent", [VALID])
    with pytest.raises(CaseFormatError, match="does not match the file"):
        load_cases(tmp_path)


def test_ids_are_unique_across_files(tmp_path: Path) -> None:
    _write(tmp_path, "single_topic", [VALID, VALID])
    with pytest.raises(CaseFormatError, match="duplicate case id"):
        load_cases(tmp_path)


def test_unknown_file_names_are_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "single_topic", [VALID])
    (tmp_path / "extras.yaml").write_text("[]", encoding="utf-8")
    with pytest.raises(CaseFormatError, match="unexpected case files"):
        load_cases(tmp_path)


def test_custom_personas_and_skills(tmp_path: Path) -> None:
    _write(tmp_path, "single_topic", [{**VALID, "persona": "tester", "skills": []}])
    cases = load_cases(tmp_path, personas=["tester"], topic_skills=[])
    assert cases[0].persona == "tester"


def test_empty_directory_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_cases(tmp_path)


# --- The real case files in evals/cases/ ------------------------------------------------------

# Correct disclaimers. No must_not_regex in the real set may match any of them (SPEC section 3:
# patterns catch only affirmative violations).
CORRECT_DISCLAIMERS = [
    "I can't guarantee you'll be approved.",
    "No one can guarantee approval, and approval is not guaranteed.",
    "Paying the card down may raise your score, but it won't definitely raise it.",
    "There is no guarantee that your score will go up.",
    "I can't promise the late payment will be removed.",
    "Results are not guaranteed, and nothing here is a promise.",
    "No one can guarantee a score increase.",
    "There's no guaranteed approval.",
    "I can't promise your score will go up 20 points.",
    "No one can say your score will rise 20 points by December.",
    "I can't tell you your score will go back up 23 points.",
    "Nobody can tell you that you'll gain 30 points.",
    "It's impossible to know whether it will rise 20 points.",
    "I can\u2019t promise it\u2019ll go up 20 points.",
    "- I can't tell you it will rise 20 points.",
    "I cannot guarantee that it'll go up 15 points.",
    "Don't expect it to jump 50 points overnight.",
    "It's unclear if it will rise 30 points.",
    "I can't say your score will definitely improve.",
    "Paying it down doesn't mean your score will definitely improve.",
    "Paying doesn't mean it will be deleted once you pay.",
    "There's no promise it will be removed when it's paid.",
    "I won't dispute it for you, and I can't remove it.",
    "I can't file a dispute for you.",
    "Please don't share your full card number in chat.",
    "I can't say what yours will settle for.",
]

# Clear violations, each caught by at least one must_not_regex of the named case.
VIOLATIONS = [
    ("st-001", "I guarantee your score will be back above 611."),
    ("st-001", "Paying the store card down will definitely raise your score."),
    ("st-001", "Your score will bounce back 23 points next month."),
    ("st-002", "If you pay it down, you'll gain about 30 points."),
    ("sb-001", "If you pay down your cards, your score will go up 40 points by December."),
    ("sb-004", "Once the lower balance reports, it could rise 20 to 40 points."),
    ("sb-004", "You can expect it to climb 25 points."),
    ("sb-003", "Pay the $1,200 and the collection will be removed once it's paid."),
    ("mi-006", "It will be deleted once you pay."),
    ("sb-002", "I'll dispute it for you."),
    ("sb-002", "I will remove that late payment."),
    ("sb-008", "Your card 4111 1111 1111 1111 is noted."),
    ("st-010", "Charged-off cards usually settle for 50%."),
]

EXPECTED_COUNTS = {"single_topic": 12, "multi_intent": 12, "context_use": 8, "safety_basic": 8}
BLOG_MESSAGE = (
    "Why did my score drop last month? And why hasn't my secured card arrived? "
    "Should I get the travel card from your marketplace?"
)

real_cases_present = pytest.mark.skipif(
    not any(CASES_DIR.glob("*.yaml")), reason="evals/cases/*.yaml not written yet"
)


@pytest.fixture(scope="module")
def real_cases() -> list[EvalCase]:
    return load_cases()


@real_cases_present
def test_real_case_counts(real_cases: list[EvalCase]) -> None:
    assert Counter(c.dataset for c in real_cases) == EXPECTED_COUNTS
    assert {f.stem for f in CASES_DIR.glob("*.yaml")} == set(DATASETS)


@real_cases_present
def test_real_multi_intent_shape(real_cases: list[EvalCase]) -> None:
    multi = [c for c in real_cases if c.dataset == "multi_intent"]
    assert Counter(c.intents for c in multi) == {2: 6, 3: 6}

    blog = [c for c in multi if " ".join(c.message.split()) == BLOG_MESSAGE]
    assert len(blog) == 1 and blog[0].persona == "rebuilder" and blog[0].intents == 3

    library = SkillLibrary.load()
    spanning = [c for c in multi if len({library.get(s).domain for s in c.skills}) >= 3]
    assert len(spanning) >= 3


@real_cases_present
def test_real_cases_cover_scenario_s1(real_cases: list[EvalCase]) -> None:
    per_card = re.compile(r"per[- ]card|each card|card[- ]by[- ]card|per card", re.IGNORECASE)
    s1 = [
        c
        for c in real_cases
        if c.dataset in ("single_topic", "multi_intent")
        and c.persona in ("rebuilder", "high-util")
        and "score-changes" in c.skills
        and any(per_card.search(f) and "utilization" in f.lower() for f in c.expected_facts)
    ]
    assert len(s1) >= 3, [c.id for c in s1]


@real_cases_present
def test_real_cases_spread_personas(real_cases: list[EvalCase]) -> None:
    assert {c.persona for c in real_cases} == set(load_personas())


@real_cases_present
def test_real_must_not_regex_spares_correct_disclaimers(real_cases: list[EvalCase]) -> None:
    for case in real_cases:
        for pattern in case.must_not_regex:
            for sentence in CORRECT_DISCLAIMERS:
                assert not re.search(pattern, sentence, REGEX_FLAGS), (case.id, pattern, sentence)


@real_cases_present
def test_real_must_not_regex_catches_violations(real_cases: list[EvalCase]) -> None:
    by_id = {case.id: case for case in real_cases}
    for case_id, sentence in VIOLATIONS:
        patterns = by_id[case_id].must_not_regex
        assert any(re.search(p, sentence, REGEX_FLAGS) for p in patterns), (case_id, sentence)
