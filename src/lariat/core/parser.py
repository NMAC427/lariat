from __future__ import annotations

import io
from dataclasses import dataclass

from lxml import etree
from lxml.etree import _Element

from lariat.core.metadata import FMMetadata
from lariat.core.util.io import GeneratorBytestIO
from lariat.errors import FileMakerError


@dataclass
class FMRecord:
    record_id: int
    mod_id: int
    raw_fields: list[tuple[str, str | list[FMRecord]]]  # fields / related sets

    def get_field(self, name, default=None):
        """
        WARNING: This is not efficient if there are more than one or two fields.
        """
        for field_name, value in self.raw_fields:
            if field_name == name:
                return value
        return default


class FMParser:
    def parse(self, stream) -> tuple[list[FMRecord], FMMetadata]:
        stream = GeneratorBytestIO(stream)
        tree = etree.iterparse(stream, events=("start-ns", "end"))

        namespace = ""
        namespace_len = 0

        records = []
        metadata = None

        for event, e in tree:
            if event == "end":
                tag = e.tag[namespace_len:]

                # Sort records by how common they are.
                if tag == "record":
                    records.append(self._parse_record(e, namespace_len))
                elif tag == "metadata":
                    metadata = FMMetadata(namespace)
                    metadata.parse(e)
                elif tag == "error":
                    code = e.attrib.get("code")
                    if code != "0":
                        raise FileMakerError(code)

            elif event == "start-ns":
                # This is a hack to quickly remove the namespace prefix from the e.tag value
                namespace = e[1]
                namespace_len = len(namespace) + 2

        return records, metadata

    def _parse_record(self, element: _Element, ns_len: int) -> FMRecord:
        record_id = element.get("record-id")
        mod_id = element.get("mod-id")
        fields = []

        for child in element:
            tag = child.tag[ns_len:]
            if tag == "field":
                name = child.get("name").lower()
                data = child[0].text
                fields.append((name, data))

                assert len(child) == 1  # Should only contain one <data> tag
            elif tag == "relatedset":
                table_name = child.get("table").lower()
                table = []

                for rs_child in child:
                    rs_record = self._parse_record(rs_child, ns_len)
                    table.append(rs_record)

                fields.append((table_name, table))

        return FMRecord(
            record_id=record_id,
            mod_id=mod_id,
            raw_fields=fields,
        )
