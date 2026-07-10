"""The suite reads its configuration from nowhere but itself.

`Settings` loads from `apps/api/.env` and from every `CORELANTIC_API_*` process variable. Both
are ambient, and both used to reach the tests: `make check` went red for anyone who followed
the setup in docs/status.md, and the tests that stayed green passed only because someone's file
happened to hold the value they asserted (#48).

These are the canaries. If the autouse fixture in conftest.py ever stops working, they fail here
— naming the cause — rather than somewhere confusing three files away.
"""

import os
from pathlib import Path

import pytest

from app.core.config import ENV_PREFIX, Settings


def test_no_ambient_variables_survive_into_a_test() -> None:
    assert [key for key in os.environ if key.startswith(ENV_PREFIX)] == []


def test_settings_ignore_a_dotenv_file_that_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Written against a `.env` we create, not the one the developer happens to have.

    Asserting only against `apps/api/.env` would pass vacuously wherever that file is absent —
    on CI, or on a fresh clone — which is exactly where the regression would slip back in.
    """

    (tmp_path / ".env").write_text(
        f"{ENV_PREFIX}DATA_SOURCE=fixture\n{ENV_PREFIX}INTERNAL_API_KEY=leaked\n"
    )
    monkeypatch.chdir(tmp_path)

    assert Settings().data_source == "azure_sql"  # the class default, not the file
    assert Settings().internal_api_key is None


def test_settings_ignore_the_developers_env_file() -> None:
    # apps/api/.env sets CORELANTIC_API_DATA_SOURCE=fixture, as the setup docs instruct. A test
    # asserting the *unset* default must not see it. Vacuous where the file is absent, which is
    # why the tmp_path case above exists too.
    assert Settings().data_source == "azure_sql"
    assert Settings().internal_api_key is None
    assert Settings().azure_sql_server is None


def test_a_test_may_still_set_a_variable_for_itself() -> None:
    # Hermetic means "nothing arrives uninvited", not "nothing can be configured".
    assert Settings(data_source="fixture").data_source == "fixture"


def test_the_env_prefix_is_the_one_the_suite_strips() -> None:
    # Guards the two from drifting apart: a renamed prefix would let the machine back in.
    assert Settings.model_config["env_prefix"] == ENV_PREFIX


@pytest.fixture(scope="module")
def settings_built_by_a_module_scoped_fixture() -> Settings:
    return Settings()


def test_isolation_runs_before_module_scoped_fixtures(
    settings_built_by_a_module_scoped_fixture: Settings,
) -> None:
    """The isolation must be session-scoped, not merely autouse.

    pytest builds a module-scoped fixture before a function-scoped one, so a function-scoped
    guard would let modules like test_fixture.py load their registry from an ambient
    `semantic_dir` first — which is exactly what happened, and only showed up under a hostile
    environment variable rather than under a `.env`.
    """

    assert settings_built_by_a_module_scoped_fixture.data_source == "azure_sql"
    assert settings_built_by_a_module_scoped_fixture.semantic_dir.name == "semantic"
