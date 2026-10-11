from __future__ import annotations

import hashlib
import asyncio
import json
from pathlib import Path

import pytest

from providers.sfx.local_manifest import LocalManifestSfxProvider
from services.sfx import SfxManifestResolver, SfxValidationError, validate_cue_sheet, write_attributions, write_sfx_cue_sheet


def _asset(tmp_path: Path, *, licence: str = "CC-BY-4.0", attribution: str = "Flow by Example Author") -> dict:
    sound = tmp_path / "flow.wav"
    sound.write_bytes(b"verified audio bytes")
    return {
        "asset_id": "wet_flow_004", "local_path": str(sound), "sha256": hashlib.sha256(sound.read_bytes()).hexdigest(),
        "source_url": "https://catalog.example/assets/wet_flow_004", "creator": "Example Author",
        "license": licence, "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "commercial_allowed": True, "attribution": attribution, "tags": ["wet", "flow", "organic"],
        "duration": 1.2, "lufs": -24.0,
    }


def _cue() -> dict:
    return {"cue_id": "cue_03", "block": 5, "start": 16.1, "end": 16.9, "reason": "Visible bicarbonate flow peaks", "asset_id": "wet_flow_004", "gain_db": -18, "fade_in": 0.03, "fade_out": 0.16}


def test_manifest_resolver_accepts_cc_by_and_ranks_matching_tag(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"assets": [asset]}), encoding="utf-8")
    assert SfxManifestResolver(manifest).resolve(["flow"]).asset_id == asset["asset_id"]


@pytest.mark.parametrize("licence", ["CC-BY-NC-4.0", "unknown"])
def test_manifest_resolver_rejects_noncommercial_or_unknown_licences(tmp_path: Path, licence: str) -> None:
    asset = _asset(tmp_path, licence=licence)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"assets": [asset]}), encoding="utf-8")
    with pytest.raises(SfxValidationError):
        SfxManifestResolver(manifest).assets()


def test_cc_by_requires_attribution_and_hash_matches(tmp_path: Path) -> None:
    asset = _asset(tmp_path, attribution="")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"assets": [asset]}), encoding="utf-8")
    with pytest.raises(SfxValidationError, match="attribution"):
        SfxManifestResolver(manifest).assets()


def test_cue_sheet_limits_cues_and_requires_physical_reason(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    assert validate_cue_sheet([_cue()], [asset])[0]["cue_id"] == "cue_03"
    bad = _cue() | {"reason": "Caption emphasis"}
    with pytest.raises(SfxValidationError, match="physical event"):
        validate_cue_sheet([bad], [asset])
    with pytest.raises(SfxValidationError, match="more than two"):
        validate_cue_sheet([_cue(), _cue() | {"cue_id": "two"}, _cue() | {"cue_id": "three"}], [asset])


def test_cue_persistence_and_cc_by_attributions(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    cue_path = write_sfx_cue_sheet(tmp_path / "run", [_cue()], [asset])
    payload = json.loads(cue_path.read_text(encoding="utf-8"))
    assert payload["assets"][0]["sha256"] == asset["sha256"]
    attribution_path = write_attributions(tmp_path / "run", [asset])
    assert "Flow by Example Author" in attribution_path.read_text(encoding="utf-8")


def test_local_provider_resolves_only_preverified_manifest_asset(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"assets": [asset]}), encoding="utf-8")
    provider = LocalManifestSfxProvider(manifest)
    result = asyncio.run(provider.resolve_asset({"tags": ["wet"]}, tmp_path / "cache"))
    assert result["asset_id"] == "wet_flow_004"


def test_mmaudio_provider_factory_and_resilient_catalog_fallback(tmp_path: Path) -> None:
    from providers.factory import get_sfx_provider
    from providers.sfx.mmaudio import MMAudioProvider

    provider = get_sfx_provider("mmaudio")
    assert isinstance(provider, MMAudioProvider)

    # Resolves via resilient CC0 catalog fallback when local execution is mocked/unavailable
    result = asyncio.run(provider.resolve_asset({"prompt": "liquid soap sliding on membrane", "tags": ["liquid", "slide"]}, tmp_path / "sfx_cache"))
    assert result["commercial_allowed"] is True
    assert result["license"] == "CC0-1.0"
    assert Path(result["local_path"]).is_file()
    assert hashlib.sha256(Path(result["local_path"]).read_bytes()).hexdigest() == result["sha256"]


