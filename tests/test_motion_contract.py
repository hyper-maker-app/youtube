"""Offline regression tests for the production motion payload and duration contracts."""
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from engine.services import remotion_bridge as bridge


def telemetry_payload():
    return dict(metricName="Test", unit="units", classification="Test", timestampLabel="Test",
                dataPoints=[0, 10], thresholdValue=5, thresholdLabel="Test", currentStatus="Test", summaryMetrics=[])


def test_missing_payload_does_not_inherit_scenario_defaults():
    with pytest.raises(ValueError, match="requires string field"):
        bridge.validate_broll_payload("telemetry", {})


@pytest.mark.parametrize("points", [[], [1], [1, float("nan")], [1, True]])
def test_invalid_telemetry_points_rejected(points):
    payload = telemetry_payload()
    payload["dataPoints"] = points
    with pytest.raises(ValueError, match="dataPoints"):
        bridge.validate_broll_payload("telemetry", payload)


def test_explicit_duration_overrides_composition_and_props_are_preserved(tmp_path):
    output = tmp_path / "clip.mp4"
    payload = telemetry_payload()
    def fake_run(command, **kwargs):
        assert "--duration=540" in command
        assert "--frames=0-539" in command
        props = next(value.split("=", 1)[1] for value in command if value.startswith("--props="))
        assert json.loads(Path(props).read_text(encoding="utf-8")) == payload
        output.write_bytes(b"test-render-output")
        return subprocess.CompletedProcess(command, 0, "", "")
    with patch.object(bridge, "resolve_npx", return_value="npx"), patch.object(bridge, "resolve_browser_executable", return_value=None), patch.object(bridge.subprocess, "run", side_effect=fake_run):
        assert bridge.render_remotion_broll("telemetry", payload, output, duration_seconds=9) == output


@pytest.mark.parametrize("seconds", [0, -1, float("nan"), float("inf")])
def test_nonpositive_duration_rejected(tmp_path, seconds):
    with pytest.raises(ValueError, match="duration_seconds"):
        bridge.render_remotion_broll("telemetry", telemetry_payload(), tmp_path / "clip.mp4", duration_seconds=seconds)


def test_tile_cache_survives_a_second_render_without_network(tmp_path, monkeypatch):
    import io
    from PIL import Image
    image = io.BytesIO()
    Image.new('RGB', (256, 256), 'black').save(image, format='PNG')
    raw = image.getvalue()
    monkeypatch.setenv('REMOTION_TILE_CACHE_DIR', str(tmp_path / 'tiles'))
    payload = {'center': [0, 0], 'zoom': 0, 'tileSource': 'https://offline.test/{z}/{x}/{y}.png'}
    with patch('urllib.request.urlopen', side_effect=lambda *a, **k: io.BytesIO(raw)) as download:
        first = bridge.cache_map_tiles(payload, 4, 256, 256)
        assert download.call_count == 1
    with patch('urllib.request.urlopen', side_effect=AssertionError('Cache must avoid network')):
        second = bridge.cache_map_tiles(payload, 4, 256, 256)
    assert first == second
    assert len(list((tmp_path / 'tiles').glob('*.png'))) == 1
    assert next(iter(second['tileCache'].values())).startswith('data:image/png;base64,')
