"""Combined Tuning resources (``0x62E94D38``).

A Combined Tuning resource contains every tuning ``<I>`` element of a package
in a single blob.  Two encodings exist:

* **XML** — used by the base-game full-build packages.  The root ``<g>``
  element holds shared values referenced by ``<r x="...">`` nodes elsewhere.
* **Binary DATA** — used by DLC and delta packages.  The ``DATA`` table format
  stores the same XML tree in seven tables; :func:`decode_binary_tuning_tree`
  rebuilds the tree directly, without going through XML text.

Both encodings are exposed through :class:`CombinedTuning`.
"""

from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
from typing import Any, Iterator, Optional

from ..exceptions import Sims4SDKError
from .data_tables import RELOFFSET_NULL, DataTables
from .resource_types import COMBINED_TUNING_TYPE_ID

_I32 = struct.Struct("<i").unpack_from

__all__ = [
    "CombinedTuning",
    "CombinedTuningError",
    "TuningElement",
    "decode_binary_tuning",
    "decode_binary_tuning_tree",
    "is_binary_tuning",
]


class CombinedTuningError(Sims4SDKError, ValueError):
    """Raised when a Combined Tuning resource cannot be decoded."""


def is_binary_tuning(data: bytes) -> bool:
    return len(data) >= 4 and data[:4] == b"DATA"


class _ReferenceTable:
    """Shared ``<g>`` values, indexed by their ``x`` attribute.

    For binary blobs the children of ``<g>`` are materialised on first use: the
    table holds tens of thousands of values, and a build only resolves a few
    thousand of them.
    """

    __slots__ = (
        "_eager",
        "_positions",
        "_cache",
        "_decoder",
        "_group",
        "_group_items",
        "_materialized",
    )

    def __init__(
        self,
        positions: Optional[dict[str, int]] = None,
        decoder: Optional["_BinaryDecoder"] = None,
        group: Optional[ET.Element] = None,
        group_items: Optional[list] = None,
    ):
        self._eager: Optional[dict[str, ET.Element]] = None
        self._positions = positions or {}
        self._cache: dict[int, ET.Element] = {}
        self._decoder = decoder
        self._group = group
        self._group_items = group_items or []
        self._materialized = False

    @classmethod
    def from_root(cls, root: ET.Element) -> "_ReferenceTable":
        table = cls()
        table._materialized = True
        group = root.find("g")
        if group is None:
            table._eager = {}
            return table
        eager: dict[str, ET.Element] = {}
        for child in group:
            key = child.get("x")
            if key is not None:
                eager[key] = child
        table._eager = eager
        return table

    def resolve(self, element: ET.Element) -> Optional[ET.Element]:
        key = element.get("x")
        if key is None:
            return None
        if self._eager is not None:
            return self._eager.get(key)
        position = self._positions.get(key)
        if position is None:
            return None
        cached = self._cache.get(position)
        if cached is None:
            cached = self._decoder.build(position)
            self._cache[position] = cached
        return cached

    def materialize(self) -> None:
        """Build every shared value (used when the full tree is requested)."""
        if self._materialized:
            return
        self._materialized = True
        if self._eager is not None:
            return
        items: list = []
        build = self._decoder.build
        cache = self._cache
        for item in self._group_items:
            if isinstance(item, str):
                items.append(item)
                continue
            element = cache.get(item)
            if element is None:
                element = build(item)
                cache[item] = element
            items.append(element)
        if self._group is not None and items:
            _assign_text_and_children(self._group, items)

    def __len__(self) -> int:
        if self._eager is not None:
            return len(self._eager)
        return len(self._positions)


