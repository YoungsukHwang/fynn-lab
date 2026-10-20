import importlib
import os
from pathlib import Path

import pytest

from fynn import config


def test_env_file_overrides_models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("FYNN_AGENT_MODEL=claude-test-agent\nFYNN_ROUTER_MODEL=claude-test-router\n")
    monkeypatch.setenv("FYNN_ENV_FILE", str(env_file))
    monkeypatch.delenv("FYNN_AGENT_MODEL", raising=False)
    monkeypatch.delenv("FYNN_ROUTER_MODEL", raising=False)
    try:
        importlib.reload(config)
        assert config.AGENT_MODEL == "claude-test-agent"
        assert config.ROUTER_MODEL == "claude-test-router"
    finally:
        # load_dotenv wrote these straight into os.environ; remove them before restoring config.
        os.environ.pop("FYNN_AGENT_MODEL", None)
        os.environ.pop("FYNN_ROUTER_MODEL", None)
        monkeypatch.undo()
        importlib.reload(config)


def test_shell_variables_win_over_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("FYNN_AGENT_MODEL=from-file\n")
    monkeypatch.setenv("FYNN_ENV_FILE", str(env_file))
    monkeypatch.setenv("FYNN_AGENT_MODEL", "from-shell")
    try:
        importlib.reload(config)
        assert config.AGENT_MODEL == "from-shell"
    finally:
        monkeypatch.undo()
        importlib.reload(config)
