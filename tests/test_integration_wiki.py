"""Optional live Sims Wiki integration tests.

These are skipped unless ``SIMS4_WIKI_TEST=1`` because they require network
access.  The deterministic parser tests live in ``test_validation.py``.
"""

from __future__ import annotations

import os

import pytest

from sims4_sdk.validation import WikiClient, parse_sim

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("SIMS4_WIKI_TEST") != "1",
        reason="set SIMS4_WIKI_TEST=1 to allow live wiki requests",
    ),
]


def test_fetch_and_parse_bella(tmp_path) -> None:
    client = WikiClient(cache_dir=tmp_path / "wiki")
    text = client.fetch_page("Bella Goth")
    assert text

    sim = parse_sim(text, "Bella Goth")
    assert sim is not None
    assert sim.name == "Bella Goth"
    assert sim.age == "Young Adult"
    assert sim.career == "Secret Agent"
    assert sim.aspiration == "Party Animal"
    assert "Good" in sim.traits
    assert sim.spouse == ["Mortimer Goth"]
    assert sim.skills.get("charisma") == 2
    assert sim.relationships[0].romance == 75


def test_fetch_premade_pages(tmp_path) -> None:
    client = WikiClient(cache_dir=tmp_path / "wiki")
    text = client.fetch_page("Pre-made (The Sims 4)")
    assert text
    assert "Bella Goth" in text
