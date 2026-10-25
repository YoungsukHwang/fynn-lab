"""Judge validation: the blind sample and page, regrading stored replies, and agreement. No API calls."""

import json
from pathlib import Path
from typing import Any

import pytest

import evals.cases
import evals.judge_validation as jv
from evals.cases import load_cases
from evals.judge import Judge, fact_ids
from fynn.llm import LLMError, Usage
from fynn.personas import load_personas
from tests.conftest import ROUTER_USAGE, FakeLLM

FIXTURE_CASES = Path(__file__).parent / "fixtures" / "eval_cases"
CASES = load_cases(FIXTURE_CASES)  # st-001, st-002, mi-001, sb-001; two facts each
P, A, C = "PRESENT", "ABSENT", "CONTRADICTED"


def _case(case_id: str, statuses: list[str], *, status: str = "ok", facts: list[str] | None = None) -> dict[str, Any]:
    case = next(c for c in CASES if c.id == case_id)
    texts = facts if facts is not None else list(case.expected_facts)
    return {
        "id": case_id,
        "persona": case.persona,
        "status": status,
        "reply": f"reply to {case_id}" if status == "ok" else None,
        "judge": {
            "facts": [{"fact": f, "status": s, "note": "n"} for f, s in zip(texts, statuses, strict=True)],
            "reason": "r",
            "passed": all(s == P for s in statuses),
        },
    }


def _run(answer: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "created_at": "2026-10-23T00:00:00+00:00",
        "models": {"router": "claude-haiku-5-5", "agent": answer, "judge": "claude-opus-5-5"},
        "cases": cases,
    }


def _runs() -> dict[str, dict[str, Any]]:
    return {
        "after-haiku": _run(
            "claude-haiku-5-5",
            [
                _case("st-001", [P, P]),
                _case("st-002", [P, A]),
                _case("mi-001", [A, A]),
                _case("sb-001", [P, P], status="error"),  # errored: never sampled
            ],
        ),
        "after-opus": _run(
            "claude-opus-5-5",
            [
                _case("st-001", [P, P]),
                _case("st-002", [P, P]),
                _case("mi-001", [P, C]),
                _case("sb-001", [P, P], facts=["an older wording", "of the facts"]),  # reworded since: never sampled
            ],
        ),
    }


def _graded(case_id: str, statuses: list[str]) -> dict[str, Any]:
    case = next(c for c in CASES if c.id == case_id)
    return {
        "facts": [{"id": fid, "status": s, "note": "n"} for fid, s in zip(fact_ids(case), statuses, strict=True)],
        "reason": "graded",
    }


def _sample(**kwargs: Any) -> dict[str, Any]:
    return jv.build_sample(_runs(), CASES, load_personas(), **{"per_stratum": 1, "seed": 3, **kwargs})


# ---------------------------------------------------------------- sample and page


def test_sample_draws_each_cell_and_records_how() -> None:
    sample = _sample(include=[("after-opus", "mi-001")])

    assert sample["population"] == {
        "after-haiku/judge_pass": 1,
        "after-haiku/judge_fail": 2,
        "after-opus/judge_pass": 2,  # mi-001 is targeted, sb-001's facts were reworded
        "after-opus/judge_fail": 0,
    }
    items = sample["items"]
    assert [i["item"] for i in items] == ["R01", "R02", "R03", "R04"]
    assert sorted((i["source"], i["stratum"]) for i in items) == [
        ("after-haiku", "judge_fail"),
        ("after-haiku", "judge_pass"),
        ("after-opus", "judge_pass"),
        ("after-opus", "targeted"),
    ]
    targeted = next(i for i in items if i["stratum"] == "targeted")
    assert targeted["case"] == "mi-001" and targeted["judge"]["statuses"] == {"F1": P, "F2": C}
    assert targeted["reply_sha"] == jv._sha("reply to mi-001")
    assert set(sample["profiles"]) == {i["persona"] for i in items}
    assert sample["args"] == {"runs": ["after-haiku", "after-opus"], "per_stratum": 1,
                              "include": ["after-opus:mi-001"], "seed": 3}


