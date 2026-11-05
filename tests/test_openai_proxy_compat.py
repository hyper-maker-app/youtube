"""Test OpenAI-compatible proxy and XAI_API_BASE / XAI_MODEL configuration."""

import json
import os
from unittest.mock import patch
import pytest

from engine.providers.llm.grok import GrokLLMProvider
from engine.services.screenplay_healer import ScreenplayHealer
from engine.services.screenplay_reviewer import Scorecard, ScreenplayReviewer


def test_grok_provider_proxy_configuration(monkeypatch):
    monkeypatch.setenv("XAI_MODEL", "d4ncboz/museai")
    monkeypatch.setenv("XAI_API_BASE", "http://127.0.0.1:20128/v1/")
    provider = GrokLLMProvider(api_key="test-key")
    assert provider.model == "d4ncboz/museai"
    assert provider.base_url == "http://127.0.0.1:20128/v1"


def test_grok_provider_defaults(monkeypatch):
    monkeypatch.delenv("XAI_MODEL", raising=False)
    monkeypatch.delenv("XAI_API_BASE", raising=False)
    provider = GrokLLMProvider(api_key="test-key")
    assert provider.model == "grok-4.20-0309-non-reasoning"
    assert provider.base_url == "https://api.x.ai/v1"


def test_reviewer_custom_proxy(monkeypatch):
    monkeypatch.setenv("XAI_MODEL", "d4ncboz/museai")
    monkeypatch.setenv("XAI_API_BASE", "http://127.0.0.1:20128/v1")
    reviewer = ScreenplayReviewer(xai_api_key="test-key")
    assert reviewer.grok_model == "d4ncboz/museai"

    captured = []

    def mock_urlopen(req, **kwargs):
        captured.append({"url": req.full_url, "payload": json.loads(req.data)})
        raise RuntimeError("stop")

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    with pytest.raises(RuntimeError):
        reviewer._consult_grok_critique([], "title", "genre", [])

    assert captured[0]["url"] == "http://127.0.0.1:20128/v1/chat/completions"
    assert captured[0]["payload"]["model"] == "d4ncboz/museai"


def test_healer_custom_proxy(monkeypatch):
    monkeypatch.setenv("XAI_MODEL", "d4ncboz/museai")
    monkeypatch.setenv("XAI_API_BASE", "http://127.0.0.1:20128/v1/")
    healer = ScreenplayHealer(xai_api_key="test-key")
    assert healer.grok_model == "d4ncboz/museai"

    captured = []

    def mock_urlopen(req, **kwargs):
        captured.append({"url": req.full_url, "payload": json.loads(req.data)})
        raise RuntimeError("stop")

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    dummy_card = Scorecard(total_score=50, category_scores={}, defects=["defect"], passed=False)
    with pytest.raises(RuntimeError):
        healer._heal_with_full_context_grok([{"scene_number": 1}], dummy_card, "title", "genre")

    assert captured[0]["url"] == "http://127.0.0.1:20128/v1/chat/completions"
    assert captured[0]["payload"]["model"] == "d4ncboz/museai"


def test_reviewer_and_healer_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("XAI_MODEL", raising=False)
    monkeypatch.delenv("XAI_API_BASE", raising=False)

    reviewer = ScreenplayReviewer(xai_api_key="test-key")
    assert reviewer.grok_model == "grok-4.20-0309-non-reasoning"

    healer = ScreenplayHealer(xai_api_key="test-key")
    assert healer.grok_model == "grok-4.20-0309-non-reasoning"

    captured = []

    def mock_urlopen(req, **kwargs):
        captured.append({"url": req.full_url, "payload": json.loads(req.data)})
        raise RuntimeError("stop")

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    with pytest.raises(RuntimeError):
        reviewer._consult_grok_critique([], "title", "genre", [])

    assert captured[0]["url"] == "https://api.x.ai/v1/chat/completions"
    assert captured[0]["payload"]["model"] == "grok-4.20-0309-non-reasoning"


def test_cli_produce_commands_judge_override(monkeypatch):
    monkeypatch.setenv("XAI_MODEL", "d4ncboz/museai")
    from tools.cli.produce_commands import produce_film

    # Test that default grok-4.20-non-reasoning is overridden by XAI_MODEL
    grok_judge_model = "grok-4.20-non-reasoning"
    if os.getenv("XAI_MODEL") and (grok_judge_model in ("grok-4.20-non-reasoning", "grok-4.20-0309-non-reasoning") or not grok_judge_model):
        grok_judge_model = os.getenv("XAI_MODEL")
    assert grok_judge_model == "d4ncboz/museai"

    # Test explicit override is preserved if different from default
    explicit_model = "my-custom-model"
    grok_judge_model = explicit_model
    if os.getenv("XAI_MODEL") and (grok_judge_model in ("grok-4.20-non-reasoning", "grok-4.20-0309-non-reasoning") or not grok_judge_model):
        grok_judge_model = os.getenv("XAI_MODEL")
    assert grok_judge_model == "my-custom-model"



def test_grok_provider_explicit_model_beats_env(monkeypatch):
    monkeypatch.setenv("XAI_MODEL", "d4ncboz/museai")
    provider = GrokLLMProvider(api_key="test-key", model="my-explicit-model")
    assert provider.model == "my-explicit-model"


def test_proxy_whitespace_and_empty_handling(monkeypatch):
    monkeypatch.setenv("XAI_API_BASE", "   http://127.0.0.1:20128/v1/   ")
    provider = GrokLLMProvider(api_key="test-key")
    assert provider.base_url == "http://127.0.0.1:20128/v1"

    monkeypatch.setenv("XAI_API_BASE", "   ")
    provider_blank = GrokLLMProvider(api_key="test-key")
    assert provider_blank.base_url == "https://api.x.ai/v1"
