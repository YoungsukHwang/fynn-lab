"""Central settings: model ids, effort levels, limits, and content paths."""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"
PERSONAS_DIR = REPO_ROOT / "personas"

# Load backend/.env before reading any setting below, so overrides placed there take
# effect for every entry point. Variables already exported in the shell win.
load_dotenv(os.environ.get("FYNN_ENV_FILE", REPO_ROOT / "backend" / ".env"))

# The router is the "small LLM" from the blog diagrams; the agent writes the answer.
# Both bots always share the same agent model so the comparison stays fair.
ROUTER_MODEL = os.environ.get("FYNN_ROUTER_MODEL", "claude-haiku-5-5")
AGENT_MODEL = os.environ.get("FYNN_AGENT_MODEL", "claude-sonnet-5-5")
JUDGE_MODEL = os.environ.get("FYNN_JUDGE_MODEL", "claude-opus-5-5")

ROUTER_EFFORT = "low"
AGENT_EFFORT = "low"

ROUTER_MAX_TOKENS = 2048
AGENT_MAX_TOKENS = 16000

# After bot skill budget per message. Both values are design choices to compare in M3.
# New: skills the router picks for the latest message.
MAX_NEW_SKILLS_PER_TURN = 3
# Carried: skills picked on the previous turn that stay loaded, so the agent still has
# the guidance behind its earlier answer.
MAX_CARRIED_SKILLS = 2
# How many recent messages the routers read to interpret the latest one.
ROUTER_CONTEXT_MESSAGES = 4

# Browser origins allowed to call the API (comma-separated in FYNN_CORS_ORIGINS).
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("FYNN_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]

# Before bot: one expert agent per domain. Each topic skill declares its domain,
# so both bots draw on exactly the same skill text.
DOMAINS: dict[str, str] = {
    "score-and-reports": "Credit score & reports",
    "credit-products": "Credit-building products",
    "rent-and-bills": "Rent & bill reporting",
    "debt-and-collections": "Debt & collections",
}
