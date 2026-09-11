"""Tests for phonemes module."""

import pytest

from marionette.phonemes import (
    PHONEME_TO_VISEME,
    Viseme,
    phonemes_to_visemes,
    text_to_phonemes,
    text_to_visemes,
)


def test_text_to_phonemes_hello():
    """"Hello" → known ARPAbet phonemes, no stress markers, no punctuation."""
    phones = text_to_phonemes("Hello")
    assert phones == ["HH", "AH", "L", "OW"]


def test_text_to_phonemes_strips_punctuation():
    """Commas, periods, and spaces do not appear in the output."""
    phones = text_to_phonemes("Hi, there.")
    assert all(p.isalpha() for p in phones)


def test_phonemes_to_visemes_known_mapping():
    """Every known phoneme maps to a Viseme; unknowns fall back to REST."""
    visemes = phonemes_to_visemes(["M", "AH", "L", "OW", "XYZ"])
    assert visemes == [Viseme.MBP, Viseme.AI, Viseme.L, Viseme.O, Viseme.REST]


def test_text_to_visemes_hello():
    """End-to-end text → viseme timeline for a short word."""
    visemes = text_to_visemes("Hello")
    assert visemes == [Viseme.REST, Viseme.AI, Viseme.L, Viseme.O]


def test_viseme_coverage():
    """Every Viseme (except ETSH, TH) is reachable from at least one phoneme."""
    reached = set(PHONEME_TO_VISEME.values())
    # Every declared viseme should either be reachable or be REST (fallback).
    for v in Viseme:
        assert v in reached or v is Viseme.REST
