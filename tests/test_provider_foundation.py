from __future__ import annotations

import os
import unittest
from unittest import mock

from providers.base import BaseLLMProvider, ConfigurationError
from providers.factory import ProviderFactory


class _RecordingLLM(BaseLLMProvider):
    def __init__(self, marker: str) -> None:
        self.marker = marker

    async def generate_script(self, topic: str, system_prompt: str, schema: dict) -> dict:
        return {"topic": topic, "marker": self.marker, "schema": schema}


class ProviderFoundationTests(unittest.TestCase):
    def test_factory_requires_an_explicit_selected_provider(self) -> None:
        factory: ProviderFactory[BaseLLMProvider] = ProviderFactory("LLM", "TEST_LLM_PROVIDER")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TEST_LLM_PROVIDER", None)
            with self.assertRaisesRegex(ConfigurationError, "Set TEST_LLM_PROVIDER"):
                factory.create()

    def test_factory_uses_only_the_selected_registered_strategy(self) -> None:
        factory: ProviderFactory[BaseLLMProvider] = ProviderFactory("LLM", "TEST_LLM_PROVIDER")
        factory.register("chosen", _RecordingLLM)
        factory.register("other", _RecordingLLM)

        with mock.patch.dict(os.environ, {"TEST_LLM_PROVIDER": "chosen"}):
            provider = factory.create(marker="selected")

        self.assertIsInstance(provider, _RecordingLLM)
        self.assertEqual(provider.marker, "selected")

    def test_factory_rejects_unknown_provider_without_substitution(self) -> None:
        factory: ProviderFactory[BaseLLMProvider] = ProviderFactory("LLM", "TEST_LLM_PROVIDER")
        factory.register("chosen", _RecordingLLM)

        with self.assertRaisesRegex(ConfigurationError, "Unknown LLM provider 'missing'"):
            factory.create("missing", marker="must-not-be-used")

    def test_factory_validates_the_selected_strategy_configuration(self) -> None:
        factory: ProviderFactory[BaseLLMProvider] = ProviderFactory("LLM", "TEST_LLM_PROVIDER")
        factory.register("chosen", _RecordingLLM, required_env=("TEST_LLM_API_KEY",))

        with mock.patch.dict(os.environ, {"TEST_LLM_PROVIDER": "chosen"}, clear=False):
            os.environ.pop("TEST_LLM_API_KEY", None)
            with self.assertRaisesRegex(ConfigurationError, "TEST_LLM_API_KEY"):
                factory.create(marker="must-not-be-used")

    def test_contracts_remain_abstract(self) -> None:
        with self.assertRaises(TypeError):
            BaseLLMProvider()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