def test_mmaudio_provider_reuses_existing_cache_file(tmp_path: Path) -> None:
    from providers.sfx.mmaudio import MMAudioProvider

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_wav = cache_dir / "custom_cue.wav"
    cached_wav.write_bytes(b"RIFFmockwavdata")

    provider = MMAudioProvider()
    result = asyncio.run(provider.resolve_asset({"asset_id": "custom_cue", "tags": ["whoosh"]}, cache_dir))
    assert result["asset_id"] == "custom_cue"
    assert result["local_path"] == str(cached_wav.resolve())


def test_elevenlabs_sfx_provider_factory_and_cache(tmp_path: Path) -> None:
    from providers.factory import get_sfx_provider
    from providers.sfx.elevenlabs import ElevenLabsSfxProvider

    provider = get_sfx_provider("elevenlabs", api_key="sk_mockkey1234567890abcdef")
    assert isinstance(provider, ElevenLabsSfxProvider)

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_wav = cache_dir / "eleven_cached.wav"
    cached_wav.write_bytes(b"RIFFmockelevenlabsdata")

    result = asyncio.run(provider.resolve_asset({"asset_id": "eleven_cached", "prompt": "pop"}, cache_dir))
    assert result["asset_id"] == "eleven_cached"
    assert result["local_path"] == str(cached_wav.resolve())


def test_detect_peak_transient_and_start_trim(tmp_path: Path) -> None:
    import struct
    import wave
    from services.sfx import detect_peak_transient

    wav_path = tmp_path / "test_hit.wav"
    framerate = 44100
    n_frames = framerate
    samples = [0] * n_frames
    peak_index = int(0.5 * framerate)
    samples[peak_index] = 30000

    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack(f"<{n_frames}h", *samples))

    detected = detect_peak_transient(wav_path)
    assert 0.49 <= detected <= 0.51

    import editor
    filter_stmts = editor.build_audio_filter(
        vo_index=1,
        music_index=None,
        sfx_inputs=[{
            "input_index": 2,
            "start": 1.0,
            "end": 1.35,
            "start_trim": 0.45,
            "gain_db": -1.0,
        }],
    )
    assert any("atrim=0.450:0.800" in stmt for stmt in filter_stmts)
    assert any("equalizer=f=250:t=q:w=1.5:g=-2.0" in stmt for stmt in filter_stmts)
    assert any("equalizer=f=4000:t=q:w=1.8:g=2.0" in stmt for stmt in filter_stmts)
    assert any("highpass=f=75" in stmt for stmt in filter_stmts)


def test_resolve_sfx_cues_translates_academic_prompt_and_enforces_natural_decay(tmp_path: Path):
    from types import SimpleNamespace
    from pipeline import resolve_sfx_cues
    from services.script_engine import Script

    class MockProvider:
        def __init__(self):
            self.last_query = None

        async def resolve_asset(self, query: dict, cache_dir: Path) -> dict:
            self.last_query = query
            mock_wav = cache_dir / f"{query.get('asset_id', 'mock')}.wav"
            mock_wav.parent.mkdir(parents=True, exist_ok=True)
            mock_wav.write_bytes(b"RIFFmockdata")
            return {
                "asset_id": query.get("asset_id", "mock_sfx"),
                "local_path": str(mock_wav),
                "sha256": hashlib.sha256(b"RIFFmockdata").hexdigest(),
                "source_url": "https://api.elevenlabs.io/v1/sound-generation#mock",
                "creator": "Mock",
                "license": "CC0-1.0",
                "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "commercial_allowed": True,
                "attribution": "",
                "tags": query.get("tags") or ["foley"],
                "duration": 1.0,
            }

    mock_prov = MockProvider()
    import pipeline
    orig_get_provider = pipeline.get_sfx_provider
    pipeline.get_sfx_provider = lambda *a, **kw: mock_prov

    try:
        ctx = SimpleNamespace(
            out_dir=tmp_path / "run_test",
            mode=SimpleNamespace(name="anatomical", max_sfx_cues=6),
            timeline=SimpleNamespace(target_duration=32.0, total_duration=32.0),
        )
        script = SimpleNamespace(
            shots=[],
            timeline=SimpleNamespace(target_duration=32.0, total_duration=32.0),
            editorial_plan={
                "sfx_cues": [{
                    "cue_id": "cue_academic_01",
                    "block": 1,
                    "start": 2.0,
                    "end": 2.35,  # 0.35s short cutoff
                    "reason": "freezing point depression caused by dissolved electrolytes",
                    "asset_id": "sfx_ice_test",
                }],
            },
        )
        resolved = asyncio.run(resolve_sfx_cues(ctx, script))
        assert len(resolved) == 1
        # Duration must be expanded to natural decay envelope (0.55s - 0.75s)
        dur = resolved[0]["end"] - resolved[0]["start"]
        assert 0.55 <= dur <= 0.75
        # Prompt sent to provider must be translated to tactile Foley
        assert mock_prov.last_query is not None
        assert "ice cracking snap" in mock_prov.last_query["prompt"] or "crystallization" in mock_prov.last_query["prompt"]
        assert "freezing point depression" not in mock_prov.last_query["prompt"]
    finally:
        pipeline.get_sfx_provider = orig_get_provider


