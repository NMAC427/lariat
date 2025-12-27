from __future__ import annotations

import inspect
import itertools
from typing import Type

from lariat._typing import ModelT
from lariat.core.parser import FMRecord
from lariat.core.server import FMServer
from lariat.models.options import ModelOptions
from lariat.models.query_builder import QueryBuilder, QuerySet

ScriptT = tuple[str, str]


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
        new_class: type[Model] = super().__new__(cls, name, bases, new_attrs, **kwargs)  # type: ignore

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
    record_id: int | None
    mod_id: int | None

    # Query interface
    @classmethod
    def records(cls: type[ModelT]) -> QuerySet[ModelT]:
        return QuerySet(cls)

    def __init__(self, *, record_id=None, mod_id=None, _from_fm_record=False, **kwargs):
        super().__init__()
        self.record_id = record_id
        self.mod_id = mod_id

        for name, value in kwargs.items():
            if name not in type(self).__dict__:
                raise AttributeError(f"No such attribute '{name}'.")

            if _from_fm_record:
                # Ignores any type of setter protection or value checks if
                # the value comes from FileMaker itself
                field = type(self).__dict__[name]
                field.force_set(self, value)
            else:
                setattr(self, name, value)

    def __repr__(self):
        base_fields = [
            f"record_id={self.record_id!r}",
            f"mod_id={self.mod_id!r}",
        ]

        fields = self._meta.fields + self._meta.list_fields
        formatted_fields = (
            f"{f.attname}={getattr(self, f.attname, None)!r}"
            for f in fields
            if not f.attname.startswith("__")
        )

        return (
            self.__class__.__qualname__
            + "("
            + ", ".join(itertools.chain(base_fields, formatted_fields))
            + ")"
        )

    def save(
        self,
        script_after: ScriptT = None,
        script_prefind: ScriptT = None,
        script_presort: ScriptT = None,
    ) -> None:
        qb = QueryBuilder(self)

        if script_after is not None:
            qb = qb.script("after", *script_after)
        if script_prefind is not None:
            qb = qb.script("prefind", *script_prefind)
        if script_presort is not None:
            qb = qb.script("presort", *script_presort)

        if self.record_id is None:
            query = qb.build_query("-new", scripts=True)
        else:
            query = qb.build_query("-edit", scripts=True)
            query.add_param("-recid", self.record_id)

        for name, value in self._to_fm_dict().items():
            if value is not None:
                query.add_field_param(name, value)

        server = FMServer.default
        result = server.run_query_model(query, type(self))[0]
        self.__dict__ = result.__dict__

    def delete(
        self,
        script_after: ScriptT = None,
        script_prefind: ScriptT = None,
        script_presort: ScriptT = None,
    ) -> None:
        qb = QueryBuilder(self)

        if script_after is not None:
            qb = qb.script("after", *script_after)
        if script_prefind is not None:
            qb = qb.script("prefind", *script_prefind)
        if script_presort is not None:
            qb = qb.script("presort", *script_presort)

        query = qb.build_query("-delete", scripts=True)

        recid = self.record_id
        assert recid is not None
        query.add_param("-recid", recid)

        server = FMServer.default
        server.run_query(query)

    def as_dict(self):
        return {
            field.attname: getattr(self, field.attname) for field in self._meta.fields
        }

    def _to_fm_dict(self):
        return {
            field.name: field.to_filemaker(getattr(self, field.attname))
            for field in self._meta.fields
            if not field.calc
        }

    @classmethod
    def _from_fm_record(cls, record: FMRecord):
        kwargs = {
            "record_id": record.record_id,
            "mod_id": record.mod_id,
            "_from_fm_record": True,
        }

        for name, value in record.raw_fields:
            if attname := cls._field_mapping.get(name.lower(), None):
                kwargs[attname] = value

        return cls(**kwargs)