class TuningElement:
    """A single ``<I>`` tuning entry with reference-aware accessors.

    Binary blobs decode entries lazily: the element starts out with its tag and
    attributes only, and its children are built the first time the element is
    touched.  Accessing :attr:`element` (or :attr:`raw`) materialises it, so the
    public behaviour is unchanged.
    """

    __slots__ = ("_element", "_references", "_decoder", "_position", "_instance_id")

    def __init__(
        self,
        element: ET.Element,
        references: _ReferenceTable,
        decoder: Optional["_BinaryDecoder"] = None,
        position: int = 0,
    ):
        self._element = element
        self._references = references
        self._decoder = decoder
        self._position = position
        self._instance_id: Optional[int] = None

    # -- element access ------------------------------------------------
    @property
    def element(self) -> ET.Element:
        """The backing XML element, materialised on first access."""
        decoder = self._decoder
        if decoder is not None:
            self._decoder = None
            decoder.fill(self._element, self._position)
        return self._element

    @property
    def raw(self) -> ET.Element:
        return self.element

    @property
    def references(self) -> _ReferenceTable:
        return self._references

    # -- top-level attributes ------------------------------------------
    @property
    def cls(self) -> str:
        return self._element.get("c", "")

    @property
    def tuning_type(self) -> str:
        return self._element.get("i", "")

    @property
    def module(self) -> str:
        return self._element.get("m", "")

    @property
    def name(self) -> str:
        return self._element.get("n", "")

    @property
    def instance_id(self) -> int:
        cached = self._instance_id
        if cached is None:
            raw = self._element.get("s")
            if raw:
                cached = int(raw, 16 if raw.lower().startswith("0x") else 10)
            else:
                cached = 0
            self._instance_id = cached
        return cached

    # -- child accessors -----------------------------------------------
    def _resolve(self, element: ET.Element) -> ET.Element:
        if element.tag == "r":
            resolved = self._references.resolve(element)
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
                return _list_text(child, self._references)
            if child.tag == "r" and child.get("n") == field_name:
                resolved = self._references.resolve(child)
                if resolved is not None and resolved.tag == "L":
                    return _list_text(resolved, self._references)
        return []

    def child(self, field_name: str) -> Optional[ET.Element]:
        for child in self.element:
            if child.get("n") == field_name:
                return self._resolve(child)
        return None

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


class CombinedTuning:
    """A parsed Combined Tuning resource."""

    __slots__ = ("_root", "references", "entries", "modules", "xml")

    TYPE_ID = COMBINED_TUNING_TYPE_ID

    def __init__(
        self,
        root: ET.Element,
        references: _ReferenceTable,
        entries: list[TuningElement],
        modules: Optional[dict[str, ET.Element]] = None,
        xml: str = "",
    ):
        self._root = root
        self.references = references
        self.entries = entries
        self.modules = modules if modules is not None else {}
        self.xml = xml

    @property
    def root(self) -> ET.Element:
        """The full element tree; lazily decoded entries are materialised here."""
        for entry in self.entries:
            if entry._decoder is not None:
                entry.element
        self.references.materialize()
        materialize_modules = getattr(self.modules, "materialize", None)
        if materialize_modules is not None:
            materialize_modules()
        return self._root

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    @classmethod
    def parse(cls, data: bytes) -> "CombinedTuning":
        """Parse raw (already decompressed) Combined Tuning bytes."""
        if is_binary_tuning(data):
            return _build_from_binary(data)
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
        modules = {
            node.get("n"): node
            for node in root.iter("M")
            if node.get("n")
        }
        return cls(
            root=root,
            references=references,
            entries=entries,
            modules=modules,
            xml=xml_text,
        )

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

    def find_module(self, name: str) -> Optional[ET.Element]:
        """Return a module-level ``<M n="...">`` block, if present."""
        return self.modules.get(name)

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
# binary DATA -> element tree
# ----------------------------------------------------------------------
def decode_binary_tuning(data: bytes) -> str:
    """Decode a binary ``DATA`` Combined Tuning blob into an XML string."""
    root = decode_binary_tuning_tree(data)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        + ET.tostring(root, encoding="unicode")
    )


def decode_binary_tuning_tree(data: bytes) -> ET.Element:
    """Decode a binary ``DATA`` Combined Tuning blob into a complete element tree."""
    decoder = _BinaryDecoder(_parse_tables(data))
    return decoder.build(decoder.top_element)


