"""Per-user (bring-your-own-keys) client construction in LLMClientFactory."""
from app.llm.chain_client import ChainLLMClient
from app.llm.client_factory import LLMClientFactory
from app.llm.openai_compat_client import OpenAICompatibleClient


def test_single_user_provider_returns_one_client():
    client = LLMClientFactory.create("interactive", user_keys={"nvidia": ["uk-1"]})
    assert isinstance(client, OpenAICompatibleClient)


def test_multiple_user_providers_build_a_chain_in_profile_order():
    client = LLMClientFactory.create(
        "interactive", user_keys={"mistral": ["uk-m"], "nvidia": ["uk-n"]}
    )
    assert isinstance(client, ChainLLMClient)
    # INTERACTIVE_ORDER lists nvidia before mistral.
    assert len(client._clients) == 2
    assert client._clients[0]._provider == "nvidia"
    assert client._clients[1]._provider == "mistral"


def test_user_clients_are_not_cached():
    a = LLMClientFactory.create("interactive", user_keys={"nvidia": ["uk-1"]})
    b = LLMClientFactory.create("interactive", user_keys={"nvidia": ["uk-1"]})
    assert a is not b  # fresh per call, never the shared process cache


def test_make_user_client_returns_none_without_keys():
    # The route-facing contract: no usable keys -> None, so callers pass client=None
    # and the LLM classes use the shared default pool (unchanged behavior).
    from app.llm.user_clients import make_user_client

    assert make_user_client("interactive", ({}, False)) is None
    assert make_user_client("interactive", ({"nvidia": ["uk-1"]}, False)) is not None
