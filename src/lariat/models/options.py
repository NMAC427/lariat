from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lariat.models.fields import Field, ListField
    from lariat.models.model import Model


class ModelOptions:
    # Options that the user can specify
    OPTIONS = {
        "db",
        "layout",
    }

    def __init__(self, meta):
        self.db: str | None = None
        self.layout: str | None = None

        self.fields: list[Field] = []
        self.list_fields: list[ListField] = []
        self._field_names: set[str] = set()

        self.meta = meta
        self.model: Model = None  # type: ignore

    def contribute_to_class(self, cls, name):
        cls._meta = self
        self.model = cls

        # Override values from 'class Meta'.
        if self.meta:
            meta_attrs = self.meta.__dict__.copy()
            for name, value in meta_attrs.items():
                if name.startswith("_"):
                    continue
                if name not in ModelOptions.OPTIONS:
                    raise TypeError(f"'class Meta' got an invalid attribute {name}")
                setattr(self, name, value)

    def add_field(self, field: Field):
        if field.name.lower() in self._field_names:
            raise ValueError(
                f"Duplicate field name: '{field.name}' (attribute '{field.attname}')"
            )
        self._field_names.add(field.name.lower())
        self.fields.append(field)

    def add_list_field(self, list_field: ListField):
        self.list_fields.append(list_field)

        for field in list_field.fields:
            field.contribute_to_class(self.model, f"__list_field_{field.name}")
