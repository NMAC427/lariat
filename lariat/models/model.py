from __future__ import annotations

import inspect
from typing import Type

from lariat._typing import ModelT
from lariat.core.parser import FMRecord
from lariat.models.options import ModelOptions
from lariat.models.query_set import QuerySet


def _has_contribute_to_class(value):
    # Only call contribute_to_class() if it's bound.
    return not inspect.isclass(value) and hasattr(value, "contribute_to_class")


class ModelBase(type):
    def __new__(cls, name, bases, attrs, **kwargs):
        # Also ensure initialization is only performed for subclasses of Model
        # (excluding Model class itself).
        parents = [b for b in bases if isinstance(b, ModelBase)]
        if not parents:
            return super().__new__(cls, name, bases, attrs)

        # Create the class
        module = attrs.pop("__module__")
        new_attrs = {"__module__": module}
        classcell = attrs.pop("__classcell__", None)
        if classcell is not None:
            new_attrs["__classcell__"] = classcell
        attr_meta = attrs.pop("Meta", None)

        # Pass all attrs without a contribute_to_class()
        # method to type.__new__() so that they're properly initialized
        # (i.e. __set_name__()).
        contributable_attrs = {}
        for obj_name, obj in attrs.items():
            if _has_contribute_to_class(obj):
                contributable_attrs[obj_name] = obj
            else:
                new_attrs[obj_name] = obj
        new_class = super().__new__(
            cls, name, bases, new_attrs, **kwargs
        )  # type: type[Model]

        # meta
        meta = attr_meta or getattr(new_class, "Meta", None)
        new_class.add_to_class("_meta", ModelOptions(meta))

        # Contribute to new class
        for obj_name, obj in contributable_attrs.items():
            new_class.add_to_class(obj_name, obj)

        # Compute field name mapping dict
        # FMS field names are case insensitive -> Convert everything to lower case
        new_class.add_to_class(
            "_field_mapping",
            {field.name.lower(): field.attname for field in new_class._meta.fields},
        )
        new_class.add_to_class(
            "_attr_mapping",
            {field.attname: field.name.lower() for field in new_class._meta.fields},
        )

        return new_class

    def add_to_class(cls, name, value):
        if _has_contribute_to_class(value):
            value.contribute_to_class(cls, name)
        else:
            setattr(cls, name, value)


class Model(metaclass=ModelBase):
    # Meta and internal attributes
    _meta: ModelOptions
    _field_mapping: dict[str, str]  # FMS field name -> attribute name
    _attr_mapping: dict[str, str]  # attribute name -> FMS field name

    # Query interface
    @classmethod
    def records(cls: Type[ModelT]) -> QuerySet[ModelT]:
        return QuerySet(cls)

    def __init__(self, record_id=None, mod_id=None, **kwargs):
        super().__init__()
        self.record_id = record_id
        self.mod_id = mod_id

        for name, value in kwargs.items():
            print(name, value)
            assert name in type(self).__dict__
            setattr(self, name, value)

    def __repr__(self):
        return (
            self.__class__.__qualname__
            + "("
            + ", ".join(
                f"{f.attname}={getattr(self, f.attname, None)!r}"
                for f in self._meta.fields
            )
            + ")"
        )

    def save(self):
        pass

    def delete(self):
        self.records().delete(self)

    def _to_fm_dict(self):
        fm_dict = dict()
        for field in self._meta.fields:
            fm_dict[field.name] = getattr(self, field.attname)

        return fm_dict

    @classmethod
    def _from_fm_record(cls, record: FMRecord):
        kwargs = {
            "record_id": record.record_id,
            "mod_id": record.mod_id,
        }

        for name, value in record.raw_fields:
            if attname := cls._field_mapping.get(name.lower(), None):
                kwargs[attname] = value

        return cls(**kwargs)
