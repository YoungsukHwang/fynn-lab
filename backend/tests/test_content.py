"""Checks on the real skill and persona files in the repo (not fixtures)."""

from fynn import config
from fynn.personas import load_personas
from fynn.skills import SkillLibrary

EXPECTED_ALWAYS_ON = {"tone", "response-rules", "guardrails"}
EXPECTED_TOPICS = {
    "score-and-reports": {"score-changes", "utilization", "payment-history"},
    "credit-products": {"credit-builder-account", "secured-card", "marketplace-offers"},
    "rent-and-bills": {"rent-reporting", "bill-reporting"},
    "debt-and-collections": {"debt-settlement", "collections"},
}
EXPECTED_PERSONAS = {"new-to-credit", "rebuilder", "high-util", "renter", "collections", "multi-product"}


def test_skill_catalog_matches_spec() -> None:
    library = SkillLibrary.load()
    assert {s.name for s in library.always_on} == EXPECTED_ALWAYS_ON
    for domain in config.DOMAINS:
        assert {s.name for s in library.domain_skills(domain)} == EXPECTED_TOPICS[domain]


def test_skill_descriptions_are_distinct() -> None:
    descriptions = [s.description for s in SkillLibrary.load().topics]
    assert len(set(descriptions)) == len(descriptions)


def test_personas_load_and_are_consistent() -> None:
    personas = load_personas()
    assert set(personas) == EXPECTED_PERSONAS
    for persona in personas.values():
        util = persona.credit["utilization"]
        limit = util["total_revolving_limit"]
        if limit:
            assert round(util["total_revolving_balance"] / limit, 2) == round(util["overall"], 2), persona.id
        assert set(persona.products) == {"credit_builder", "secured_card", "rent_reporting", "bill_reporting", "debt_settlement"}


def test_rebuilder_matches_blog_example() -> None:
    jordan = load_personas()["rebuilder"]
    assert jordan.credit["score"]["current"] < jordan.credit["score"]["previous"]
    assert jordan.products["secured_card"]["status"] == "shipped"
    assert not jordan.products["secured_card"]["activated"]