def test_sample_ignores_the_order_of_sources_and_includes() -> None:
    first = _sample(include=[("after-opus", "mi-001"), ("after-haiku", "st-002")])
    runs = dict(reversed(list(_runs().items())))
    second = jv.build_sample(
        runs, CASES, load_personas(), per_stratum=1, seed=3,
        include=[("after-haiku", "st-002"), ("after-opus", "mi-001"), ("after-opus", "mi-001")],  # repeated too
    )
    assert [(i["source"], i["case"]) for i in second["items"]] == [(i["source"], i["case"]) for i in first["items"]]
    assert second["sample_id"] == first["sample_id"]
    assert len(second["items"]) == 5


def test_sample_numbers_do_not_follow_source_or_verdict() -> None:
    # Many replies per cell, so an unshuffled draw would number them source by source, pass before fail.
    big = {
        source: _run(answer, [_case("st-001", [P, P]), _case("st-002", [P, A]), _case("mi-001", [A, A])])
        for source, answer in (("a", "m1"), ("b", "m2"), ("c", "m3"))
    }
    sample = jv.build_sample(big, CASES, load_personas(), per_stratum=2, seed=0)
    order = [(i["source"], i["stratum"]) for i in sample["items"]]
    assert order != sorted(order, key=lambda x: (x[0], x[1] == "judge_fail"))


def test_sample_refuses_a_targeted_reply_it_cannot_grade() -> None:
    with pytest.raises(SystemExit, match="after-haiku:sb-001"):
        _sample(include=[("after-haiku", "sb-001")])


def test_page_shows_every_item_and_nothing_that_unblinds() -> None:
    sample = _sample(include=[("after-opus", "mi-001")])
    html = jv.build_page(sample, jv.PAGE_TEMPLATE.read_text(encoding="utf-8"))
    data = json.loads(html.split('<script type="application/json" id="data">', 1)[1].split("</script>", 1)[0])

    assert data["sample_id"] == sample["sample_id"]
    assert [i["item"] for i in data["items"]] == [i["item"] for i in sample["items"]]
    assert all(set(i) == {"item", "persona", "message", "reply", "facts"} for i in data["items"])
    for leak in ("after-opus", "after-haiku", "claude-opus-5-5", "claude-haiku-5-5", "judge_pass", "targeted"):
        assert leak not in html


def test_page_adds_translations_under_the_english() -> None:
    sample = _sample()
    item = sample["items"][0]
    translations = {"messages": {item["message"]: "질문"}, "facts": {item["facts"][0]["fact"]: "사실"}}
    html = jv.build_page(sample, "__DATA__", translations)
    data = json.loads(html)
    first = next(i for i in data["items"] if i["item"] == item["item"])
    assert first["message"] == item["message"] and first["message_ko"] == "질문"
    assert first["facts"][0] == {**item["facts"][0], "ko": "사실"}
    assert "ko" not in first["facts"][1]


def test_cli_sample_refuses_to_overwrite_a_sample(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    run = tmp_path / "after-haiku.json"
    run.write_text(json.dumps(_runs()["after-haiku"]), encoding="utf-8")
    out = tmp_path / "sample.json"
    out.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="--force"):
        jv.main(["sample", "--runs", str(run), "--out", str(out)])
    assert out.read_text(encoding="utf-8") == "{}"
    jv.main(["sample", "--runs", str(run), "--out", str(out), "--force"])
    assert json.loads(out.read_text(encoding="utf-8"))["kind"] == "judge_sample"


# ---------------------------------------------------------------- regrade


