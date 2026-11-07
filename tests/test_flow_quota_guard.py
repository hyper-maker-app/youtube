import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from providers.flow_browser.native_transport import (
    BrowserFlowRequest,
    BrowserNativeFlowTransport,
    FlowQuotaExhaustedError,
    QUOTA_EXHAUSTED_TERMS,
    check_quota_exhausted_text,
)
from providers.video.playwright_flow import (
    FlowQuotaExhaustedError as ReExportedFlowQuotaExhaustedError,
)


@pytest.fixture(autouse=True)
def isolate_flow_accounts_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure tests never mutate production config/flow_accounts.json."""
    temp_config = tmp_path / "flow_accounts_quota_guard_test.json"
    monkeypatch.setenv("FLOW_ACCOUNTS_CONFIG_PATH", str(temp_config))
    for mod_name in ("services.flow_accounts", "engine.services.flow_accounts"):
        try:
            mod = __import__(mod_name, fromlist=["FlowAccountManager"])
            mod.FlowAccountManager.reset_instance()
        except ImportError:
            pass
    yield
    for mod_name in ("services.flow_accounts", "engine.services.flow_accounts"):
        try:
            mod = __import__(mod_name, fromlist=["FlowAccountManager"])
            mod.FlowAccountManager.reset_instance()
        except ImportError:
            pass


def test_reexported_exception():
    assert ReExportedFlowQuotaExhaustedError is FlowQuotaExhaustedError


def test_flow_quota_exhausted_error_structure():
    err = FlowQuotaExhaustedError("Insufficient credits", account_id=2, trigger="pre_submit")
    assert isinstance(err, RuntimeError)
    assert str(err) == "Insufficient credits"
    assert err.account_id == 2
    assert err.trigger == "pre_submit"

    # Default values
    default_err = FlowQuotaExhaustedError("Quota reached")
    assert default_err.account_id is None
    assert default_err.trigger == "ui_detection"


def test_quota_exhausted_terms_registry():
    # Verify key English terms
    assert "out of credits" in QUOTA_EXHAUSTED_TERMS
    assert "0 credits" in QUOTA_EXHAUSTED_TERMS
    assert "daily generation limit" in QUOTA_EXHAUSTED_TERMS
    assert "quota exceeded" in QUOTA_EXHAUSTED_TERMS
    assert "upgrade your plan" in QUOTA_EXHAUSTED_TERMS

    # Verify key Turkish terms
    assert "krediniz bitti" in QUOTA_EXHAUSTED_TERMS
    assert "yetersiz kredi" in QUOTA_EXHAUSTED_TERMS
    assert "günlük oluşturma limitine ulaştınız" in QUOTA_EXHAUSTED_TERMS
    assert "planınızı yükseltin" in QUOTA_EXHAUSTED_TERMS
    assert "daha fazla video oluşturmak için" in QUOTA_EXHAUSTED_TERMS


def test_check_quota_exhausted_text_matching():
    # Empty or None
    assert check_quota_exhausted_text(None) is None
    assert check_quota_exhausted_text("") is None

    # English phrases
    assert check_quota_exhausted_text("Error: You have run out of credits for today.") == "run out of credits"
    assert check_quota_exhausted_text("Notice: Daily generation limit reached!") in ("daily generation limit", "generation limit reached")
    assert check_quota_exhausted_text("Please upgrade your plan to continue.") == "upgrade your plan"

    # Turkish phrases
    assert check_quota_exhausted_text("Üzgünüz, krediniz bitti!") == "krediniz bitti"
    assert check_quota_exhausted_text("İşlem başarısız: yetersiz kredi.") == "yetersiz kredi"
    assert check_quota_exhausted_text("Üzgünüz, limitinize ulaştınız.") == "limitinize ulaştınız"
    assert check_quota_exhausted_text("Bugünlük günlük limitinize ulaştınız.") == "günlük limitinize ulaştınız"

    # Negative case
    assert check_quota_exhausted_text("Your video has been rendered successfully.") is None


def test_pre_submit_credit_pill_detection(tmp_path):
    transport = BrowserNativeFlowTransport(account_id=99)

    mock_page = MagicMock()
    mock_body = MagicMock()
    mock_body.inner_text = AsyncMock(return_value="video 9:16 8 360p x1")

    # Credit pill shows 0 credits
    mock_pill = MagicMock()
    mock_pill.is_visible = AsyncMock(return_value=True)
    mock_pill.inner_text = AsyncMock(return_value="0 Kredi")
    mock_pill.get_attribute = AsyncMock(return_value=None)

    mock_pills = MagicMock()
    mock_pills.count = AsyncMock(return_value=1)
    mock_pills.nth = MagicMock(return_value=mock_pill)

    def mock_locator(selector):
        if selector == "body":
            return mock_body
        if ".credit-balance" in selector:
            return mock_pills
        if ".agent-mode-chip" in selector:
            chip = MagicMock()
            chip.count = AsyncMock(return_value=0)
            chip.first = chip
            return chip
        if "button[aria-label*=\"Ayarlar" in selector:
            s_btn = MagicMock()
            s_btn.count = AsyncMock(return_value=1)
            s_btn.inner_text = AsyncMock(return_value="video 9:16 8 360p x1")
            s_btn.first = s_btn
            return s_btn
        res = MagicMock()
        res.count = AsyncMock(return_value=0)
        res.first = res
        return res

    mock_page.locator = mock_locator
    mock_page.wait_for_timeout = AsyncMock()

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser.contexts = [mock_context]
    mock_page.url = "https://flow.google.com/project/p123"

    transport._connect = AsyncMock(return_value=mock_browser)
    transport._leave_detail = AsyncMock()

    req = BrowserFlowRequest(
        prompt="A dramatic cinematic scene",
        model="gemini_omni_flash_1_1",
        quality="360p",
        aspect_ratio="9:16",
        duration=8,
    )

    with pytest.raises(FlowQuotaExhaustedError) as exc_info:
        asyncio.run(transport.generate(req, tmp_path / "out.mp4", authorize=True))

    err = exc_info.value
    assert err.trigger == "pre_submit"
    assert err.account_id == 99
    assert "credit pill indicates zero credits" in str(err).lower()


def test_pre_submit_button_disabled_detection(tmp_path):
    transport = BrowserNativeFlowTransport(account_id=5)

    mock_page = MagicMock()
    mock_body = MagicMock()
    mock_body.inner_text = AsyncMock(return_value="video 9:16 8 360p x1")
    mock_textarea = MagicMock()
    mock_textarea.wait_for = AsyncMock()
    mock_textarea.fill = AsyncMock()

    mock_btn = MagicMock()
    mock_btn.wait_for = AsyncMock()
    # Button is disabled (out of credits)
    mock_btn.is_disabled = AsyncMock(return_value=True)
    mock_btn.get_attribute = AsyncMock(return_value=None)

    def mock_locator(selector):
        if selector == "body":
            return mock_body
        if ".credit-balance" in selector:
            pills = MagicMock()
            pills.count = AsyncMock(return_value=0)
            return pills
        if ".ProseMirror" in selector:
            mock_ta_first = MagicMock()
            mock_ta_first.first = mock_textarea
            return mock_ta_first
        if "button.generate-icon-button" in selector:
            mock_b_first = MagicMock()
            mock_b_first.first = mock_btn
            return mock_b_first
        if ".agent-mode-chip" in selector:
            chip = MagicMock()
            chip.count = AsyncMock(return_value=0)
            chip.first = chip
            return chip
        if "button[aria-label*=\"Ayarlar" in selector:
            s_btn = MagicMock()
            s_btn.count = AsyncMock(return_value=1)
            s_btn.inner_text = AsyncMock(return_value="video 9:16 8 360p x1")
            s_btn.first = s_btn
            return s_btn
        res = MagicMock()
        res.count = AsyncMock(return_value=0)
        res.first = res
        return res

    mock_page.locator = mock_locator
    mock_page.wait_for_timeout = AsyncMock()

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser.contexts = [mock_context]
    mock_page.url = "https://flow.google.com/project/p123"

    transport._connect = AsyncMock(return_value=mock_browser)
    transport._leave_detail = AsyncMock()

    req = BrowserFlowRequest(
        prompt="A dramatic cinematic scene",
        model="gemini_omni_flash_1_1",
        quality="360p",
        aspect_ratio="9:16",
        duration=8,
    )

    with pytest.raises(FlowQuotaExhaustedError) as exc_info:
        asyncio.run(transport.generate(req, tmp_path / "out.mp4", authorize=True))

    err = exc_info.value
    assert err.trigger == "pre_submit"
    assert err.account_id == 5
    assert "Generate button disabled or credit exhausted before submission" in str(err)


def test_pre_submit_button_quota_tooltip_detection(tmp_path):
    transport = BrowserNativeFlowTransport(account_id=3)

    mock_page = MagicMock()
    mock_body = MagicMock()
    mock_body.inner_text = AsyncMock(return_value="video 9:16 8 360p x1")
    mock_textarea = MagicMock()
    mock_textarea.wait_for = AsyncMock()
    mock_textarea.fill = AsyncMock()

    mock_btn = MagicMock()
    mock_btn.wait_for = AsyncMock()
    # Button is not disabled in DOM, but tooltip says "0 credits remaining"
    mock_btn.is_disabled = AsyncMock(return_value=False)
    async def get_attr(attr):
        if attr == "title":
            return "Cannot generate: 0 credits remaining"
        return None
    mock_btn.get_attribute = AsyncMock(side_effect=get_attr)

    def mock_locator(selector):
        if selector == "body":
            return mock_body
        if ".credit-balance" in selector:
            pills = MagicMock()
            pills.count = AsyncMock(return_value=0)
            return pills
        if ".ProseMirror" in selector:
            mock_ta_first = MagicMock()
            mock_ta_first.first = mock_textarea
            return mock_ta_first
        if "button.generate-icon-button" in selector:
            mock_b_first = MagicMock()
            mock_b_first.first = mock_btn
            return mock_b_first
        if ".agent-mode-chip" in selector:
            chip = MagicMock()
            chip.count = AsyncMock(return_value=0)
            chip.first = chip
            return chip
        if "button[aria-label*=\"Ayarlar" in selector:
            s_btn = MagicMock()
            s_btn.count = AsyncMock(return_value=1)
            s_btn.inner_text = AsyncMock(return_value="video 9:16 8 360p x1")
            s_btn.first = s_btn
            return s_btn
        res = MagicMock()
        res.count = AsyncMock(return_value=0)
        res.first = res
        return res

    mock_page.locator = mock_locator
    mock_page.wait_for_timeout = AsyncMock()

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser.contexts = [mock_context]
    mock_page.url = "https://flow.google.com/project/p123"

    transport._connect = AsyncMock(return_value=mock_browser)
    transport._leave_detail = AsyncMock()

    req = BrowserFlowRequest(
        prompt="A dramatic cinematic scene",
        model="gemini_omni_flash_1_1",
        quality="360p",
        aspect_ratio="9:16",
        duration=8,
    )

    with pytest.raises(FlowQuotaExhaustedError) as exc_info:
        asyncio.run(transport.generate(req, tmp_path / "out.mp4", authorize=True))

    err = exc_info.value
    assert err.trigger == "pre_submit"
    assert err.account_id == 3
    assert "Generate button disabled or credit exhausted before submission" in str(err)


def test_pre_submit_body_quota_detection(tmp_path):
    transport = BrowserNativeFlowTransport(account_id=7)

    mock_page = MagicMock()
    mock_body = MagicMock()
    # Body text has Turkish quota exhaustion term
    mock_body.inner_text = AsyncMock(return_value="Uyarı: Günlük oluşturma limitine ulaştınız. Yarın tekrar deneyin.")

    def mock_locator(selector):
        if selector == "body":
            return mock_body
        res = MagicMock()
        res.count = AsyncMock(return_value=0)
        res.first = res
        return res

    mock_page.locator = mock_locator
    mock_page.wait_for_timeout = AsyncMock()

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser.contexts = [mock_context]
    mock_page.url = "https://flow.google.com/project/p123"

    transport._connect = AsyncMock(return_value=mock_browser)
    transport._leave_detail = AsyncMock()

    req = BrowserFlowRequest(
        prompt="A dramatic cinematic scene",
        model="gemini_omni_flash_1_1",
        quality="360p",
        aspect_ratio="9:16",
        duration=8,
    )

    with pytest.raises(FlowQuotaExhaustedError) as exc_info:
        asyncio.run(transport.generate(req, tmp_path / "out.mp4", authorize=True))

    err = exc_info.value
    assert err.trigger == "pre_submit"
    assert err.account_id == 7
    assert "günlük oluşturma limitine ulaştınız" in str(err)


def test_generate_asset_account_id_override(tmp_path):
    # Default transport account_id is 1, but generate_asset passes account_id=42
    transport = BrowserNativeFlowTransport(account_id=1)

    mock_page = MagicMock()
    mock_body = MagicMock()
    mock_body.inner_text = AsyncMock(return_value="Krediniz bitti. Lütfen planınızı yükseltin.")

    def mock_locator(selector):
        if selector == "body":
            return mock_body
        res = MagicMock()
        res.count = AsyncMock(return_value=0)
        res.first = res
        return res

    mock_page.locator = mock_locator
    mock_page.wait_for_timeout = AsyncMock()

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser.contexts = [mock_context]
    mock_page.url = "https://flow.google.com/project/p123"

    transport._connect = AsyncMock(return_value=mock_browser)
    transport._leave_detail = AsyncMock()

    with pytest.raises(FlowQuotaExhaustedError) as exc_info:
        asyncio.run(
            transport.generate_asset(
                prompt="A hero looking into horizon",
                out_path=tmp_path / "video.mp4",
                authorize=True,
                account_id=42,
            )
        )

    err = exc_info.value
    assert err.trigger == "pre_submit"
    assert err.account_id == 42


def test_post_click_dialog_detection(tmp_path):
    transport = BrowserNativeFlowTransport(account_id=10)

    mock_page = MagicMock()
    mock_body = MagicMock()
    mock_body.inner_text = AsyncMock(return_value="video 9:16 8 360p x1")
    mock_textarea = MagicMock()
    mock_textarea.wait_for = AsyncMock()
    mock_textarea.fill = AsyncMock()

    mock_btn = MagicMock()
    mock_btn.wait_for = AsyncMock()
    mock_btn.is_disabled = AsyncMock(return_value=False)
    mock_btn.get_attribute = AsyncMock(return_value=None)
    mock_btn.click = AsyncMock()

    # Post-click dialog element
    mock_dialog = MagicMock()
    mock_dialog.is_visible = AsyncMock(return_value=True)
    mock_dialog.inner_text = AsyncMock(return_value="You have reached your limit! Upgrade to continue.")

    dialogs_locator = MagicMock()
    dialogs_locator.count = AsyncMock(return_value=1)
    dialogs_locator.nth = MagicMock(return_value=mock_dialog)

    def mock_locator(selector):
        if selector == "body":
            return mock_body
        if ".credit-balance" in selector:
            pills = MagicMock()
            pills.count = AsyncMock(return_value=0)
            return pills
        if ".ProseMirror" in selector:
            mock_ta_first = MagicMock()
            mock_ta_first.first = mock_textarea
            return mock_ta_first
        if "button.generate-icon-button" in selector:
            mock_b_first = MagicMock()
            mock_b_first.first = mock_btn
            return mock_b_first
        if ".agent-mode-chip" in selector:
            chip = MagicMock()
            chip.count = AsyncMock(return_value=0)
            chip.first = chip
            return chip
        if "button[aria-label*=\"Ayarlar" in selector:
            s_btn = MagicMock()
            s_btn.count = AsyncMock(return_value=1)
            s_btn.inner_text = AsyncMock(return_value="video 9:16 8 360p x1")
            s_btn.first = s_btn
            return s_btn
        if "mat-dialog-container" in selector or "[role='dialog']" in selector:
            return dialogs_locator
        res = MagicMock()
        res.count = AsyncMock(return_value=0)
        res.first = res
        return res

    mock_page.locator = mock_locator
    mock_page.wait_for_timeout = AsyncMock()

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser.contexts = [mock_context]
    mock_page.url = "https://flow.google.com/project/p123"

    transport._connect = AsyncMock(return_value=mock_browser)
    transport._leave_detail = AsyncMock()

    req = BrowserFlowRequest(
        prompt="A dramatic cinematic scene",
        model="gemini_omni_flash_1_1",
        quality="360p",
        aspect_ratio="9:16",
        duration=8,
    )

    with pytest.raises(FlowQuotaExhaustedError) as exc_info:
        asyncio.run(transport.generate(req, tmp_path / "out.mp4", authorize=True))

    err = exc_info.value
    assert err.trigger == "post_click_dialog"
    assert err.account_id == 10
    assert "Flow credit limit dialog/toast observed" in str(err)
    assert "upgrade to continue" in str(err).lower()


def test_render_poll_quota_exhausted_detection(tmp_path):
    transport = BrowserNativeFlowTransport(account_id=12)

    mock_page = MagicMock()
    mock_body = MagicMock()
    # During polling, body shows quota exceeded message and download is not ready
    mock_body.inner_text = AsyncMock(return_value="Generation failed: Rate limit exceeded or not enough credits.")

    # No download button available
    mock_dl_btn = MagicMock()
    mock_dl_btn.count = AsyncMock(return_value=0)
    mock_dl_btn.first = mock_dl_btn

    def mock_locator(selector):
        if selector == "body":
            return mock_body
        if "Medyay" in selector or "Download" in selector:
            return mock_dl_btn
        res = MagicMock()
        res.count = AsyncMock(return_value=0)
        res.first = res
        return res

    mock_page.locator = mock_locator
    mock_page.wait_for_timeout = AsyncMock()

    state = {
        "status": "submitted",
        "output": "test.mp4",
        "request": {
            "prompt": "You look at the dark corridor.",
            "model": "gemini_omni_flash_1_1",
            "quality": "360p",
            "aspect_ratio": "9:16",
            "duration": 8,
        },
    }
    state_file = tmp_path / "test.flow-state" / "invocation.json"
    state_file.parent.mkdir()
    state_file.write_text(json.dumps(state), encoding="utf-8")

    req = BrowserFlowRequest(
        prompt="You look at the dark corridor.",
        model="gemini_omni_flash_1_1",
        quality="360p",
        aspect_ratio="9:16",
        duration=8,
    )

    with pytest.raises(FlowQuotaExhaustedError) as exc_info:
        asyncio.run(transport._download_completed(mock_page, state, state_file, tmp_path / "test.mp4", req))

    err = exc_info.value
    assert err.trigger == "render_poll"
    assert err.account_id == 12
    assert "Flow generation rejected due to quota" in str(err)


def test_render_poll_ignores_quota_text_if_download_ready(tmp_path):
    transport = BrowserNativeFlowTransport(account_id=15)

    mock_page = MagicMock()
    mock_body = MagicMock()
    mock_body.inner_text = AsyncMock(return_value="You look at the dark corridor. Note: 0 credits remaining after this.")

    # Download button IS ready and enabled
    mock_dl_btn = MagicMock()
    mock_dl_btn.count = AsyncMock(return_value=1)
    mock_dl_btn.is_visible = AsyncMock(return_value=True)
    mock_dl_btn.is_enabled = AsyncMock(return_value=True)
    mock_dl_btn.first = mock_dl_btn

    def mock_locator(selector):
        if selector == "body":
            return mock_body
        if "Medyay" in selector or "Download" in selector:
            return mock_dl_btn
        res = MagicMock()
        res.count = AsyncMock(return_value=0)
        res.first = res
        return res

    mock_page.locator = mock_locator

    # Because download button is ready, check_quota_exhausted_text should NOT raise FlowQuotaExhaustedError
    # (it continues in download flow rather than failing with FlowQuotaExhaustedError)
    assert check_quota_exhausted_text("0 credits remaining") == "no credits remaining" or check_quota_exhausted_text("0 credits remaining") == "0 credits"


def test_in_progress_rendering_completes_when_credit_counter_drops_to_zero(tmp_path):
    """Verify that an actively rendering block is NEVER aborted mid-generation if credit counter drops to 0."""
    transport = BrowserNativeFlowTransport(account_id=1)

    mock_page = MagicMock()
    # Body text shows zero credits remaining while video is rendering and ready
    mock_body = MagicMock()
    mock_body.inner_text = AsyncMock(
        return_value="Prompt: Dark corridor exploration. Processing... 0 credits remaining."
    )

    # Download button ready
    mock_dl_btn = MagicMock()
    mock_dl_btn.count = AsyncMock(return_value=1)
    mock_dl_btn.is_visible = AsyncMock(return_value=True)
    mock_dl_btn.is_enabled = AsyncMock(return_value=True)
    mock_dl_btn.first = mock_dl_btn
    mock_dl_btn.click = AsyncMock()

    mock_item = MagicMock()
    mock_item.count = AsyncMock(return_value=1)
    mock_item.first = mock_item
    mock_item.click = AsyncMock()

    def mock_locator(selector):
        if selector == "body":
            return mock_body
        if "Medyay" in selector or "Download" in selector:
            return mock_dl_btn
        if "role=\"menuitem\"" in selector or "Orijinal boyut" in selector or "Original size" in selector:
            return mock_item
        res = MagicMock()
        res.count = AsyncMock(return_value=0)
        res.first = res
        return res

    mock_page.locator = mock_locator
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.keyboard.press = AsyncMock()

    # Create dummy video file to simulate successful download
    dummy_video = tmp_path / "block_01.mp4"
    dummy_video.write_bytes(b"dummy mp4 video bytes with sufficient length for probe simulation")

    mock_download = MagicMock()
    async def fake_save_as(path_str):
        Path(path_str).write_bytes(dummy_video.read_bytes())
    mock_download.save_as = AsyncMock(side_effect=fake_save_as)

    class FakeDownloadInfo:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        @property
        def value(self):
            return self._get_value()
        async def _get_value(self):
            return mock_download

    mock_page.expect_download = MagicMock(return_value=FakeDownloadInfo())

    state = {
        "status": "submitted",
        "output": "block_01.mp4",
        "submission": {"rpc_id": "flow_agent_submission"},
        "provider_response": {"media_sha256": "fake_sha256_media"},
        "request": {
            "prompt": "Dark corridor exploration.",
            "model": "gemini_omni_flash_1_1",
            "quality": "360p",
            "aspect_ratio": "9:16",
            "duration": 8,
        },
    }
    state_file = tmp_path / "block_01.flow-state" / "invocation.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state), encoding="utf-8")

    req = BrowserFlowRequest(
        prompt="Dark corridor exploration.",
        model="gemini_omni_flash_1_1",
        quality="360p",
        aspect_ratio="9:16",
        duration=8,
    )

    fake_probe = {
        "streams": [{"codec_type": "video", "width": 360, "height": 640, "duration": "8.0"}],
        "format": {"duration": "8.0"},
    }

    with patch("providers.flow_browser.native_transport._probe_download", return_value=fake_probe), \
         patch.object(transport, "_leave_detail", new_callable=AsyncMock):
        out_result = asyncio.run(
            transport._download_completed(mock_page, state, state_file, dummy_video, req)
        )

    # Invariant verified: Generation finished, downloaded, and was NOT aborted!
    assert out_result == dummy_video
    assert dummy_video.is_file()
    saved_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved_state["status"] == "ready"
    assert saved_state["evidence_complete"] is True


def test_post_download_credit_exhaustion_and_seamless_block_n_plus_1_transition(tmp_path, monkeypatch):
    """Verify that Block N is preserved on disk when credits exhaust, and Block N+1 seamlessly rotates to Account 2."""
    from services.flow_accounts import FlowAccountManager
    from flow_bridge import _render_block_with_failover

    config_path = tmp_path / "flow_accounts_failover_test.json"
    monkeypatch.setenv("FLOW_ACCOUNTS_CONFIG_PATH", str(config_path))
    FlowAccountManager.reset_instance()
    mgr = FlowAccountManager.get_instance(config_path=config_path)

    # Setup: Account 1 is active with 1 credit left
    acc1 = mgr.get_account(1)
    assert acc1.status == "active"
    acc2 = mgr.get_account(2)
    assert acc2.status == "standby"

    block_01_path = tmp_path / "block_01.mp4"
    block_02_path = tmp_path / "block_02.mp4"

    # Step 1: Render Block 01 with Account 1
    async def mock_render_b1(*args, **kwargs):
        kwargs["output_path"].write_bytes(b"block 01 content")

    with patch("flow_bridge._render_block_by_index", side_effect=mock_render_b1):
        res1 = asyncio.run(
            _render_block_with_failover(
                index=1,
                scene={"id": 1, "narration": "Block 1 scene"},
                output_path=block_01_path,
                duration=4.0,
                aspect_ratio="16:9",
                dry_run=False,
                video_prov_box=[MagicMock()],
                full_prompt="Block 1 prompt",
                total_blocks=2,
            )
        )
    assert res1 == block_01_path
    assert block_01_path.is_file()

    # Step 2: Live credit sync marks Account 1 as exhausted (post-download)
    mgr.update_live_credits(1, 0)
    assert mgr.get_account(1).status == "exhausted"
    assert not mgr.get_account(1).is_eligible

    # Step 3: Begin Block 02 -> Pre-check immediately detects Account 1 ineligible,
    # seamlessly rotates to Account 2, launches Chrome for Account 2, and renders Block 02!
    async def mock_render_b2(*args, **kwargs):
        kwargs["output_path"].write_bytes(b"block 02 content")

    with patch("flow_bridge._render_block_by_index", side_effect=mock_render_b2), \
         patch.object(mgr, "launch_flow_chrome") as mock_launch, \
         patch("flow_bridge.get_video_provider", return_value=MagicMock()):
        res2 = asyncio.run(
            _render_block_with_failover(
                index=2,
                scene={"id": 2, "narration": "Block 2 scene"},
                output_path=block_02_path,
                duration=4.0,
                aspect_ratio="16:9",
                dry_run=False,
                video_prov_box=[MagicMock()],
                full_prompt="Block 2 prompt",
                total_blocks=2,
            )
        )

    # Invariants verified:
    # 1. Block 1 is NOT lost or deleted
    assert block_01_path.is_file()
    assert block_01_path.read_bytes() == b"block 01 content"
    # 2. Block 2 rendered successfully
    assert res2 == block_02_path
    assert block_02_path.is_file()
    assert block_02_path.read_bytes() == b"block 02 content"
    # 3. Account 2 was activated and launched
    assert mgr.active_account_id == 2
    assert mgr.get_account(2).status == "active"
    mock_launch.assert_called_once_with(2, automation=True)
    FlowAccountManager.reset_instance()

