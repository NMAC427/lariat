from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic

from lariat._typing import T
from lariat.errors import ConversionError, FieldError
from lariat.models import symbolic as sym

if TYPE_CHECKING:
    from lariat.models import Model


class Field(Generic[T], ABC):
    def __init__(self, name: str, not_empty=False, lenient=True, calc=False):
        """
        :param name: The name of the field in the FileMaker layout.
        :param not_empty: If the value can be None or not.
        :param lenient: Bool specifying if type conversion should be lenient or strict.
        :param calc: Bool specifying if the field is the result of a calculation
            or not. Only fields with calc=False can be set.
        """
        self.name = name
        self.not_empty = not_empty
        self.lenient = lenient
        self.calc = calc

        self.attname = None

    def contribute_to_class(self, cls, name):
        self.attname = name
        setattr(cls, name, self)
        cls._meta.add_field(self)

    def __get__(self, instance: Model, owner=None):
        if instance is None:
            # If __get__ gets called on the class instead of an instance.
            return self.symbolic()

        instance_state = instance.__dict__
        if self.attname not in instance_state:
            if self.not_empty:
                raise ValueError(
                    f"Value for field '{self.attname}' not set (can't be empty)."
                )
            return None

        return instance_state[self.attname]

    def __set__(self, instance: Model, value: T):
        if self.calc:
            raise AttributeError("Can't set field the value of a calculated field.")

        instance_state = instance.__dict__

        if value is None:
            if self.not_empty:
                raise FieldError(
                    f"Field '{self.attname}' is non empty. It's value can't be set to"
                    " None."
                )
            instance_state[self.attname] = None
        else:
            instance_state[self.attname] = self.to_python(value)

    def force_set(self, instance: Model, value: T):
        instance_state = instance.__dict__
        instance_state[self.attname] = self.to_python(value)

    def __repr__(self):
        return f"<{type(self).__name__} '{self.name}'>"

    @abstractmethod
    def to_python(self, value) -> T:
        """
        Convert the input value to the correct Python data type for this
        field. If this conversion fails, a lariat.exception.ConversionError
        should get raised.
        """

    @abstractmethod
    def symbolic(self) -> sym.SField[T]:
        ...


class IntField(Field[int]):
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

    def symbolic(self):
        return sym.IntSField(self)

    def __get__(self, instance, owner=None) -> int | sym.IntSField:
        return super().__get__(instance, owner)


class FloatField(Field[float]):
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

    def symbolic(self):
        return sym.FloatSField(self)

    def __get__(self, instance, owner=None) -> float | sym.FloatSField:
        return super().__get__(instance, owner)


class StringField(Field[str]):
    def to_python(self, value):
        if isinstance(value, str):
            return value
        return str(value)

    def symbolic(self):
        return sym.StringSField(self)

    def __get__(self, instance, owner=None) -> str | sym.StringSField:
        return super().__get__(instance, owner)


class BoolField(Field[bool]):
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

    def symbolic(self):
        return sym.BoolSField(self)

    def __get__(self, instance, owner=None) -> bool | sym.BoolSField:
        return super().__get__(instance, owner)


class _ListField(Field):
    # TODO: Implement in the future. This is not as important.
    # API INTERFACE:  ListField(IntField('Price{}'), IntField('Bestellungen{}'), StringField('MenuName{}'))
    def __new__(cls, *args, **kwargs):
        raise NotImplementedError
