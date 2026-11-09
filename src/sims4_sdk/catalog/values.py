"""Helpers for reading values out of tuning elements.

Combined tuning uses a compact XML dialect with shared references (``<r x="…">``)
and variant wrappers (``<V t="…">``).  :class:`TuningView` smooths over both so
domain extractors can ask for "the localized display name" or "the list of age
enums" without repeating the reference-walking logic.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Mapping, Optional

from ..core.combined_tuning import TuningElement

__all__ = ["TuningView", "localize", "LOCALIZATION_PREFIX"]

LOCALIZATION_PREFIX = "0x"
_MAX_REFERENCE_DEPTH = 32


def localize(value: Optional[str], strings: Mapping[int, str]) -> Optional[str]:
    """Resolve a localization key like ``0x69178C27`` to its text."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if text.lower().startswith(LOCALIZATION_PREFIX):
        try:
            return strings.get(int(text, 16), value)
        except ValueError:
            return value
    return value


class TuningView:
    """Reference-aware accessors for a :class:`TuningElement`."""

    def __init__(self, entry: TuningElement, strings: Mapping[int, str]):
        self.entry = entry
        self.strings = strings

    # ------------------------------------------------------------------
    # reference resolution
    # ------------------------------------------------------------------
    def resolve(self, element: Optional[ET.Element]) -> Optional[ET.Element]:
        if element is None:
            return None
        depth = 0
        while element is not None and element.tag == "r" and depth < _MAX_REFERENCE_DEPTH:
            element = self.entry.references.resolve(element)
            depth += 1
        return element

    def child(self, name: str) -> Optional[ET.Element]:
        for child in self.entry.raw:
            if child.get("n") == name:
                return child
        return None

    def resolved_child(self, name: str) -> Optional[ET.Element]:
        return self.resolve(self.child(name))

    def first(self) -> Optional[ET.Element]:
        for child in self.entry.raw:
            return child
        return None

    # ------------------------------------------------------------------
    # scalar values
    # ------------------------------------------------------------------
    def text_of(self, element: Optional[ET.Element]) -> Optional[str]:
        element = self.resolve(element)
        if element is None:
            return None
        text = (element.text or "").strip()
        if not text:
            return None
        return localize(text, self.strings)

    def raw_text(self, name: str) -> Optional[str]:
        element = self.resolve(self.child(name))
        if element is None:
            return None
        text = (element.text or "").strip()
        return text or None

    def text(self, name: str) -> Optional[str]:
        """Return a localized text field."""
        return self.text_of(self.child(name))

    def raw_text_of(self, element: Optional[ET.Element]) -> Optional[str]:
        element = self.resolve(element)
        if element is None:
            return None
        text = (element.text or "").strip()
        return text or None

    def number(self, name: str) -> Optional[int]:
        return self.number_of(self.child(name))

    def number_of(self, element: Optional[ET.Element]) -> Optional[int]:
        raw = self.raw_text_of(element)
        if raw is None:
            return None
        try:
            return int(raw, 0)
        except ValueError:
            return None

    def flag(self, name: str, default: bool = False) -> bool:
        return self.flag_of(self.child(name), default=default)

    def flag_of(self, element: Optional[ET.Element], default: bool = False) -> bool:
        raw = self.raw_text_of(element)
        if raw is None:
            return default
        return raw.strip().lower() in ("true", "1", "enabled", "yes")

    def enum(self, name: str) -> Optional[str]:
        """Return the text of an enum value, if present."""
        element = self.resolved_child(name)
        if element is None:
            return None
        text = (element.text or "").strip()
        if text:
            return text
        value = element.get("value") or element.get("n")
        return value or None

    # ------------------------------------------------------------------
    # variants
    # ------------------------------------------------------------------
    def variant(self, name: str) -> tuple[Optional[str], Optional[ET.Element]]:
        """Return ``(variant_type, payload_element)`` for a ``<V>`` field."""
        element = self.resolved_child(name)
        if element is None:
            return None, None
        if element.tag != "V":
            return None, element
        variant_type = element.get("t")
        payload = None
        if variant_type == "enabled":
            for child in element:
                payload = self.resolve(child)
                break
        else:
            for child in element:
                payload = self.resolve(child)
                break
        return variant_type, payload

    def enabled_value(self, name: str) -> Optional[int]:
        """Read an ``<V t="enabled">`` wrapper that contains a numeric value."""
        variant_type, payload = self.variant(name)
        if variant_type not in (None, "enabled"):
            return None
        if payload is None:
            # Sometimes the payload is the V element itself with text.
            payload = self.resolved_child(name)
        return self.number_of(payload)

    def enabled_element(self, name: str) -> Optional[ET.Element]:
        variant_type, payload = self.variant(name)
        if variant_type != "enabled":
            return None
        return payload

    # ------------------------------------------------------------------
    # lists
    # ------------------------------------------------------------------
    def list_elements(self, name: str) -> list[ET.Element]:
        element = self.resolved_child(name)
        if element is None:
            return []
        if element.tag == "L":
            return list(element)
        return [element]

    def list_texts(self, name: str) -> list[str]:
        return [text for text in (self.text_of(el) for el in self.list_elements(name)) if text]

    def list_enums(self, name: str) -> list[str]:
        values: list[str] = []
        for element in self.list_elements(name):
            resolved = self.resolve(element)
            if resolved is None:
                continue
            text = (resolved.text or "").strip()
            if not text:
                text = resolved.get("value") or resolved.get("n") or ""
            if text:
                values.append(text)
        return values

    def list_numbers(self, name: str) -> list[int]:
        values: list[int] = []
        for element in self.list_elements(name):
            number = self.number_of(element)
            if number is not None:
                values.append(number)
        return values

    def list_int_text(self, name: str) -> list[int]:
        return self.list_numbers(name)
