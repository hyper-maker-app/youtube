import pytest

from engine.providers.voice.deepgram_aura import DeepgramAuraProvider
from providers.base import ProviderError


def test_alignment_validates_against_probed_duration():
    DeepgramAuraProvider._validate_word_timing([{"start": 0.0, "end": 10.1}], 10.0)
    with pytest.raises(ProviderError, match=r"word_index=0.*duration=10.000s") as error:
        DeepgramAuraProvider._validate_word_timing(
            [{"text": "private transcript", "start": 9.0, "end": 10.2}], 10.0
        )
    assert "private transcript" not in str(error.value)


@pytest.mark.parametrize("start,end", [(float("nan"), 1.0), (0.0, float("inf")), (-0.1, 1.0), (2.0, 1.0)])
def test_alignment_rejects_invalid_timestamps(start, end):
    with pytest.raises(ProviderError):
        DeepgramAuraProvider._validate_word_timing([{"start": start, "end": end}], 10.0)