def test_regrade_grades_stored_replies_with_the_given_model() -> None:
    results = _runs()["after-haiku"]
    llm = FakeLLM([_graded("st-001", [P, P]), _graded("st-002", [P, P]), _graded("mi-001", [P, A])])
    rows = jv.regrade(results, CASES, load_personas(), Judge(llm, model="claude-haiku-5-5"), workers=1, progress=None)

    assert [r["id"] for r in rows] == ["st-001", "st-002", "mi-001"]  # sb-001 errored in the run, so it is skipped
    assert {call["model"] for call in llm.json_calls} == {"claude-haiku-5-5"}
    assert "reply to st-002" in llm.json_calls[1]["messages"][0]["content"]  # the stored reply, not a new one
    assert [r["judge"]["passed"] for r in rows] == [True, True, False]
    assert rows[0]["reply_sha"] == jv._sha("reply to st-001")
    assert rows[0]["judge"]["usage"]["input_tokens"] == ROUTER_USAGE.input_tokens

    out = jv.build_regrade(source=Path("after-haiku.json"), results=results, judge_model="claude-haiku-5-5",
                           label="haiku", judge_code="j", rows=rows)
    assert out["source"] == "after-haiku" and out["complete"] is True and out["judge_code"] == "j"
    assert out["models"] == {"answer": "claude-haiku-5-5", "judge": "claude-haiku-5-5"}
    assert out["summary"] == {"graded": 3, "passed": 2, "errors": 0}


class AuthenticationError(Exception):
    pass


def test_regrade_stops_after_a_fatal_error_and_records_the_skipped_replies() -> None:
    llm = FakeLLM([AuthenticationError("invalid x-api-key"), _graded("st-002", [P, P])])
    rows = jv.regrade(_runs()["after-haiku"], CASES, load_personas(), Judge(llm), workers=1, progress=None)

    assert [r["status"] for r in rows] == ["error", "error", "error"]
    assert rows[0]["error"].startswith("AuthenticationError:")
    assert [r["error"] for r in rows[1:]] == [jv.SKIPPED_ERROR, jv.SKIPPED_ERROR]
    assert len(llm.json_calls) == 1  # nothing after the fatal error was sent
    out = jv.build_regrade(source=Path("x.json"), results=_runs()["after-haiku"], judge_model="m", label="m",
                           judge_code="j", rows=rows)
    assert out["complete"] is False


@pytest.mark.parametrize(
    ("errors", "complete"),
    [
        ([None, None], True),
        ([None, "LLMError: judge did not grade F2"], True),  # one bad reply, not fatal
        (["AuthenticationError: invalid x-api-key", None], False),  # fatal on a reply already in flight
        (["LLMError: a", "LLMError: b"], False),  # every reply errored
        ([None, jv.SKIPPED_ERROR], False),
    ],
)
def test_regrade_is_complete_only_without_a_fatal_error(errors: list[str | None], complete: bool) -> None:
    rows = [{"status": "ok" if e is None else "error", "error": e} for e in errors]
    assert jv.regrade_complete(rows) is complete


def test_regrade_keeps_a_failed_calls_tokens() -> None:
    llm = FakeLLM([LLMError("judge did not grade F2", Usage(input_tokens=7)), _graded("st-002", [P, P])])
    results = _run("claude-haiku-5-5", [_case("st-001", [P, P]), _case("st-002", [P, P])])
    rows = jv.regrade(results, CASES, load_personas(), Judge(llm), workers=1, progress=None)

    assert [r["status"] for r in rows] == ["error", "ok"]  # not fatal, so the next reply is still graded
    assert rows[0]["judge"]["usage"]["input_tokens"] == 7


def test_cli_regrade_writes_a_partial_file_after_a_fatal_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    results = tmp_path / "after-haiku.json"
    results.write_text(json.dumps(_runs()["after-haiku"]), encoding="utf-8")
    monkeypatch.setattr(jv, "make_judge_llm", lambda: FakeLLM([_graded("st-001", [P, P]),
                                                               RuntimeError("Your credit balance is too low")]))
    out = tmp_path / "regrades" / "sonnet.json"
    with pytest.raises(SystemExit):
        jv.main(["regrade", "--results", str(results), "--workers", "1", "--out", str(out)])
    assert not out.exists()
    partial = json.loads((tmp_path / "regrades" / "sonnet.partial.json").read_text(encoding="utf-8"))
    assert partial["complete"] is False and partial["summary"] == {"graded": 1, "passed": 1, "errors": 2}

    warnings: list[str] = []
    assert jv.load_regrades([tmp_path / "regrades"], warnings) == []
    assert "partial regrade" in warnings[0]


