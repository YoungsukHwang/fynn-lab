"""Routing coverage and reply length, computed from results files. No API calls."""

from typing import Any

from evals.quality import available_skills, reply_lengths, routing_quality
from fynn.skills import SkillLibrary


def _case(skills: list[str], strategy: str, selected: list[str], reply: str = "a b c", status: str = "ok") -> dict[str, Any]:
    return {
        "id": "-".join(skills) + "/" + "-".join(selected),
        "skills": skills,
        "status": status,
        "reply": reply,
        "routing": {"strategy": strategy, "selected": selected, "carried": []},
    }


def test_a_before_agent_has_every_skill_of_its_domain(mini_library: SkillLibrary) -> None:
    domains = {s.name: s.domain for s in mini_library.topics}
    assert available_skills({"strategy": "single_agent", "selected": ["score-and-reports"]}, domains) == {
        "score-changes",
        "utilization",
    }
    assert available_skills({"strategy": "skills", "selected": ["secured-card"], "carried": ["rent-reporting"]}, domains) == {
        "secured-card",
        "rent-reporting",
    }


def test_routing_quality_for_the_before_bot(mini_library: SkillLibrary) -> None:
    results = {
        "cases": [
            _case(["score-changes", "utilization"], "single_agent", ["score-and-reports"]),  # one domain: covered
            _case(["score-changes", "secured-card"], "single_agent", ["score-and-reports"]),  # second domain missing
            _case(["collections"], "single_agent", ["score-and-reports"]),  # wrong domain
            _case(["collections"], "single_agent", ["debt-and-collections"], status="error"),  # left out
        ]
    }
    q = routing_quality(results, mini_library)
    assert (q["strategy"], q["cases"], q["runs"], q["all_available"]) == ("single_agent", 3, 3, 1)
    assert q["by_group"] == {"cross": {"runs": 1, "all_available": 0}, "single": {"runs": 2, "all_available": 1}}
    assert q["skills"]["secured-card"] == {"labeled": 1, "available": 0, "picked": 0, "picked_unlabeled": 0}
    assert q["skills"]["score-changes"]["available"] == 2


def test_routing_quality_for_the_after_bot_counts_picks(mini_library: SkillLibrary) -> None:
    results = {
        "cases": [
            _case(["score-changes", "secured-card"], "skills", ["score-changes", "secured-card", "utilization"]),
            _case(["score-changes", "utilization"], "skills", ["score-changes"]),
        ]
    }
    q = routing_quality(results, mini_library)
    assert (q["cases"], q["all_available"]) == (2, 1)
    assert q["by_group"]["cross"] == {"runs": 1, "all_available": 1}
    assert q["skills"]["utilization"] == {"labeled": 1, "available": 0, "picked": 1, "picked_unlabeled": 1}
    assert q["skills"]["score-changes"] == {"labeled": 2, "available": 2, "picked": 2, "picked_unlabeled": 0}


def test_reply_lengths_counts_words_over_the_limit() -> None:
    results = {
        "cases": [
            {"status": "ok", "reply": " ".join(["w"] * 100)},
            {"status": "ok", "reply": " ".join(["w"] * 260)},
            {"status": "ok", "reply": " ".join(["w"] * 320)},
            {"status": "error", "reply": None},
        ]
    }
    lengths = reply_lengths(results)
    assert lengths == {"replies": 3, "median_words": 260, "mean_words": 226.7, "limit": 250, "over_limit": 2, "over_300": 1}


def test_every_run_of_a_repeated_case_counts(mini_library: SkillLibrary) -> None:
    case = {
        "id": "mi-001",
        "skills": ["score-changes", "secured-card"],
        "runs": [
            {"status": "ok", "reply": "a b", "routing": {"strategy": "skills", "selected": ["score-changes", "secured-card"]}},
            {"status": "ok", "reply": "a b c d", "routing": {"strategy": "skills", "selected": ["score-changes"]}},
            {"status": "error", "reply": None, "routing": None},
        ],
    }
    q = routing_quality({"cases": [case]}, mini_library)
    assert (q["cases"], q["runs"], q["all_available"]) == (1, 2, 1)
    assert reply_lengths({"cases": [case]})["replies"] == 2
