from __future__ import annotations

from lxml.etree import _Element
from dataclasses import dataclass

from lariat.errors import XMLParserError


@dataclass
class FMFieldDefinition:
    name: str

    max_repeating: int
    not_empty: int
    result_type: str  # one of: 'text', 'number', 'date', 'time', 'timestamp' or 'container'
    type: str  # one of: 'normal', 'calculation' or 'summary'


class FMMetadata:
    """
    Class to store the <metadata> node from the xml.
    """

    def __init__(self, namespace: str):
        self.namespace = namespace

        self.fields = {}
        self.related_sets = {}

    def parse(self, element: _Element):
        ns_len = len(self.namespace) + 2
        for child in element:
            tag = child.tag[ns_len:]

            if tag == "field-definition":
                field = self._parse_field_definition(child)
                self.fields[field.name] = field
            elif tag == "relatedset-definition":
                table, related_set = self._parse_relatedset_definition(child)
                self.related_sets[table] = related_set
            else:
                raise XMLParserError(f"Unexpected tag {tag}.")

    def _parse_field_definition(self, element: _Element) -> FMFieldDefinition:
        return FMFieldDefinition(
            name=element.get("name"),
            max_repeating=int(element.get("max-repeat")),
            not_empty=element.get("not-empty") == "yes",
            result_type=element.get("result"),
            type=element.get("type"),
        )

    def _parse_relatedset_definition(
        self, element: _Element
    ) -> tuple[str, dict[str, FMFieldDefinition]]:
        table = element.get("table")
        fields = dict()
        for child in element:
            field = self._parse_field_definition(child)
            fields[field.name] = field
        return table, fields