def test_cli_regrade_records_the_judge_code_it_started_with(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    results = tmp_path / "after-haiku.json"
    results.write_text(json.dumps(_runs()["after-haiku"]), encoding="utf-8")
    codes = iter(["at start", "after an edit"])
    monkeypatch.setattr(jv, "setup_fingerprint", lambda: {"judge_code": next(codes)})
    llm = FakeLLM([_graded("st-001", [P, P]), _graded("st-002", [P, P]), _graded("mi-001", [P, P])])
    monkeypatch.setattr(jv, "make_judge_llm", lambda: llm)
    out = jv.main(["regrade", "--results", str(results), "--judge-model", "claude-sonnet-5-5", "--workers", "1",
                   "--out", str(tmp_path / "r.json")])
    assert out["judge_code"] == "at start"
    assert {call["model"] for call in llm.json_calls} == {"claude-sonnet-5-5"}


def test_cli_regrade_without_credentials_stops_before_any_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # conftest removed every credential source, so the real client builder refuses.
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    results = tmp_path / "after.json"
    results.write_text(json.dumps(_runs()["after-haiku"]), encoding="utf-8")
    with pytest.raises(SystemExit, match="No Anthropic credentials"):
        jv.main(["regrade", "--results", str(results), "--out", str(tmp_path / "out.json")])
    assert not (tmp_path / "out.json").exists()


# ---------------------------------------------------------------- agreement


def test_compare_counts_agreement_kappa_and_direction() -> None:
    result = jv.compare([(P, P), (P, A), (A, A), (C, A)], ["r1", "r1", "r2", "r3"])
    assert result["agree"] == 2  # three-way: (P, P) and (A, A)
    assert result["agree_binary"] == 3  # C and A both count as not present
    assert result["kappa_binary"] == 0.5  # observed 0.75, expected 0.5
    assert (result["stricter"], result["lenient"]) == (0, 1)
    assert result["confusion"][C][A] == 1
    assert result["replies"] == 3
    low, high = result["ci_binary"]
    assert low <= 0.75 <= high

    stricter = jv.compare([(A, P), (P, P)], ["r1", "r1"])
    assert (stricter["stricter"], stricter["lenient"]) == (1, 0)
    assert stricter["ci_binary"] is None  # one reply: no interval


def _item(item: str, case: str, stratum: str, judge: list[str], source: str = "x") -> dict[str, Any]:
    case_def = next(c for c in CASES if c.id == case)
    return {
        "item": item, "source": source, "case": case, "stratum": stratum, "reply_sha": jv._sha(f"reply to {case}"),
        "facts": [{"id": fid, "fact": f} for fid, f in zip(fact_ids(case_def), case_def.expected_facts, strict=True)],
        "judge": {"model": "m", "statuses": dict(zip(["F1", "F2"], judge, strict=True))},
    }


def _regrade_row(case: str, statuses: list[str], reply: str | None = None) -> dict[str, Any]:
    case_def = next(c for c in CASES if c.id == case)
    return {
        "id": case, "status": "ok", "reply_sha": jv._sha(reply or f"reply to {case}"),
        "judge": {"facts": [{"fact": f, "status": s} for f, s in zip(case_def.expected_facts, statuses, strict=True)],
                  "passed": all(s == P for s in statuses)},
    }


SAMPLE = {
    "population": {"x/judge_pass": 9, "x/judge_fail": 3},
    "items": [
        _item("R01", "st-001", "judge_pass", [P, P]),
        _item("R02", "st-002", "judge_fail", [P, A]),
        _item("R03", "mi-001", "judge_fail", [A, A]),
        _item("R04", "sb-001", "targeted", [A, P]),
    ],
}
ALL_PRESENT = {i["item"]: {"F1": P, "F2": P} for i in SAMPLE["items"]}


def test_human_agreement_weights_by_the_replies_compared() -> None:
    labels = {**ALL_PRESENT, "R03": {"F1": P}}  # R03 partly labeled: left out, so R02 alone stands for its cell
    warnings: list[str] = []
    report = jv.human_agreement(SAMPLE, labels, jv.judge_views(SAMPLE, [], warnings), warnings)

    original = report["judges"]["original (m)"]
    assert (original["replies"], original["facts"], original["agree_binary"], original["stricter"]) == (2, 4, 3, 1)
    assert original["weighted_rate_binary"] == 0.875  # R01 stands for 9 replies (2 agree), R02 for 3 (1 of 2 agree)
    assert (original["replies_agree"], original["replies_judge_fail_human_pass"]) == (1, 1)
    assert original["replies_judge_fail"] == 1  # R02; the person passes it, so it is also the one disagreement
    assert (report["labeled_items"], report["partly_labeled_items"], report["labeled_random_replies"]) == (3, 1, 2)
    assert report["targeted"][0]["facts"] == [{"id": "F1", "human": P, "original (m)": A},
                                              {"id": "F2", "human": P, "original (m)": P}]
    assert warnings == []


def test_another_judge_is_set_beside_the_original_on_the_same_replies() -> None:
    # The cheap judge regraded st-002 only, and agrees with the human there; the original judge did not.
    regrades = [{"kind": "judge_regrade", "label": "cheap", "source": "x", "cases": [_regrade_row("st-002", [P, P])]}]
    warnings: list[str] = []
    report = jv.human_agreement(SAMPLE, ALL_PRESENT, jv.judge_views(SAMPLE, regrades, warnings), warnings)

    original, cheap = report["judges"]["original (m)"], report["judges"]["cheap"]
    assert (original["replies"], original["facts"], original["agree_binary"]) == (3, 6, 3)  # every labeled reply
    assert (cheap["replies"], cheap["rate_binary"]) == (1, 1.0)
    assert cheap["original_on_same_replies"]["rate_binary"] == 0.5  # the original on st-002 alone
    assert "original_on_same_replies" not in original
    assert any("cheap: no compared reply stands for x/judge_pass" in w for w in warnings)


def test_a_regrade_outside_the_sample_leaves_the_original_judge_alone() -> None:
    elsewhere = [{"kind": "judge_regrade", "label": "cheap", "source": "before", "cases": [_regrade_row("st-001", [P, P])]}]
    warnings: list[str] = []
    views = jv.judge_views(SAMPLE, elsewhere, warnings)
    report = jv.human_agreement(SAMPLE, ALL_PRESENT, views, warnings)
    assert list(report["judges"]) == ["original (m)"] and report["judges"]["original (m)"]["replies"] == 3
    assert "none of its replies are in the sample" in warnings[0]


def test_a_regrade_of_another_reply_is_left_out() -> None:
    regrades = [{"kind": "judge_regrade", "label": "cheap", "source": "x",
                 "cases": [_regrade_row("st-001", [P, P], reply="a rerun's new reply")]}]
    warnings: list[str] = []
    views = jv.judge_views(SAMPLE, regrades, warnings)
    assert "cheap" not in views
    assert "different reply or different facts" in warnings[0]


def test_judge_vs_judge_counts_direction_and_skips_what_does_not_match() -> None:
    run = {**_runs()["after-haiku"], "setup_fingerprint": {"judge_code": "old"}}
    rows = [
        _regrade_row("st-001", [A, P]),  # the regrade fails a fact the original passed: stricter
        _regrade_row("st-002", [P, P]),  # the original's F2 ABSENT: the regrade is more lenient
        _regrade_row("mi-001", [A, A], reply="another reply"),  # the run was rerun since: left out
    ]
    regrade = {"kind": "judge_regrade", "label": "opus again", "source": "after-haiku", "judge_code": "new", "cases": rows}
    warnings: list[str] = []
    [pair] = jv.judge_vs_judge({"after-haiku": run}, [regrade], CASES, warnings)

    assert (pair["replies"], pair["facts"], pair["stricter"], pair["lenient"]) == (2, 4, 1, 1)
    assert pair["passes"] == {"original": 1, "regrade": 1, "both": 0}
    assert pair["same_judge_code"] is False
    assert any("1 replies differ from the results file" in w for w in warnings)
    assert any("judge prompt or checks changed" in w for w in warnings)

    missing: list[str] = []
    assert jv.judge_vs_judge({}, [regrade], CASES, missing) == []
    assert "--runs" in missing[0]


def test_load_labels_takes_the_pages_format_and_checks_sample_and_statuses(tmp_path: Path) -> None:
    page = tmp_path / "page.json"
    page.write_text(json.dumps({"sample_id": "s1", "labels": {"R01": {"facts": {"F1": P}, "note": "close call",
                                                                       "sample": "s1"}}}), encoding="utf-8")
    assert jv.load_labels(page, "s1") == {"R01": {"F1": P}}
    with pytest.raises(SystemExit, match="labeled for sample s1"):
        jv.load_labels(page, "s2")

    flat = tmp_path / "flat.json"
    flat.write_text(json.dumps({"R01": {"F1": "MAYBE"}}), encoding="utf-8")
    with pytest.raises(SystemExit, match="MAYBE"):
        jv.load_labels(flat)


def test_cli_sample_regrade_agreement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    runs = tmp_path / "runs"
    runs.mkdir()
    for name, results in _runs().items():
        (runs / f"{name}.json").write_text(json.dumps(results), encoding="utf-8")

    sample = jv.main(["sample", "--runs", str(runs / "after-haiku.json"), "--per-stratum", "2",
                      "--out", str(tmp_path / "sample.json")])
    assert len(sample["items"]) == 3  # 1 pass and 2 fails are all the eligible replies
    jv.main(["page", "--sample", str(tmp_path / "sample.json"), "--out", str(tmp_path / "page.html")])
    assert sample["sample_id"] in (tmp_path / "page.html").read_text(encoding="utf-8")

    llm = FakeLLM([_graded("st-001", [P, P]), _graded("st-002", [P, P]), _graded("mi-001", [A, A])])
    monkeypatch.setattr(jv, "make_judge_llm", lambda: llm)
    regrade_out = tmp_path / "regrades" / "sonnet-on-after-haiku.json"
    jv.main(["regrade", "--results", str(runs / "after-haiku.json"), "--judge-model", "claude-sonnet-5-5",
             "--workers", "1", "--out", str(regrade_out)])
    assert json.loads(regrade_out.read_text())["label"] == "claude-sonnet-5-5"

    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"sample_id": sample["sample_id"], "labels": {
        i["item"]: {"facts": {f["id"]: P for f in i["facts"]}, "note": "", "sample": sample["sample_id"]}
        for i in sample["items"]}}), encoding="utf-8")
    report = jv.main(["agreement", "--sample", str(tmp_path / "sample.json"), "--labels", str(labels),
                      "--regrades", str(tmp_path / "regrades"), "--runs", str(runs / "after-haiku.json"),
                      "--out", str(tmp_path / "agreement")])
    assert set(report["human"]["judges"]) == {"original (claude-opus-5-5)", "claude-sonnet-5-5"}
    assert report["human"]["labeled_random_replies"] == 3
    assert report["judge_vs_judge"][0]["passes"] == {"original": 1, "regrade": 2, "both": 1}
    assert report["judge_vs_judge"][0]["same_judge_code"] is None  # the fixture run records no setup fingerprint
    assert (tmp_path / "agreement" / "agreement.md").read_text().startswith("# Judge validation")