def test_generate_mmaudio_sfx_handles_short_and_edge_shots(tmp_path: Path):
    from types import SimpleNamespace
    from pipeline import generate_mmaudio_sfx

    class MockProvider:
        async def resolve_asset(self, query: dict, cache_dir: Path) -> dict:
            mock_wav = cache_dir / f"{query.get('asset_id', 'mock')}.wav"
            mock_wav.parent.mkdir(parents=True, exist_ok=True)
            mock_wav.write_bytes(b"RIFFmockdata")
            return {
                "asset_id": query.get("asset_id", "mock_sfx"),
                "local_path": str(mock_wav),
                "sha256": hashlib.sha256(b"RIFFmockdata").hexdigest(),
                "source_url": "https://api.elevenlabs.io/v1/sound-generation#mock",
                "creator": "Mock",
                "license": "CC0-1.0",
                "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "commercial_allowed": True,
                "attribution": "",
                "tags": query.get("tags") or ["foley"],
                "duration": 1.0,
            }

    import pipeline
    orig_get_provider = pipeline.get_sfx_provider
    pipeline.get_sfx_provider = lambda *a, **kw: MockProvider()

    try:
        ctx = SimpleNamespace(
            out_dir=tmp_path / "run_edge",
            sfx_provider="elevenlabs",
            mode=SimpleNamespace(
                name="anatomical",
                max_sfx_cues=6,
                sfx_trigger_keywords=("fluid", "bubble", "valve", "crack", "snap"),
            ),
            timeline=SimpleNamespace(target_duration=12.0, total_duration=12.0),
        )
        # Block files
        blocks_dir = tmp_path / "blocks"
        blocks_dir.mkdir()
        b1 = blocks_dir / "b1.mp4"
        b2 = blocks_dir / "b2.mp4"
        b1.write_bytes(b"dummy")
        b2.write_bytes(b"dummy")

        # Shot 1 is ultra-short (<0.4s), Shot 2 is normal (4.0s)
        script = SimpleNamespace(
            shots=[
                SimpleNamespace(
                    block=1,
                    t_start=0.0,
                    t_end=0.2,  # Too short for Foley decay
                    presentation_mode="mechanism",
                    journey_phase="explore",
                    normalized_domain="mechanical",
                    proof_on_screen="micro bubble",
                    dominant_event="fluid bubble",
                    transition_kind="hard_cut",
                    impact_offset_seconds=0.1,
                ),
                SimpleNamespace(
                    block=2,
                    t_start=0.2,
                    t_end=4.2,  # Normal length
                    presentation_mode="mechanism",
                    journey_phase="explore",
                    normalized_domain="mechanical",
                    proof_on_screen="valve snap",
                    dominant_event="mechanical valve release",
                    transition_kind="hard_cut",
                    impact_offset_seconds=1.8,
                ),
            ],
            timeline=SimpleNamespace(target_duration=12.0, total_duration=12.0),
        )

        cues = asyncio.run(generate_mmaudio_sfx(ctx, script, [b1, b2]))
        # Block 1 was skipped because <0.4s; Block 2 succeeded
        assert len(cues) == 1
        assert cues[0]["block"] == 2
        dur = cues[0]["end"] - cues[0]["start"]
        assert 0.55 <= dur <= 0.75
        assert cues[0]["end"] > cues[0]["start"]
    finally:
        pipeline.get_sfx_provider = orig_get_provider



