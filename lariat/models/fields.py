from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from lariat.errors import FieldError, ConversionError

if TYPE_CHECKING:
    from lariat.models import Model


class SymbolicField:
    """Interface to reference and manipulate a column symbolically"""

    # TODO: Allow refering to a field using this symbolic field
    #       instead of strings / kwargs.
    #
    # eg:
    # Model.filter(
    #     Model.field_name >= 15
    # ).sort(
    #     -Model.field_name
    # )

    def __init__(
        self,
        field: Field,
        _neg: bool = False,
        _sort_by=None,
    ):
        self.field = field
        self._neg = _neg
        self._sort_by = _sort_by

    def _copy(self, **kwargs):
        return self.__class__(**{**self.__dict__, **kwargs})

    # Sorting

    def __neg__(self):
        """Negate to specify descending order."""
        return self._copy(_neg=not self._neg)

    def sort_by(self, value_list):
        """Specify a value list to sort by."""
        return self._copy(_sort_by=value_list)

    # Filtering

    def __eq__(self, other):
        return SymbolicFieldExpression(self.field, "eq", other)

    def __ne__(self, other):
        return SymbolicFieldExpression(self.field, "neq", other)

    def __gt__(self, other):
        return SymbolicFieldExpression(self.field, "gt", other)

    def __ge__(self, other):
        return SymbolicFieldExpression(self.field, "gte", other)

    def __lt__(self, other):
        return SymbolicFieldExpression(self.field, "lt", other)

    def __le__(self, other):
        return SymbolicFieldExpression(self.field, "lte", other)

    def contains(self, other):
        return SymbolicFieldExpression(self.field, "cn", other)

    def begins_with(self, other):
        return SymbolicFieldExpression(self.field, "bw", other)

    def ends_with(self, other):
        return SymbolicFieldExpression(self.field, "ew", other)


class SymbolicFieldExpression:
    def __init__(self, lhs, op: str, rhs):
        self.lhs = lhs
        self.op = op
        self.rhs = rhs


class FieldAttribute:
    """
    The getter / setter that each defined field gets replaced with in a model instance.
    """

    def __init__(self, field: Field):
        self.field = field

    def __get__(self, instance: Model, owner=None) -> Any:
        if instance is None:
            # If __get__ gets called on the class instead of an instance.
            return SymbolicField(self.field)

        instance_state = instance.__dict__
        field_name = self.field.attname

        if field_name not in instance_state:
            if self.field.not_empty:
                raise ValueError(
                    f"Value for field '{field_name}' not set (can't be empty)."
                )
            return None

        return instance_state[field_name]

    def __set__(self, instance, value):
        instance_state = instance.__dict__
        field_name = self.field.attname

        # Handle None
        if value is None:
            if self.field.not_empty:
                raise FieldError(
                    f"Field '{field_name}' is non empty. It's value can't be set to"
                    " None."
                )
            instance_state[field_name] = None
            return

        # Convert to python value and then store in the instance
        python_value = self.field.to_python(value)
        instance_state[field_name] = python_value


# Fields


class Field:
    def __init__(self, name: str, not_empty: bool = False, lenient: bool = True):
        """
        :param name: The name of the field in the FileMaker layout.
        :param not_empty: It the value can be None or not.
        :param lenient: Bool specifying if type conversion should be lenient tor strict.
        """
        self.name = name
        self.not_empty = not_empty
        self.lenient = lenient

    def contribute_to_class(self, cls, name):
        self.attname = name
        setattr(cls, name, FieldAttribute(self))
        cls._meta.add_field(self)

    def to_python(self, value):
        """
        Convert the input value to the correct Python data type for this
        field. If this conversion fails, a lariat.exception.ConversionError
        should get raised.
        """
        return value


class IntField(Field):
    regex = re.compile("[^0-9.]")

    def to_python(self, value):
        try:
            return int(value)
        except (TypeError, ValueError) as e:
            # Try to convert lenient
            if self.lenient:
                value = self.regex.sub("", value)
                value = value.split(".")[0]

                try:
                    return int(value)
                except (TypeError, ValueError):
                    pass

            if self.not_empty:
                raise ConversionError(e)
            return None


class FloatField(Field):
    regex = re.compile("[^0-9.]")

    def to_python(self, value: str):
        try:
            return float(value)
        except (TypeError, ValueError) as e:
            # Try to convert lenient
            if self.lenient:
                value = self.regex.sub("", value)

                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass

            if self.not_empty:
                raise ConversionError(e)
            return None


class StringField(Field):
    def to_python(self, value):
        if isinstance(value, str):
            return value
        return str(value)


class BoolField(Field):
    def to_python(self, value):
        if value in (True, False):
            # 1/0 are equal to True/False. bool() converts former to latter.
            return bool(value)
        if value in ("t", "true", "True", "1", "yes"):
            return True
        if value in ("f", "false", "False", "0", "no"):
            return False
        if self.not_empty:
            raise ConversionError(f"Couldn't convert value {value!r} to a boolean.")


class ListField(Field):
    # TODO: Implement in the future. This is not as important.
    # API INTERFACE:  ListField(IntField('Price{}'), IntField('Bestellungen{}'), StringField('MenuName{}'))
    def __new__(cls, *args, **kwargs):
        raise NotImplementedError
