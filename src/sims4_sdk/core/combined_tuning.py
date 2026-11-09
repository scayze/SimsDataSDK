"""Combined Tuning resources (``0x62E94D38``).

A Combined Tuning resource contains every tuning ``<I>`` element of a package
in a single blob.  Two encodings exist:

* **XML** — used by the base-game full-build packages.  The root ``<g>``
  element holds shared values referenced by ``<r x="...">`` nodes elsewhere.
* **Binary DATA** — used by DLC and delta packages.  The ``DATA`` table format
  stores the same XML tree in seven tables; :func:`decode_binary_tuning`
  turns it back into XML.

Both encodings are exposed through :class:`CombinedTuning`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from .data_tables import RELOFFSET_NULL, DataTables
from .resource_types import COMBINED_TUNING_TYPE_ID

__all__ = [
    "CombinedTuning",
    "CombinedTuningError",
    "TuningElement",
    "decode_binary_tuning",
    "is_binary_tuning",
]


class CombinedTuningError(ValueError):
    """Raised when a Combined Tuning resource cannot be decoded."""


def is_binary_tuning(data: bytes) -> bool:
    return len(data) >= 4 and data[:4] == b"DATA"


class _ReferenceTable:
    """Shared ``<g>`` values, indexed by their ``x`` attribute."""

    def __init__(self, values: Optional[dict[str, ET.Element]] = None):
        self._values = values or {}

    @classmethod
    def from_root(cls, root: ET.Element) -> "_ReferenceTable":
        group = root.find("g")
        if group is None:
            return cls()
        values: dict[str, ET.Element] = {}
        for child in group:
            key = child.get("x")
            if key is not None:
                values[key] = child
        return cls(values)

    def resolve(self, element: ET.Element) -> Optional[ET.Element]:
        key = element.get("x")
        if key is None:
            return None
        return self._values.get(key)

    def __len__(self) -> int:
        return len(self._values)


@dataclass
class TuningElement:
    """A single ``<I>`` tuning entry with reference-aware accessors."""

    element: ET.Element
    references: _ReferenceTable = field(default_factory=_ReferenceTable)

    # -- top-level attributes ------------------------------------------
    @property
    def cls(self) -> str:
        return self.element.get("c", "")

    @property
    def tuning_type(self) -> str:
        return self.element.get("i", "")

    @property
    def module(self) -> str:
        return self.element.get("m", "")

    @property
    def name(self) -> str:
        return self.element.get("n", "")

    @property
    def instance_id(self) -> int:
        raw = self.element.get("s")
        return int(raw, 16 if raw and raw.lower().startswith("0x") else 10) if raw else 0

    # -- child accessors -----------------------------------------------
    def _resolve(self, element: ET.Element) -> ET.Element:
        if element.tag == "r":
            resolved = self.references.resolve(element)
            if resolved is not None:
                return resolved
        return element

    def _text(self, element: ET.Element) -> Optional[str]:
        resolved = self._resolve(element)
        if resolved.text is None:
            return None
        text = resolved.text.strip()
        return text or None

    def get_value(self, field_name: str) -> Optional[str]:
        for child in self.element:
            if child.get("n") == field_name:
                return self._text(child)
        return None

    def get_enum(self, field_name: str) -> Optional[str]:
        return self.get_value(field_name)

    def get_bool(self, field_name: str, default: bool = False) -> bool:
        value = self.get_value(field_name)
        if value is None:
            return default
        return value.strip().lower() == "true"

    def get_int(self, field_name: str, default: int = 0) -> int:
        value = self.get_value(field_name)
        if value is None:
            return default
        try:
            return int(value, 0)
        except ValueError:
            return default

    def get_float(self, field_name: str, default: float = 0.0) -> float:
        value = self.get_value(field_name)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            return default

    def get_list(self, field_name: str) -> list[str]:
        for child in self.element:
            if child.tag == "L" and child.get("n") == field_name:
                return _list_text(child, self.references)
            if child.tag == "r" and child.get("n") == field_name:
                resolved = self.references.resolve(child)
                if resolved is not None and resolved.tag == "L":
                    return _list_text(resolved, self.references)
        return []

    def child(self, field_name: str) -> Optional[ET.Element]:
        for child in self.element:
            if child.get("n") == field_name:
                return self._resolve(child)
        return None

    @property
    def raw(self) -> ET.Element:
        return self.element

    def to_dict(self) -> dict[str, Any]:
        return {
            "class": self.cls,
            "tuning_type": self.tuning_type,
            "module": self.module,
            "name": self.name,
            "instance_id": self.instance_id,
        }

    def __repr__(self) -> str:
        return (
            f"TuningElement(class={self.cls!r}, name={self.name!r}, "
            f"instance_id=0x{self.instance_id:016X})"
        )


def _list_text(element: ET.Element, references: _ReferenceTable) -> list[str]:
    values: list[str] = []
    for child in element:
        target = child
        if child.tag == "r":
            resolved = references.resolve(child)
            if resolved is not None:
                target = resolved
        if target.text and target.text.strip():
            values.append(target.text.strip())
    return values


@dataclass
class CombinedTuning:
    """A parsed Combined Tuning resource."""

    root: ET.Element
    references: _ReferenceTable
    entries: list[TuningElement]
    xml: str = ""

    TYPE_ID = COMBINED_TUNING_TYPE_ID

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    @classmethod
    def parse(cls, data: bytes) -> "CombinedTuning":
        """Parse raw (already decompressed) Combined Tuning bytes."""
        if is_binary_tuning(data):
            xml_text = decode_binary_tuning(data)
        else:
            xml_text = data.decode("utf-8-sig", errors="replace")
        return cls.from_xml(xml_text)

    @classmethod
    def from_xml(cls, xml_text: str) -> "CombinedTuning":
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise CombinedTuningError(f"invalid combined tuning XML: {exc}") from exc

        references = _ReferenceTable.from_root(root)
        entries = [
            TuningElement(element, references)
            for element in root.iter("I")
            if element.get("c") is not None
        ]
        return cls(root=root, references=references, entries=entries, xml=xml_text)

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def by_class(self, class_name: str) -> list[TuningElement]:
        return [entry for entry in self.entries if entry.cls == class_name]

    def by_module(self, module: str) -> list[TuningElement]:
        return [entry for entry in self.entries if entry.module == module]

    def by_tuning_type(self, tuning_type: str) -> list[TuningElement]:
        return [entry for entry in self.entries if entry.tuning_type == tuning_type]

    def find_by_name(self, name: str) -> Optional[TuningElement]:
        for entry in self.entries:
            if entry.name == name:
                return entry
        return None

    def find_by_instance_id(self, instance_id: int) -> Optional[TuningElement]:
        for entry in self.entries:
            if entry.instance_id == instance_id:
                return entry
        return None

    def index_by_instance_id(self) -> dict[int, TuningElement]:
        return {entry.instance_id: entry for entry in self.entries}

    def index_by_name(self) -> dict[str, TuningElement]:
        return {entry.name: entry for entry in self.entries}

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterator[TuningElement]:
        return iter(self.entries)

    def __repr__(self) -> str:
        return f"CombinedTuning(entries={len(self.entries)})"


# ----------------------------------------------------------------------
# binary DATA -> XML
# ----------------------------------------------------------------------
def decode_binary_tuning(data: bytes) -> str:
    """Decode a binary ``DATA`` Combined Tuning blob into an XML string."""
    tables = DataTables.parse(data)
    if len(tables.tables) < 7:
        raise CombinedTuningError(
            f"Combined Tuning DATA needs 7 tables, found {len(tables.tables)}"
        )

    meta_rows = tables.rows[0]
    node_rows = tables.rows[1]
    attribute_rows = tables.rows[2]
    node_refs = tables.rows[3]
    attribute_refs = tables.rows[4]
    string_refs = tables.rows[5]

    if not meta_rows:
        raise CombinedTuningError("Combined Tuning DATA has no metadata row")
    meta = meta_rows[0]

    table_offsets: list[int] = []
    for table in tables.tables:
        position = table.row_offset_pos + table.row_offset
        position += -position & 15
        table_offsets.append(position)

    decoder = _XmlDecoder(tables.data)
    first_element = decoder.position(meta["first_element"])
    top_element = decoder.position(meta["top_element"])

    def row_index(position: int, table_index: int) -> int:
        table_start = table_offsets[table_index]
        return (position - table_start) // tables.tables[table_index].row_size

    def text_at(string_row: int) -> str:
        ref = string_refs[string_row]
        return decoder.read_string(decoder.position(ref))

    def read_attributes(first: int) -> list[tuple[str, str]]:
        attributes: list[tuple[str, str]] = []
        index = row_index(first, 4)
        while index < len(attribute_refs):
            ref = attribute_refs[index]
            if decoder.is_null(ref):
                break
            attribute_position = decoder.position(ref)
            attribute_index = row_index(attribute_position, 2)
            attribute = attribute_rows[attribute_index]
            attributes.append(
                (text_at(attribute["name"]), text_at(attribute["value"]))
            )
            index += 1
        return attributes

    def read_children(first: int) -> list[str]:
        children: list[str] = []
        index = row_index(first, 3)
        while index < len(node_refs):
            ref = node_refs[index]
            if decoder.is_null(ref):
                break
            children.append(read_node(decoder.position(ref)))
            index += 1
        return children

    def read_node(position: int) -> str:
        node = node_rows[row_index(position, 1)]
        text = text_at(node["text"])
        has_attributes = not decoder.is_null(node["attrs"])
        has_children = not decoder.is_null(node["children"])

        if not has_attributes and not has_children:
            escaped = _escape(text)
            return f"<{escaped} />" if position >= first_element else escaped

        parts = [f"<{text}"]
        if has_attributes:
            for name, value in read_attributes(decoder.position(node["attrs"])):
                parts.append(f' {name}="{_escape(value)}"')
        if has_children:
            parts.append(">")
            parts.extend(read_children(decoder.position(node["children"])))
            parts.append(f"</{text}>")
        else:
            parts.append(" />")
        return "".join(parts)

    xml = read_node(top_element)
    return '<?xml version="1.0" encoding="utf-8"?>\n' + xml


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class _XmlDecoder:
    """Helpers for reading strings at absolute offsets."""

    def __init__(self, data: bytes):
        self.data = data

    def position(self, ref: dict[str, Any]) -> int:
        offset = ref["mDataOffset"]
        if offset == RELOFFSET_NULL:
            return RELOFFSET_NULL
        return ref["startof_mDataOffset"] + offset

    @staticmethod
    def is_null(ref: dict[str, Any]) -> bool:
        return ref["mDataOffset"] == RELOFFSET_NULL

    def read_string(self, position: int) -> str:
        if position < 0 or position >= len(self.data):
            raise CombinedTuningError(f"string offset {position} is out of range")
        end = self.data.find(b"\x00", position)
        if end < 0:
            raise CombinedTuningError(f"unterminated string at {position}")
        return self.data[position:end].decode("utf-8", errors="replace")
