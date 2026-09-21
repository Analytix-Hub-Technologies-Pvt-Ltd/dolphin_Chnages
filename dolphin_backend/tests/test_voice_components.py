import pytest
from services.tts_normalizer import TTSNormalizer


def test_tts_normalizer_basic_markdown():
    raw_md = """### Enclosed Space Entry
**Warning**: Never enter without authorization!
* Gas test must be completed.
* Ventilation is required.
For more info see [Safety Manual](https://example.com/safety).
"""
    normalized = TTSNormalizer.normalize_for_tts(raw_md)
    assert "###" not in normalized
    assert "**" not in normalized
    assert "https://" not in normalized
    assert "Enclosed Space Entry" in normalized
    assert "Never enter without authorization" in normalized
    assert "Gas test must be completed" in normalized
    assert "Safety Manual" in normalized


def test_tts_normalizer_table_conversion():
    table_md = """Here are the requirements:

| Requirement | Status |
|---|---|
| Enclosed Space Permit | Required |
| Gas Detector Calibration | Yes |
| Continuous Ventilation | Mandatory |

Ensure all are checked."""

    normalized = TTSNormalizer.normalize_for_tts(table_md)
    assert "|" not in normalized
    assert "---" not in normalized
    assert "Enclosed Space Permit is required" in normalized
    assert "Gas Detector Calibration is required" in normalized
    assert "Continuous Ventilation is required" in normalized


def test_tts_normalizer_split_into_sentences():
    text = "Enclosed space entry requires a permit. Atmospheric testing must be done before entering! Is the ventilation active? Yes it is."
    sentences = TTSNormalizer.split_into_tts_sentences(text)
    assert len(sentences) == 4
    assert sentences[0].startswith("Enclosed space entry requires a permit")
    assert sentences[1].startswith("Atmospheric testing must be done")
    assert sentences[2].startswith("Is the ventilation active")
    assert sentences[3].startswith("Yes it is")
