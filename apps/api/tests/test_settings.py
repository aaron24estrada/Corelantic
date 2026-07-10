"""The suite reads its configuration from nowhere but itself.

`Settings` loads from `apps/api/.env` and from every `CORELANTIC_API_*` process variable. Both
are ambient, and both used to reach the tests: `make check` went red for anyone who followed
the setup in docs/status.md, and the tests that stayed green passed only because someone's file
happened to hold the value they asserted (#48).

These are the canaries. If the autouse fixture in conftest.py ever stops working, they fail here
— naming the cause — rather than somewhere confusing three files away.
"""

import os

from app.core.config import ENV_PREFIX, Settings


def test_no_ambient_variables_survive_into_a_test() -> None:
    assert [key for key in os.environ if key.startswith(ENV_PREFIX)] == []


def test_settings_ignore_the_developers_env_file() -> None:
    # apps/api/.env sets CORELANTIC_API_DATA_SOURCE=fixture, as the setup docs instruct. A test
    # asserting the *unset* default must not see it.
    assert Settings().data_source == "azure_sql"
    assert Settings().internal_api_key is None
    assert Settings().azure_sql_server is None


def test_a_test_may_still_set_a_variable_for_itself() -> None:
    # Hermetic means "nothing arrives uninvited", not "nothing can be configured".
    assert Settings(data_source="fixture").data_source == "fixture"


def test_the_env_prefix_is_the_one_the_suite_strips() -> None:
    # Guards the two from drifting apart: a renamed prefix would let the machine back in.
    assert Settings.model_config["env_prefix"] == ENV_PREFIX