def _parse_tables(data: bytes) -> DataTables:
    tables = DataTables.parse(data)
    if len(tables.tables) < 7:
        raise CombinedTuningError(
            f"Combined Tuning DATA needs 7 tables, found {len(tables.tables)}"
        )
    if tables.tables[0].row_count == 0:
        raise CombinedTuningError("Combined Tuning DATA has no metadata row")
    return tables


def _build_from_binary(data: bytes) -> CombinedTuning:
    """Decode a binary blob, leaving the tuning entries lazily materialised."""
    decoder = _BinaryDecoder(_parse_tables(data))
    root, modules, entry_nodes, references = decoder.build_document_lazy()
    entries = [
        TuningElement(
            element,
            references,
            None if position is None else decoder,
            0 if position is None else position,
        )
        for element, position in entry_nodes
    ]
    return CombinedTuning(
        root=root,
        references=references,
        entries=entries,
        modules=modules,
        xml="",
    )


class _BinaryDecoder:
    """Reads the seven Combined Tuning tables directly out of the blob.

    Rows are addressed by their buffer position, which is how references are
    stored.  Nothing is materialised until an element is asked for.
    """

    __slots__ = (
        "data",
        "top_element",
        "first_element",
        "node_base",
        "node_stride",
        "text_offset",
        "attrs_offset",
        "children_offset",
        "attribute_base",
        "attribute_stride",
        "name_offset",
        "value_offset",
        "node_ref_base",
        "node_ref_stride",
        "node_ref_count",
        "attribute_ref_base",
        "attribute_ref_stride",
        "attribute_ref_count",
        "string_ref_base",
        "string_ref_stride",
        "string_cache",
    )

    def __init__(self, tables: DataTables):
        meta = tables.rows[0][0]

        self.data = tables.data
        self.first_element = _reference_position(meta["first_element"])
        self.top_element = _reference_position(meta["top_element"])

        node_columns = _column_map(tables, 1)
        attribute_columns = _column_map(tables, 2)

        node_table = tables.tables[1]
        self.node_base = node_table.row_start
        self.node_stride = node_table.row_stride
        self.text_offset = node_columns["text"]
        self.attrs_offset = node_columns["attrs"]
        self.children_offset = node_columns["children"]

        attribute_table = tables.tables[2]
        self.attribute_base = attribute_table.row_start
        self.attribute_stride = attribute_table.row_stride
        self.name_offset = attribute_columns["name"]
        self.value_offset = attribute_columns["value"]

        self.node_ref_base = tables.tables[3].row_start
        self.node_ref_stride = tables.tables[3].row_stride
        self.node_ref_count = tables.tables[3].row_count
        self.attribute_ref_base = tables.tables[4].row_start
        self.attribute_ref_stride = tables.tables[4].row_stride
        self.attribute_ref_count = tables.tables[4].row_count
        self.string_ref_base = tables.tables[5].row_start
        self.string_ref_stride = tables.tables[5].row_stride

        self.string_cache: list = [None] * tables.tables[5].row_count

    # -- primitive reads -----------------------------------------------
    def _row(self, position: int, base: int, stride: int) -> int:
        return base + ((position - base) // stride) * stride

    def text_at(self, string_row: int) -> str:
        cache = self.string_cache
        value = cache[string_row]
        if value is None:
            data = self.data
            field = self.string_ref_base + string_row * self.string_ref_stride
            offset = _I32(data, field)[0]
            if offset == RELOFFSET_NULL:
                raise CombinedTuningError("null string reference")
            position = field + offset
            if position < 0 or position >= len(data):
                raise CombinedTuningError(f"string offset {position} is out of range")
            end = data.find(b"\x00", position)
            if end < 0:
                raise CombinedTuningError(f"unterminated string at {position}")
            value = data[position:end].decode("utf-8", errors="replace")
            cache[string_row] = value
        return value

    def tag_at(self, position: int) -> str:
        row = self._row(position, self.node_base, self.node_stride)
        return self.text_at(_I32(self.data, row + self.text_offset)[0])

    # -- element construction -------------------------------------------
    def shallow(self, position: int) -> ET.Element:
        """Build the element with its tag and attributes, but no children."""
        row = self._row(position, self.node_base, self.node_stride)
        tag = self.text_at(_I32(self.data, row + self.text_offset)[0])
        return ET.Element(tag, self.attributes(row))

    def attributes(self, row: int) -> dict[str, str]:
        data = self.data
        field = row + self.attrs_offset
        offset = _I32(data, field)[0]
        if offset == RELOFFSET_NULL:
            return {}

        attrib: dict[str, str] = {}
        index = (field + offset - self.attribute_ref_base) // self.attribute_ref_stride
        count = self.attribute_ref_count
        while index < count:
            reference_field = self.attribute_ref_base + index * self.attribute_ref_stride
            reference = _I32(data, reference_field)[0]
            if reference == RELOFFSET_NULL:
                break
            attribute_row = self._row(
                reference_field + reference, self.attribute_base, self.attribute_stride
            )
            attrib[
                self.text_at(_I32(data, attribute_row + self.name_offset)[0])
            ] = self.text_at(
                _I32(data, attribute_row + self.value_offset)[0]
            )
            index += 1
        return attrib

    def x_attribute(self, row: int) -> Optional[str]:
        """Return the ``x`` attribute of an attribute-owning row, if present."""
        data = self.data
        field = row + self.attrs_offset
        offset = _I32(data, field)[0]
        if offset == RELOFFSET_NULL:
            return None
        index = (field + offset - self.attribute_ref_base) // self.attribute_ref_stride
        count = self.attribute_ref_count
        while index < count:
            reference_field = self.attribute_ref_base + index * self.attribute_ref_stride
            reference = _I32(data, reference_field)[0]
            if reference == RELOFFSET_NULL:
                break
            attribute_row = self._row(
                reference_field + reference, self.attribute_base, self.attribute_stride
            )
            if self.text_at(_I32(data, attribute_row + self.name_offset)[0]) == "x":
                return self.text_at(_I32(data, attribute_row + self.value_offset)[0])
            index += 1
        return None

    def fill(self, element: ET.Element, position: int) -> None:
        """Append the element's children (called once, on materialisation)."""
        data = self.data
        row = self._row(position, self.node_base, self.node_stride)
        field = row + self.children_offset
        offset = _I32(data, field)[0]
        if offset == RELOFFSET_NULL:
            return

        items: list = []
        index = (field + offset - self.node_ref_base) // self.node_ref_stride
        count = self.node_ref_count
        first_element = self.first_element
        while index < count:
            reference_field = self.node_ref_base + index * self.node_ref_stride
            reference = _I32(data, reference_field)[0]
            if reference == RELOFFSET_NULL:
                break
            child = reference_field + reference
            if child < first_element:
                child_row = self._row(child, self.node_base, self.node_stride)
                items.append(
                    self.text_at(_I32(data, child_row + self.text_offset)[0])
                )
            else:
                items.append(self.build(child))
            index += 1
        if items:
            _assign_text_and_children(element, items)

    def build(self, position: int) -> ET.Element:
        """Build a complete element subtree."""
        element = self.shallow(position)
        self.fill(element, position)
        return element

    # -- document level -------------------------------------------------
    def children(self, position: int):
        """Yield ``(position, tag)`` for the children of ``position``.

        ``tag`` is ``None`` for text nodes.
        """
        data = self.data
        row = self._row(position, self.node_base, self.node_stride)
        field = row + self.children_offset
        offset = _I32(data, field)[0]
        if offset == RELOFFSET_NULL:
            return
        index = (field + offset - self.node_ref_base) // self.node_ref_stride
        count = self.node_ref_count
        first_element = self.first_element
        while index < count:
            reference_field = self.node_ref_base + index * self.node_ref_stride
            reference = _I32(data, reference_field)[0]
            if reference == RELOFFSET_NULL:
                break
            child = reference_field + reference
            yield child, (self.tag_at(child) if child >= first_element else None)
            index += 1

    def build_document_lazy(self):
        """Build ``combined > R > (I | M)``, deferring large subtrees.

        ``<g>`` values and ``<M>`` modules are materialised on demand, and the
        ``<I>`` tuning entries are handed back for lazy construction.
        """
        root = self.shallow(self.top_element)
        modules = _LazyModules(self)
        references = _ReferenceTable({}, self)
        entry_nodes: list[tuple[ET.Element, Optional[int]]] = []

        items: list = []
        for child, tag in self.children(self.top_element):
            if tag == "g":
                group = self.shallow(child)
                positions: dict[str, int] = {}
                group_items: list = []
                for member, member_tag in self.children(child):
                    if member_tag is None:
                        group_items.append(self.tag_at(member))
                        continue
                    row = self._row(member, self.node_base, self.node_stride)
                    key = self.x_attribute(row)
                    if key is not None:
                        positions[key] = member
                    group_items.append(member)
                references = _ReferenceTable(positions, self, group, group_items)
                items.append(group)
                continue

            if tag == "R":
                group = self.shallow(child)
                group_items = []
                for member, member_tag in self.children(child):
                    if member_tag is None:
                        group_items.append(self.tag_at(member))
                    elif member_tag == "I":
                        element = self.shallow(member)
                        group_items.append(element)
                        if element.get("c") is not None:
                            entry_nodes.append((element, member))
                    elif member_tag == "M":
                        module = self.shallow(member)
                        group_items.append(module)
                        modules.register(module, member)
                    else:
                        group_items.append(self.build(member))
                if group_items:
                    _assign_text_and_children(group, group_items)
                items.append(group)
                continue

            element = self.build(child)
            items.append(element)
            if tag == "M":
                modules.register(element)
            elif tag == "I" and element.get("c") is not None:
                entry_nodes.append((element, None))

        if items:
            _assign_text_and_children(root, items)
        return root, modules, entry_nodes, references


class _LazyModules(dict):
    """Module blocks that are materialised the first time they are read."""

    def __init__(self, decoder: "_BinaryDecoder"):
        super().__init__()
        self._decoder = decoder
        self._positions: dict[str, int] = {}

    def register(self, element: ET.Element, position: Optional[int] = None) -> None:
        name = element.get("n")
        if not name:
            return
        dict.__setitem__(self, name, element)
        if position is not None:
            self._positions[name] = position

    def __getitem__(self, name: str) -> ET.Element:
        element = dict.__getitem__(self, name)
        position = self._positions.pop(name, None)
        if position is not None:
            self._decoder.fill(element, position)
        return element

    def get(self, name: str, default: Optional[ET.Element] = None):
        if not dict.__contains__(self, name):
            return default
        return self[name]

    def materialize(self) -> None:
        for name in list(dict.keys(self)):
            self[name]

    def values(self):
        self.materialize()
        return dict.values(self)

    def items(self):
        self.materialize()
        return dict.items(self)


def _reference_position(ref: dict) -> int:
    """Absolute buffer position of a String/Object/Variant reference."""
    offset = ref["mDataOffset"]
    if offset == RELOFFSET_NULL:
        return RELOFFSET_NULL
    return ref["startof_mDataOffset"] + offset


def _column_map(tables: DataTables, table_index: int) -> dict[str, int]:
    schema = tables.schemas[tables.tables[table_index].schema_index]
    return {
        column.name: column.offset
        for column in schema.columns
        if column.name is not None
    }


def _assign_text_and_children(element: ET.Element, items: list) -> None:
    """Mirror ElementTree's text/tail layout for a mixed content run."""
    index = 0
    total = len(items)
    leading: list[str] = []
    while index < total and isinstance(items[index], str):
        leading.append(items[index])
        index += 1
    if leading:
        element.text = "".join(leading)

    previous: Optional[ET.Element] = None
    while index < total:
        item = items[index]
        if isinstance(item, str):
            if previous is None:
                element.text = (element.text or "") + item
            else:
                previous.tail = (previous.tail or "") + item
        else:
            element.append(item)
            previous = item
        index += 1
