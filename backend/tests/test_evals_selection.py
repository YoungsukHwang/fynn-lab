"""Dependent-test selection rules (SPEC section 3 table)."""

from dataclasses import asdict, replace

import pytest

from evals.cases import EvalCase
from evals.selection import SkillChange, baseline_routing, diff_libraries, select_cases, select_changed, select_for_changes
from fynn.skills import SkillLibrary


def _case(case_id: str, skills: list[str]) -> EvalCase:
    dataset = {"st": "single_topic", "mi": "multi_intent", "sb": "safety_basic"}[case_id[:2]]
    return EvalCase(
        id=case_id,
        dataset=dataset,
        persona="tester",
        message="m",
        intents=1,
        skills=skills,
        expected_facts=["a", "b"],
    )


CASES = [
    _case("st-001", ["score-changes"]),
    _case("st-002", ["utilization"]),
    _case("mi-001", ["secured-card", "rent-reporting"]),
    _case("sb-001", []),
]
ALL_IDS = [c.id for c in CASES]

# st-002 is labeled utilization, but the baseline router also loaded score-changes for it.
AFTER_BASELINE = {
    "bot": "after",
    "cases": [
        {"id": "st-002", "routing": {"selected": ["utilization", "score-changes"], "carried": []}},
        {"id": "mi-001", "routing": {"selected": ["secured-card"], "carried": []}},
        {"id": "sb-001", "routing": None},
    ],
}


def _variant(library: SkillLibrary, name: str, **changes) -> SkillLibrary:
    return SkillLibrary([replace(s, **changes) if s.name == name else s for s in library.all])


def test_topic_body_change_reruns_labeled_and_routed_cases(mini_library: SkillLibrary) -> None:
    candidate = _variant(mini_library, "score-changes", body="new body")
    ids, rule = select_cases(CASES, mini_library, candidate, AFTER_BASELINE)
    assert ids == ["st-001", "st-002"]
    assert "body of topic skill score-changes" in rule
    assert "2 of 4" in rule


def test_topic_body_change_without_baseline_uses_labels_only(mini_library: SkillLibrary) -> None:
    candidate = _variant(mini_library, "score-changes", body="new body")
    ids, rule = select_cases(CASES, mini_library, candidate, None)
    assert ids == ["st-001"]
    assert "no baseline routing" in rule


def test_body_change_uses_before_domain_routing(mini_library: SkillLibrary) -> None:
    # The Before bot loads every skill of the domain it routes to.
    baseline = {"bot": "before", "cases": [{"id": "mi-001", "routing": {"selected": ["score-and-reports"]}}]}
    candidate = _variant(mini_library, "utilization", body="new body")
    ids, _ = select_cases(CASES, mini_library, candidate, baseline)
    assert ids == ["st-002", "mi-001"]


@pytest.mark.parametrize(
    ("name", "changes", "phrase"),
    [
        ("score-changes", {"description": "Covers score drops and anything about balances."}, "description of topic"),
        ("tone", {"body": "## Facts\n- shorter"}, "always-on skill tone"),
        ("tone", {"description": "Tone rules, reworded."}, "always-on skill tone"),
        ("utilization", {"domain": "credit-products"}, "only the Before bot"),
        ("collections", {"type": "always_on", "domain": None}, "type of collections"),
    ],
)
def test_changes_that_rerun_everything(mini_library: SkillLibrary, name: str, changes: dict, phrase: str) -> None:
    candidate = _variant(mini_library, name, **changes)
    ids, rule = select_cases(CASES, mini_library, candidate, AFTER_BASELINE)
    assert ids == ALL_IDS
    assert rule.startswith("all cases")
    assert phrase in rule


def test_added_skill_reruns_everything(mini_library: SkillLibrary) -> None:
    extra = replace(mini_library.get("collections"), name="debt-settlement")
    candidate = SkillLibrary([*mini_library.all, extra])
    ids, rule = select_cases(CASES, mini_library, candidate, AFTER_BASELINE)
    assert ids == ALL_IDS
    assert "debt-settlement was added" in rule


def test_no_change_reruns_nothing(mini_library: SkillLibrary) -> None:
    assert select_cases(CASES, mini_library, mini_library, AFTER_BASELINE) == ([], "no skill changed: nothing to rerun")


def test_diff_names_each_changed_part(mini_library: SkillLibrary) -> None:
    candidate = _variant(mini_library, "score-changes", body="b", description="d")
    [change] = diff_libraries(mini_library, candidate)
    assert (change.skill, change.parts, change.type) == ("score-changes", ("description", "body"), "topic")


def _fingerprint(library: SkillLibrary) -> dict:
    return {name: asdict(h) for name, h in library.fingerprint().items()}


def test_select_changed_diffs_against_the_baseline_fingerprint(mini_library: SkillLibrary) -> None:
    baseline = {**AFTER_BASELINE, "skill_fingerprint": _fingerprint(mini_library)}

    body = _variant(mini_library, "score-changes", body="new body")
    assert select_changed(CASES, baseline, body)[0] == ["st-001", "st-002"]

    domain = _variant(mini_library, "utilization", domain="credit-products")
    ids, rule = select_changed(CASES, baseline, domain)
    assert ids == ALL_IDS
    assert "type or domain of utilization" in rule

    assert select_changed(CASES, baseline, mini_library)[0] == []


def test_baseline_routing_is_the_union_over_repeated_runs() -> None:
    baseline = {
        "cases": [
            {
                "id": "st-002",
                "routing": {"selected": ["rent-reporting"], "carried": []},
                "runs": [
                    {"routing": {"selected": ["rent-reporting"], "carried": []}},
                    {"routing": {"selected": ["rent-reporting", "score-changes"], "carried": []}},
                    {"routing": None},
                ],
            }
        ]
    }
    assert baseline_routing(baseline) == {"st-002": {"rent-reporting", "score-changes"}}
    # st-002 is labeled utilization; only its second baseline run loaded score-changes.
    body = SkillChange("score-changes", ("body",), "topic", "score-and-reports")
    ids, _ = select_for_changes([_case("st-002", ["utilization"])], [body], baseline)
    assert ids == ["st-002"]
